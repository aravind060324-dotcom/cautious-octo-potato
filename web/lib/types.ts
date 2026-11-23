export type Budget = "low" | "medium" | "high";

export type SearchPreferences = {
  location: string;
  budget?: Budget | "";
  cuisine?: string;
  min_rating?: number | "";
  preferences?: string;
  limit: number;
};

export type RestaurantCard = {
  rank: number;
  id: string;
  name: string;
  location: string;
  cuisines: string[];
  rest_types: string[];
  rating: number | null;
  votes: number;
  cost_for_two: number | null;
  explanation: string;
};

export type RecommendationResponse = {
  summary: string;
  applied_filters: Record<string, string | number>;
  candidate_count: number;
  explanations_available: boolean;
  recommendations: RestaurantCard[];
};

export type CuisineCount = {
  name: string;
  count: number;
};

export type FavoriteRestaurant = Omit<RestaurantCard, "rank" | "explanation"> & {
  savedAt: string;
  explanation?: string;
};

export type RecentSearch = {
  id: string;
  savedAt: string;
  preferences: SearchPreferences;
  label: string;
};
