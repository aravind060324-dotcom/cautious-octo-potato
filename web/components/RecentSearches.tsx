"use client";

import type { RecentSearch } from "@/lib/types";

type Props = {
  items: RecentSearch[];
  onSelect: (item: RecentSearch) => void;
};

export function RecentSearches({ items, onSelect }: Props) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="recent-list" aria-label="Recent searches">
      <p className="hint" style={{ marginBottom: "0.35rem" }}>
        Recent searches
      </p>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className="recent-item"
          onClick={() => onSelect(item)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
