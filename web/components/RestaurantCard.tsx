"use client";

import type { CSSProperties } from "react";
import type { RestaurantCard as Card } from "@/lib/types";
import { FavoritesButton } from "./FavoritesButton";

type Props = {
  card: Card;
  enterIndex?: number;
  favorite: boolean;
  compared: boolean;
  compareDisabled?: boolean;
  onOpen: () => void;
  onToggleFavorite: () => void;
  onToggleCompare: () => void;
};

function formatRupees(amount: number) {
  return `₹${Number(amount).toLocaleString("en-IN")}`;
}

export function RestaurantCard({
  card,
  enterIndex,
  favorite,
  compared,
  compareDisabled,
  onOpen,
  onToggleFavorite,
  onToggleCompare,
}: Props) {
  const cuisineText = card.cuisines?.filter(Boolean).join(", ");
  const experienceText = card.rest_types?.filter(Boolean).join(", ");
  const staggerMs =
    typeof enterIndex === "number" ? `${enterIndex * 60}ms` : undefined;

  return (
    <article
      className={`card is-clickable${staggerMs ? " card-enter" : ""}`}
      style={
        staggerMs
          ? ({ ["--stagger" as string]: staggerMs } as CSSProperties)
          : undefined
      }
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      <div className="card-body">
        <div className="card-top">
          <div className="card-heading">
            <div className="card-title-row">
              <span className="rank-badge">Rank #{card.rank}</span>
              <h3 className="card-title">{card.name}</h3>
            </div>
            <p className="card-cuisines">
              Cuisine: {cuisineText || "unavailable"}
            </p>
            <p className="card-experience">
              Experience: {experienceText || "unavailable"}
            </p>
          </div>
          <div className="rating-chip">
            <span className="material-symbols-outlined" aria-hidden>
              star
            </span>
            <span>
              {card.rating === null || card.rating === undefined
                ? "No rating yet"
                : `${card.rating} · ${(card.votes || 0).toLocaleString("en-IN")} ratings`}
            </span>
          </div>
        </div>

        <div className="card-meta">
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

        <div className="explanation">
          <span className="material-symbols-outlined" aria-hidden>
            tips_and_updates
          </span>
          <p>
            {card.explanation
              ? card.explanation
              : "A written reason is unavailable."}
          </p>
        </div>

        <div className="card-actions">
          <FavoritesButton active={favorite} onClick={onToggleFavorite} />
          <button
            type="button"
            className={`ghost-btn${compared ? " is-active" : ""}`}
            disabled={!compared && compareDisabled}
            onClick={(event) => {
              event.stopPropagation();
              onToggleCompare();
            }}
          >
            <span className="material-symbols-outlined" aria-hidden>
              compare_arrows
            </span>
            {compared ? "In compare" : "Compare"}
          </button>
        </div>
      </div>
    </article>
  );
}
