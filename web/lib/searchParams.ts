import type { Budget, SearchPreferences } from "./types";

export const DEFAULT_PREFERENCES: SearchPreferences = {
  location: "",
  budget: "",
  cuisine: "",
  min_rating: "",
  preferences: "",
  limit: 5,
};

export function preferencesFromSearchParams(
  params: URLSearchParams,
): SearchPreferences {
  const budget = params.get("budget");
  const minRating = params.get("min_rating");
  const limitRaw = params.get("limit");
  const limit = limitRaw ? Number(limitRaw) : 5;

  return {
    location: params.get("location")?.trim() || "",
    budget: isBudget(budget) ? budget : "",
    cuisine: params.get("cuisine")?.trim() || "",
    min_rating:
      minRating !== null && minRating !== "" && !Number.isNaN(Number(minRating))
        ? Number(minRating)
        : "",
    preferences: params.get("preferences")?.trim() || "",
    limit: Number.isFinite(limit) && limit >= 1 && limit <= 10 ? limit : 5,
  };
}

export function preferencesToSearchParams(
  prefs: SearchPreferences,
): URLSearchParams {
  const params = new URLSearchParams();
  if (prefs.location) {
    params.set("location", prefs.location);
  }
  if (prefs.budget) {
    params.set("budget", prefs.budget);
  }
  if (prefs.cuisine?.trim()) {
    params.set("cuisine", prefs.cuisine.trim());
  }
  if (prefs.min_rating !== "" && prefs.min_rating !== undefined) {
    params.set("min_rating", String(prefs.min_rating));
  }
  if (prefs.preferences?.trim()) {
    params.set("preferences", prefs.preferences.trim());
  }
  params.set("limit", String(prefs.limit || 5));
  return params;
}

export function preferencesLabel(prefs: SearchPreferences): string {
  const parts = [prefs.location || "Unknown area"];
  if (prefs.cuisine?.trim()) {
    parts.push(prefs.cuisine.trim());
  }
  if (prefs.budget) {
    parts.push(prefs.budget);
  }
  if (prefs.min_rating !== "" && prefs.min_rating !== undefined) {
    parts.push(`≥ ${prefs.min_rating}`);
  }
  return parts.join(" · ");
}

function isBudget(value: string | null): value is Budget {
  return value === "low" || value === "medium" || value === "high";
}
