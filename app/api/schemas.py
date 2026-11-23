"""HTTP request and response models for the recommendation API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecommendationRequest(BaseModel):
    """Preference body. An empty budget token is rejected; blank wishes are unset."""

    model_config = ConfigDict(extra="ignore")

    location: str = Field(min_length=1)
    budget: Literal["low", "medium", "high"] | None = None
    cuisine: str | None = None
    min_rating: float | None = Field(default=None, ge=0, le=5)
    preferences: str | None = Field(default=None, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("location", mode="before")
    @classmethod
    def location_is_present(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise ValueError("location is required")
            return text
        return value

    @field_validator("budget", mode="before")
    @classmethod
    def budget_token(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise ValueError("budget must be low, medium, or high")
            return text
        return value

    @field_validator("cuisine", "preferences", mode="before")
    @classmethod
    def blank_text_is_unset(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value


class HealthResponse(BaseModel):
    status: str
    restaurants: int


class LocationsResponse(BaseModel):
    locations: list[str]


class CuisineCountResponse(BaseModel):
    name: str
    count: int


class CuisinesResponse(BaseModel):
    cuisines: list[CuisineCountResponse]


class RecommendationCardResponse(BaseModel):
    rank: int
    id: str
    name: str
    location: str
    cuisines: list[str]
    rest_types: list[str] = []
    rating: float | None
    votes: int
    cost_for_two: int | None
    explanation: str


class RecommendationResponse(BaseModel):
    summary: str
    applied_filters: dict[str, str | float]
    candidate_count: int
    explanations_available: bool
    recommendations: list[RecommendationCardResponse]
