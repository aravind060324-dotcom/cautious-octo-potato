import type {
  CuisineCount,
  RecommendationResponse,
  SearchPreferences,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function recommendationBody(prefs: SearchPreferences) {
  const body: Record<string, string | number> = {
    location: prefs.location,
    limit: prefs.limit,
  };
  if (prefs.budget) {
    body.budget = prefs.budget;
  }
  const cuisine = prefs.cuisine?.trim();
  if (cuisine) {
    body.cuisine = cuisine;
  }
  if (prefs.min_rating !== "" && prefs.min_rating !== undefined) {
    body.min_rating = Number(prefs.min_rating);
  }
  const wishes = prefs.preferences?.trim();
  if (wishes) {
    body.preferences = wishes;
  }
  return body;
}

export async function fetchLocations(): Promise<string[]> {
  const response = await fetch("/api/locations");
  if (!response.ok) {
    throw new ApiError(response.status, null, "Failed to load locations");
  }
  const data = (await response.json()) as { locations: string[] };
  return data.locations || [];
}

export async function fetchCuisines(): Promise<CuisineCount[]> {
  const response = await fetch("/api/cuisines");
  if (!response.ok) {
    throw new ApiError(response.status, null, "Failed to load cuisines");
  }
  const data = (await response.json()) as { cuisines: CuisineCount[] };
  return data.cuisines || [];
}

export async function fetchRecommendations(
  prefs: SearchPreferences,
): Promise<RecommendationResponse> {
  const response = await fetch("/api/recommendations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(recommendationBody(prefs)),
  });
  if (response.status === 422) {
    throw new ApiError(422, await response.json(), "Validation failed");
  }
  if (!response.ok) {
    throw new ApiError(response.status, null, "Recommendations unavailable");
  }
  return (await response.json()) as RecommendationResponse;
}
