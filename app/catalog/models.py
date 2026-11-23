"""Catalog record and the preferences used to filter it."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Restaurant(BaseModel):
    """Fields stored in the processed catalog. Phone numbers and menus are absent."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    address: str
    location: str
    cuisines: list[str] = Field(default_factory=list)
    cost_for_two: int | None = None
    rating: float | None = None
    votes: int = 0
    rest_types: list[str] = Field(default_factory=list)
    dishes_liked: list[str] = Field(default_factory=list)
    online_order: bool = False
    book_table: bool = False
    listed_types: list[str] = Field(default_factory=list)
    review_snippets: list[str] = Field(default_factory=list)
    url: str = ""


class Preferences(BaseModel):
    """Hard filters plus the soft wishes sent to the model later.

    Empty cuisine and wishes become unset. An unknown neighborhood is still
    accepted here; the HTTP layer rejects it once the live catalog is loaded.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    location: str = Field(min_length=1)
    budget: Literal["low", "medium", "high"] | None = None
    cuisine: str | None = None
    min_rating: float | None = Field(default=None, ge=0, le=5)
    preferences: str | None = Field(default=None, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("location")
    @classmethod
    def location_is_present(cls, value: str) -> str:
        if not value:
            raise ValueError("location is required")
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

    @field_validator("budget", mode="before")
    @classmethod
    def blank_budget_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
