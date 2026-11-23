import type { RecentSearch, SearchPreferences } from "./types";
import { preferencesLabel } from "./searchParams";

const KEY = "bangalore-bites:recent-searches";
const MAX = 8;

function read(): RecentSearch[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as RecentSearch[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(items: RecentSearch[]) {
  window.localStorage.setItem(KEY, JSON.stringify(items));
}

export function listRecentSearches(): RecentSearch[] {
  return read();
}

export function pushRecentSearch(prefs: SearchPreferences): RecentSearch[] {
  if (!prefs.location.trim()) {
    return read();
  }
  const entry: RecentSearch = {
    id: `${Date.now()}-${prefs.location}`,
    savedAt: new Date().toISOString(),
    preferences: { ...prefs },
    label: preferencesLabel(prefs),
  };
  const rest = read().filter(
    (item) =>
      item.preferences.location !== prefs.location ||
      item.preferences.budget !== prefs.budget ||
      item.preferences.cuisine !== prefs.cuisine ||
      item.preferences.min_rating !== prefs.min_rating ||
      item.preferences.preferences !== prefs.preferences ||
      item.preferences.limit !== prefs.limit,
  );
  const next = [entry, ...rest].slice(0, MAX);
  write(next);
  return next;
}
