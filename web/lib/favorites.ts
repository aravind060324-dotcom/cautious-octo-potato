import type { FavoriteRestaurant, RestaurantCard } from "./types";

const KEY = "bangalore-bites:favorites";

function read(): FavoriteRestaurant[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as FavoriteRestaurant[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(items: FavoriteRestaurant[]) {
  window.localStorage.setItem(KEY, JSON.stringify(items));
}

export function listFavorites(): FavoriteRestaurant[] {
  return read().sort((a, b) => b.savedAt.localeCompare(a.savedAt));
}

export function isFavorite(id: string): boolean {
  return read().some((item) => item.id === id);
}

export function toggleFavorite(card: RestaurantCard | FavoriteRestaurant): FavoriteRestaurant[] {
  const current = read();
  const exists = current.some((item) => item.id === card.id);
  const next = exists
    ? current.filter((item) => item.id !== card.id)
    : [
        {
          id: card.id,
          name: card.name,
          location: card.location,
          cuisines: card.cuisines,
          rest_types: card.rest_types || [],
          rating: card.rating,
          votes: card.votes,
          cost_for_two: card.cost_for_two,
          explanation: "explanation" in card ? card.explanation : "",
          savedAt: new Date().toISOString(),
        },
        ...current,
      ];
  write(next);
  return next;
}

export function removeFavorite(id: string): FavoriteRestaurant[] {
  const next = read().filter((item) => item.id !== id);
  write(next);
  return next;
}
