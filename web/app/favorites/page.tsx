"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listFavorites, removeFavorite } from "@/lib/favorites";
import type { FavoriteRestaurant } from "@/lib/types";

function formatRupees(amount: number) {
  return `₹${Number(amount).toLocaleString("en-IN")}`;
}

export default function FavoritesPage() {
  const [items, setItems] = useState<FavoriteRestaurant[]>([]);

  useEffect(() => {
    setItems(listFavorites());
  }, []);

  return (
    <div>
      <h2 className="page-title">Favorites</h2>
      {items.length === 0 ? (
        <section className="empty-state">
          <h2>No saved restaurants yet</h2>
          <p className="empty-copy">
            Heart a recommendation on the search page to keep it here.
          </p>
          <Link href="/" className="primary-btn" style={{ width: "auto", marginTop: "1rem" }}>
            Back to search
          </Link>
        </section>
      ) : (
        <div className="favorites-grid">
          {items.map((item) => (
            <article key={item.id} className="card">
              <div className="card-body">
                <div className="card-top">
                  <div className="card-heading">
                    <h3 className="card-title">{item.name}</h3>
                    <p className="card-cuisines">
                      Cuisine: {item.cuisines.filter(Boolean).join(", ") || "unavailable"}
                    </p>
                    <p className="card-experience">
                      Experience:{" "}
                      {item.rest_types?.filter(Boolean).join(", ") || "unavailable"}
                    </p>
                  </div>
                  <div className="rating-chip">
                    <span className="material-symbols-outlined" aria-hidden>
                      star
                    </span>
                    <span>
                      {item.rating === null || item.rating === undefined
                        ? "No rating yet"
                        : `${item.rating} · ${(item.votes || 0).toLocaleString("en-IN")} ratings`}
                    </span>
                  </div>
                </div>
                <div className="card-meta">
                  <span className="meta-item">
                    <span className="material-symbols-outlined" aria-hidden>
                      payments
                    </span>
                    {item.cost_for_two === null || item.cost_for_two === undefined
                      ? "Cost unavailable"
                      : `${formatRupees(item.cost_for_two)} for two`}
                  </span>
                  <span className="meta-item">
                    <span className="material-symbols-outlined" aria-hidden>
                      location_on
                    </span>
                    {item.location}
                  </span>
                </div>
                <div className="card-actions">
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => setItems(removeFavorite(item.id))}
                  >
                    Remove
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
