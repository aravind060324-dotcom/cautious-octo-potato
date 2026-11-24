"use client";

import type { RecommendationResponse, RestaurantCard as Card } from "@/lib/types";
import { RestaurantCard } from "./RestaurantCard";

type Props = {
  result: RecommendationResponse | null;
  favoriteIds: Set<string>;
  compareIds: Set<string>;
  compareFull: boolean;
  onOpen: (card: Card) => void;
  onToggleFavorite: (card: Card) => void;
  onToggleCompare: (card: Card) => void;
};

export function ResultsList({
  result,
  favoriteIds,
  compareIds,
  compareFull,
  onOpen,
  onToggleFavorite,
  onToggleCompare,
}: Props) {
  if (!result) {
    return null;
  }

  const cards = [...result.recommendations].sort((a, b) => a.rank - b.rank);

  if (cards.length === 0) {
    return (
      <section className="empty-state">
        <div className="empty-glyph">
          <span className="material-symbols-outlined filled" aria-hidden>
            ramen_dining
          </span>
        </div>
        <h2>{result.summary || "No restaurants matched these choices."}</h2>
        <p className="empty-label">Choices used</p>
        <div className="filter-chips">
          {Object.entries(result.applied_filters || {}).map(([key, value]) => (
            <span key={key} className="chip">
              {key}: {String(value)}
            </span>
          ))}
        </div>
        <p className="empty-copy">
          No restaurants matched. Widen the search and try again.
        </p>
      </section>
    );
  }

  return (
    <div className="results">
      <div className="summary-card">
        <div className="summary-inner">
          <div className="summary-icon">
            <span className="material-symbols-outlined filled" aria-hidden>
              auto_awesome
            </span>
          </div>
          <div>
            <div className="summary-meta">
              <span className="summary-kicker">Curated for your evening</span>
              <span className="summary-count">
                • {cards.length} match{cards.length === 1 ? "" : "es"} ranked
              </span>
            </div>
            <p className="summary-text">{result.summary}</p>
          </div>
        </div>
      </div>

      {!result.explanations_available ? (
        <p className="note">
          Written reasons are unavailable. The list is ordered by rating.
        </p>
      ) : null}

      <div className="cards">
        {cards.map((card, index) => (
          <RestaurantCard
            key={card.id}
            card={card}
            enterIndex={index}
            favorite={favoriteIds.has(card.id)}
            compared={compareIds.has(card.id)}
            compareDisabled={compareFull}
            onOpen={() => onOpen(card)}
            onToggleFavorite={() => onToggleFavorite(card)}
            onToggleCompare={() => onToggleCompare(card)}
          />
        ))}
      </div>
    </div>
  );
}
