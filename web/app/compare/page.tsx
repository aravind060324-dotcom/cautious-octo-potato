"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  clearCompare,
  listCompare,
  removeCompare,
  type CompareItem,
} from "@/lib/compare";

function formatRupees(amount: number | null) {
  if (amount === null || amount === undefined) {
    return "Cost unavailable";
  }
  return `₹${Number(amount).toLocaleString("en-IN")} for two`;
}

export default function ComparePage() {
  const [items, setItems] = useState<CompareItem[]>([]);

  useEffect(() => {
    setItems(listCompare());
  }, []);

  if (items.length === 0) {
    return (
      <div>
        <h2 className="page-title">Compare</h2>
        <section className="empty-state">
          <h2>Nothing to compare yet</h2>
          <p className="empty-copy">
            Pin up to three restaurants from search results, then return here.
          </p>
          <Link href="/" className="primary-btn" style={{ width: "auto", marginTop: "1rem" }}>
            Back to search
          </Link>
        </section>
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "1rem",
          alignItems: "center",
          marginBottom: "1.5rem",
        }}
      >
        <h2 className="page-title" style={{ margin: 0 }}>
          Compare
        </h2>
        <button
          type="button"
          className="ghost-btn"
          onClick={() => setItems(clearCompare())}
        >
          Clear all
        </button>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table className="compare-table">
          <thead>
            <tr>
              <th>Field</th>
              {items.map((item) => (
                <th key={item.id}>
                  {item.name}
                  <div>
                    <button
                      type="button"
                      className="ghost-btn"
                      style={{ marginTop: "0.5rem" }}
                      onClick={() => setItems(removeCompare(item.id))}
                    >
                      Remove
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Neighborhood</td>
              {items.map((item) => (
                <td key={`${item.id}-loc`}>{item.location}</td>
              ))}
            </tr>
            <tr>
              <td>Cuisine</td>
              {items.map((item) => (
                <td key={`${item.id}-cui`}>
                  {item.cuisines.filter(Boolean).join(", ") || "unavailable"}
                </td>
              ))}
            </tr>
            <tr>
              <td>Experience</td>
              {items.map((item) => (
                <td key={`${item.id}-exp`}>
                  {item.rest_types?.filter(Boolean).join(", ") || "unavailable"}
                </td>
              ))}
            </tr>
            <tr>
              <td>Rating</td>
              {items.map((item) => (
                <td key={`${item.id}-rat`}>
                  {item.rating === null || item.rating === undefined
                    ? "No rating yet"
                    : `${item.rating} · ${(item.votes || 0).toLocaleString("en-IN")} ratings`}
                </td>
              ))}
            </tr>
            <tr>
              <td>Cost for two</td>
              {items.map((item) => (
                <td key={`${item.id}-cost`}>{formatRupees(item.cost_for_two)}</td>
              ))}
            </tr>
            <tr>
              <td>Why it fits</td>
              {items.map((item) => (
                <td key={`${item.id}-why`}>
                  {item.explanation || "A written reason is unavailable."}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
