"""In-memory restaurant catalog and the six filter steps."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from app.catalog.models import Preferences, Restaurant
from app.config import ALL_BANGALORE, Settings


class CatalogError(RuntimeError):
    """The catalog file is missing or cannot be read."""


class CuisineCount(NamedTuple):
    """A cuisine token and how many restaurants list it."""

    name: str
    count: int


@dataclass(frozen=True)
class FilterResult:
    """Rows after the cap, plus how many rows survived the filters."""

    restaurants: tuple[Restaurant, ...]
    candidate_count: int


class CatalogStore:
    """Restaurants loaded once, with neighborhood and cuisine indexes."""

    def __init__(
        self,
        restaurants: Sequence[Restaurant],
        *,
        settings: Settings | None = None,
        max_candidates: int | None = None,
    ) -> None:
        self._settings = settings or Settings(_env_file=None)
        chosen = self._settings.max_candidates if max_candidates is None else max_candidates
        if not 1 <= chosen <= 30:
            raise ValueError("max_candidates must be from 1 to 30")
        self.max_candidates = chosen
        self.restaurants = tuple(restaurants)
        self.locations = _locations(self.restaurants)
        self.cuisines = _cuisine_counts(self.restaurants)

    @classmethod
    def load(cls, path: str | Path, *, settings: Settings | None = None) -> CatalogStore:
        """Read a Parquet catalog. A missing or unreadable file is an error."""
        catalog_path = Path(path)
        if not catalog_path.is_file():
            raise CatalogError(f"Catalog file is missing: {catalog_path}")
        try:
            frame = pd.read_parquet(catalog_path)
            restaurants = tuple(_restaurant_from_row(row) for row in frame.to_dict(orient="records"))
        except CatalogError:
            raise
        except Exception as exc:
            raise CatalogError(f"Catalog file is unreadable: {catalog_path}") from exc
        return cls(restaurants, settings=settings)

    def filter(self, preferences: Preferences) -> FilterResult:
        """Apply location, cuisine, rating, and budget, then sort and cap.

        Extra wishes are ignored. They do not add or remove rows.
        """
        rows = list(self.restaurants)
        location = preferences.location.strip()
        if location.casefold() != ALL_BANGALORE.casefold():
            wanted = location.casefold()
            rows = [row for row in rows if row.location.casefold() == wanted]

        if preferences.cuisine:
            needle = preferences.cuisine.casefold()
            rows = [
                row
                for row in rows
                if any(needle in token.casefold() for token in row.cuisines)
            ]

        if preferences.min_rating is not None:
            minimum = preferences.min_rating
            rows = [row for row in rows if row.rating is not None and row.rating >= minimum]

        if preferences.budget is not None:
            lower, upper = self._settings.budget_bounds(preferences.budget)
            rows = [row for row in rows if _cost_in_band(row.cost_for_two, lower, upper)]

        rows.sort(key=_rank_key)
        return FilterResult(
            restaurants=tuple(rows[: self.max_candidates]),
            candidate_count=len(rows),
        )


def _locations(restaurants: Sequence[Restaurant]) -> tuple[str, ...]:
    names = {restaurant.location.strip() for restaurant in restaurants if restaurant.location.strip()}
    return tuple(sorted(names))


def _cuisine_counts(restaurants: Sequence[Restaurant]) -> tuple[CuisineCount, ...]:
    counts: dict[str, int] = {}
    for restaurant in restaurants:
        seen: set[str] = set()
        for token in restaurant.cuisines:
            name = token.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            counts[name] = counts.get(name, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    return tuple(CuisineCount(name, count) for name, count in ordered)


def _cost_in_band(cost: int | None, lower: int, upper: int | None) -> bool:
    if cost is None:
        return False
    if cost < lower:
        return False
    if upper is not None and cost > upper:
        return False
    return True


def _rank_key(restaurant: Restaurant) -> tuple[bool, float, int]:
    """Rated rows first, highest rating, then most votes. Original order breaks ties."""
    if restaurant.rating is None:
        return (True, 0.0, -restaurant.votes)
    return (False, -float(restaurant.rating), -restaurant.votes)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict, str, bytes)):
        return False
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    # An array of flags is not a scalar missing value.
    if getattr(missing, "shape", None) not in (None, ()):
        return False
    return bool(missing)


def _optional_int(value: object) -> int | None:
    if _is_missing(value):
        return None
    return int(value)  # type: ignore[arg-type]


def _optional_float(value: object) -> float | None:
    if _is_missing(value):
        return None
    return float(value)  # type: ignore[arg-type]


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
        value = value.tolist()
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for item in value:
            if item is None or _is_missing(item):
                continue
            text = str(item).strip()
            if text:
                items.append(text)
        return items
    if _is_missing(value):
        return []
    text = str(value).strip()
    return [text] if text else []


def _restaurant_from_row(row: dict[str, object]) -> Restaurant:
    try:
        return Restaurant.model_validate(
            {
                "id": "" if _is_missing(row.get("id")) else str(row.get("id")),
                "name": "" if _is_missing(row.get("name")) else str(row.get("name")),
                "address": "" if _is_missing(row.get("address")) else str(row.get("address")),
                "location": "" if _is_missing(row.get("location")) else str(row.get("location")),
                "cuisines": _string_list(row.get("cuisines")),
                "cost_for_two": _optional_int(row.get("cost_for_two")),
                "rating": _optional_float(row.get("rating")),
                "votes": 0 if _is_missing(row.get("votes")) else int(row.get("votes")),  # type: ignore[arg-type]
                "rest_types": _string_list(row.get("rest_types")),
                "dishes_liked": _string_list(row.get("dishes_liked")),
                "online_order": bool(row.get("online_order")),
                "book_table": bool(row.get("book_table")),
                "listed_types": _string_list(row.get("listed_types")),
                "review_snippets": _string_list(row.get("review_snippets")),
                "url": "" if _is_missing(row.get("url")) else str(row.get("url")),
            }
        )
    except Exception as exc:
        raise CatalogError(f"Catalog row could not be read: {row.get('id')}") from exc
