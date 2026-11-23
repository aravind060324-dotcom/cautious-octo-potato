"use client";

import Link from "next/link";
import type { CompareItem } from "@/lib/compare";

type Props = {
  items: CompareItem[];
  onClear: () => void;
  onRemove: (id: string) => void;
};

export function CompareBar({ items, onClear, onRemove }: Props) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="compare-bar" role="status">
      <div>
        <strong>
          Compare tray · {items.length}/3
        </strong>
        <div className="filter-chips" style={{ marginTop: "0.5rem" }}>
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              className="chip"
              onClick={() => onRemove(item.id)}
              title="Remove"
            >
              {item.name} ×
            </button>
          ))}
        </div>
      </div>
      <div className="card-actions">
        <button type="button" className="ghost-btn" onClick={onClear}>
          Clear
        </button>
        <Link href="/compare" className="primary-btn" style={{ width: "auto" }}>
          Open compare
        </Link>
      </div>
    </div>
  );
}
