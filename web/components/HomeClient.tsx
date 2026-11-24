"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ApiError, fetchCuisines, fetchLocations, fetchRecommendations } from "@/lib/api";
import {
  clearCompare,
  listCompare,
  removeCompare,
  toggleCompare,
  type CompareItem,
} from "@/lib/compare";
import { isFavorite, listFavorites, toggleFavorite } from "@/lib/favorites";
import { listRecentSearches, pushRecentSearch } from "@/lib/recentSearches";
import {
  DEFAULT_PREFERENCES,
  preferencesFromSearchParams,
  preferencesToSearchParams,
} from "@/lib/searchParams";
import type {
  RecentSearch,
  RecommendationResponse,
  RestaurantCard,
  SearchPreferences,
} from "@/lib/types";
import { CompareBar } from "./CompareBar";
import { DetailDrawer } from "./DetailDrawer";
import { RecentSearches } from "./RecentSearches";
import { ResultsList } from "./ResultsList";
import { SearchForm } from "./SearchForm";

export function HomeClient() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [prefs, setPrefs] = useState<SearchPreferences>(DEFAULT_PREFERENCES);
  const [locations, setLocations] = useState<string[]>([]);
  const [cuisines, setCuisines] = useState<string[]>([]);
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [status, setStatus] = useState("");
  const [statusError, setStatusError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<
    Partial<Record<keyof SearchPreferences | "form", string>>
  >({});
  const [selected, setSelected] = useState<RestaurantCard | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
  const [compareItems, setCompareItems] = useState<CompareItem[]>([]);
  const [recent, setRecent] = useState<RecentSearch[]>([]);
  const [bootstrapped, setBootstrapped] = useState(false);

  const compareIds = useMemo(
    () => new Set(compareItems.map((item) => item.id)),
    [compareItems],
  );

  useEffect(() => {
    setFavoriteIds(new Set(listFavorites().map((item) => item.id)));
    setCompareItems(listCompare());
    setRecent(listRecentSearches());
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [locs, cuisineRows] = await Promise.all([
          fetchLocations(),
          fetchCuisines(),
        ]);
        if (cancelled) {
          return;
        }
        setLocations(locs);
        setCuisines(cuisineRows.map((row) => row.name).filter(Boolean));
      } catch {
        if (!cancelled) {
          setStatus("The service is unavailable. You can try again.");
          setStatusError(true);
        }
      } finally {
        if (!cancelled) {
          setBootstrapped(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!bootstrapped) {
      return;
    }
    const fromUrl = preferencesFromSearchParams(
      new URLSearchParams(searchParams.toString()),
    );
    setPrefs(fromUrl);
    if (fromUrl.location) {
      void runSearch(fromUrl, { skipUrl: true, skipRecent: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bootstrapped]);

  async function runSearch(
    nextPrefs: SearchPreferences,
    options?: { skipUrl?: boolean; skipRecent?: boolean },
  ) {
    setErrors({});
    if (!nextPrefs.location.trim()) {
      setErrors({ location: "Choose a neighborhood." });
      return;
    }

    setLoading(true);
    setStatus("Results are being prepared.");
    setStatusError(false);
    setResult(null);
    setSelected(null);

    if (!options?.skipUrl) {
      const params = preferencesToSearchParams(nextPrefs);
      router.replace(`${pathname}?${params.toString()}`);
    }

    try {
      const data = await fetchRecommendations(nextPrefs);
      setResult(data);
      setStatus("");
      if (!options?.skipRecent) {
        setRecent(pushRecentSearch(nextPrefs));
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        applyValidationErrors(error.detail);
        setStatus("");
      } else {
        setStatus("The service is unavailable. You can try again.");
        setStatusError(true);
      }
    } finally {
      setLoading(false);
    }
  }

  function applyValidationErrors(detail: unknown) {
    if (typeof detail === "object" && detail && "detail" in detail) {
      const payload = (detail as { detail: unknown }).detail;
      if (typeof payload === "string") {
        setErrors({ form: payload });
        return;
      }
      if (Array.isArray(payload)) {
        const next: Partial<Record<keyof SearchPreferences | "form", string>> =
          {};
        for (const item of payload) {
          const loc = Array.isArray(item?.loc) ? item.loc : [];
          const field = loc[loc.length - 1];
          const message = item?.msg || "Check this field.";
          if (typeof field === "string") {
            next[field as keyof SearchPreferences] = message;
          } else {
            next.form = message;
          }
        }
        setErrors(next);
        return;
      }
    }
    setErrors({ form: "Check the form and try again." });
  }

  function handleToggleFavorite(card: RestaurantCard) {
    toggleFavorite(card);
    setFavoriteIds(new Set(listFavorites().map((item) => item.id)));
  }

  function handleToggleCompare(card: RestaurantCard) {
    const next = toggleCompare(card);
    setCompareItems(next);
  }

  return (
    <div className="layout">
      <div>
        <SearchForm
          value={prefs}
          locations={locations}
          cuisines={cuisines}
          loading={loading}
          errors={errors}
          onChange={setPrefs}
          onSubmit={() => void runSearch(prefs)}
        />
        <RecentSearches
          items={recent}
          onSelect={(item) => {
            setPrefs(item.preferences);
            void runSearch(item.preferences);
          }}
        />
      </div>

      <section className="results-column">
        {status ? (
          <p
            className={`status-banner${statusError ? " is-error" : ""}${
              !statusError && status === "Results are being prepared."
                ? " is-loading"
                : ""
            }`}
          >
            {status}
          </p>
        ) : null}
        <ResultsList
          result={result}
          favoriteIds={favoriteIds}
          compareIds={compareIds}
          compareFull={compareItems.length >= 3}
          onOpen={setSelected}
          onToggleFavorite={handleToggleFavorite}
          onToggleCompare={handleToggleCompare}
        />
        <CompareBar
          items={compareItems}
          onClear={() => setCompareItems(clearCompare())}
          onRemove={(id) => setCompareItems(removeCompare(id))}
        />
      </section>

      <DetailDrawer
        card={selected}
        favorite={selected ? isFavorite(selected.id) : false}
        compared={selected ? compareIds.has(selected.id) : false}
        compareDisabled={compareItems.length >= 3}
        onClose={() => setSelected(null)}
        onToggleFavorite={() => selected && handleToggleFavorite(selected)}
        onToggleCompare={() => selected && handleToggleCompare(selected)}
      />
    </div>
  );
}
