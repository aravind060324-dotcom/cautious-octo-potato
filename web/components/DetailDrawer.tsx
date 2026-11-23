"use client";

import type { RestaurantCard } from "@/lib/types";
import { FavoritesButton } from "./FavoritesButton";

type Props = {
  card: RestaurantCard | null;
  favorite: boolean;
  compared: boolean;
  compareDisabled?: boolean;
  onClose: () => void;
  onToggleFavorite: () => void;
  onToggleCompare: () => void;
};

function formatRupees(amount: number) {
  return `₹${Number(amount).toLocaleString("en-IN")}`;
}

export function DetailDrawer({
  card,
  favorite,
  compared,
  compareDisabled,
  onClose,
  onToggleFavorite,
  onToggleCompare,
}: Props) {
  if (!card) {
    return null;
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden />
      <aside className="drawer" role="dialog" aria-label={`${card.name} details`}>
        <div className="drawer-header">
          <div>
            <span className="rank-badge">Rank #{card.rank}</span>
            <h2>{card.name}</h2>
          </div>
          <button type="button" className="ghost-btn" onClick={onClose}>
            Close
          </button>
        </div>

        <p className="card-cuisines">
          Cuisine: {card.cuisines.filter(Boolean).join(", ") || "unavailable"}
        </p>
        <p className="card-experience">
          Experience:{" "}
          {card.rest_types?.filter(Boolean).join(", ") || "unavailable"}
        </p>

        <div className="card-meta" style={{ marginTop: "1rem" }}>
          <span className="meta-item">
            <span className="material-symbols-outlined" aria-hidden>
              star
            </span>
            {card.rating === null || card.rating === undefined
              ? "No rating yet"
              : `${card.rating} · ${(card.votes || 0).toLocaleString("en-IN")} ratings`}
          </span>
          <span className="meta-item">
            <span className="material-symbols-outlined" aria-hidden>
              payments
            </span>
            {card.cost_for_two === null || card.cost_for_two === undefined
              ? "Cost unavailable"
              : `${formatRupees(card.cost_for_two)} for two`}
          </span>
          <span className="meta-item">
            <span className="material-symbols-outlined" aria-hidden>
              location_on
            </span>
            {card.location}
          </span>
        </div>

        <div className="explanation" style={{ marginTop: "1.25rem" }}>
          <span className="material-symbols-outlined" aria-hidden>
            tips_and_updates
          </span>
          <p>
            {card.explanation
              ? card.explanation
              : "A written reason is unavailable."}
          </p>
        </div>

        <div className="card-actions" style={{ marginTop: "1.25rem" }}>
          <FavoritesButton active={favorite} onClick={onToggleFavorite} />
          <button
            type="button"
            className="ghost-btn"
            disabled={!compared && compareDisabled}
            onClick={onToggleCompare}
          >
            <span className="material-symbols-outlined" aria-hidden>
              compare_arrows
            </span>
            {compared ? "Remove from compare" : "Add to compare"}
          </button>
        </div>
      </aside>
    </>
  );
}
