import type { RestaurantCard } from "./types";

const KEY = "bangalore-bites:compare";
const MAX = 3;

export type CompareItem = Omit<RestaurantCard, "rank">;

function read(): CompareItem[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as CompareItem[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(items: CompareItem[]) {
  window.localStorage.setItem(KEY, JSON.stringify(items));
}

export function listCompare(): CompareItem[] {
  return read();
}

export function isInCompare(id: string): boolean {
  return read().some((item) => item.id === id);
}

export function toggleCompare(card: RestaurantCard | CompareItem): CompareItem[] {
  const current = read();
  const exists = current.some((item) => item.id === card.id);
  if (exists) {
    const next = current.filter((item) => item.id !== card.id);
    write(next);
    return next;
  }
  if (current.length >= MAX) {
    return current;
  }
  const next = [
    ...current,
    {
      id: card.id,
      name: card.name,
      location: card.location,
      cuisines: card.cuisines,
      rest_types: card.rest_types || [],
      rating: card.rating,
      votes: card.votes,
      cost_for_two: card.cost_for_two,
      explanation: "explanation" in card ? card.explanation || "" : "",
    },
  ];
  write(next);
  return next;
}

export function removeCompare(id: string): CompareItem[] {
  const next = read().filter((item) => item.id !== id);
  write(next);
  return next;
}

export function clearCompare(): CompareItem[] {
  write([]);
  return [];
}
