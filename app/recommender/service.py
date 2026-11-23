"""Filter the catalog, ask the model to rank that short list, and join the reply back."""

from __future__ import annotations

from dataclasses import dataclass

from app.catalog.models import Preferences, Restaurant
from app.catalog.store import CatalogStore
from app.recommender.llm import LlmClient, LlmError, Ranking, parse_ranking
from app.recommender.prompt import build_messages

EMPTY_SUMMARY = "No restaurants matched these choices."
FALLBACK_SUMMARY = "Written reasons are unavailable."


@dataclass(frozen=True)
class Recommendation:
    """One card. Displayed facts are copied from the catalog row."""

    rank: int
    id: str
    name: str
    location: str
    cuisines: list[str]
    rest_types: list[str]
    rating: float | None
    votes: int
    cost_for_two: int | None
    explanation: str


@dataclass(frozen=True)
class RecommendationResult:
    """The ranking the API will return. ``candidate_count`` is the pre-cap total."""

    summary: str
    applied_filters: dict[str, object]
    candidate_count: int
    explanations_available: bool
    recommendations: tuple[Recommendation, ...]


class RecommendationService:
    """One recommendation request. The model never sees rows the filters removed."""

    def recommend(
        self,
        preferences: Preferences,
        store: CatalogStore,
        client: LlmClient,
    ) -> RecommendationResult:
        filtered = store.filter(preferences)
        filters = applied_filters(preferences)
        if not filtered.restaurants:
            return RecommendationResult(
                summary=EMPTY_SUMMARY,
                applied_filters=filters,
                candidate_count=filtered.candidate_count,
                explanations_available=False,
                recommendations=(),
            )
        try:
            text = client.complete(build_messages(preferences, filtered.restaurants))
            ranking = parse_ranking(text)
        except LlmError:
            return _fallback(preferences, filtered.restaurants, filtered.candidate_count, filters)
        return _from_ranking(preferences, filtered.restaurants, filtered.candidate_count, filters, ranking)


def applied_filters(preferences: Preferences) -> dict[str, object]:
    """Location plus whichever optional preferences were set."""
    filters: dict[str, object] = {"location": preferences.location}
    if preferences.budget is not None:
        filters["budget"] = preferences.budget
    if preferences.cuisine is not None:
        filters["cuisine"] = preferences.cuisine
    if preferences.min_rating is not None:
        filters["min_rating"] = preferences.min_rating
    if preferences.preferences is not None:
        filters["preferences"] = preferences.preferences
    return filters


def _from_ranking(
    preferences: Preferences,
    candidates: tuple[Restaurant, ...],
    candidate_count: int,
    filters: dict[str, object],
    ranking: Ranking,
) -> RecommendationResult:
    by_id = {restaurant.id: restaurant for restaurant in candidates}
    ordered = sorted(
        enumerate(ranking.items),
        key=lambda pair: (
            pair[1].rank is None,
            pair[1].rank if pair[1].rank is not None else 0,
            pair[0],
        ),
    )
    chosen: list[Restaurant] = []
    explanations: dict[str, str] = {}
    seen: set[str] = set()
    for _, item in ordered:
        if item.id in seen or item.id not in by_id:
            continue
        seen.add(item.id)
        chosen.append(by_id[item.id])
        explanations[item.id] = item.explanation.strip()
        if len(chosen) >= preferences.limit:
            break

    padded = False
    if len(chosen) < preferences.limit and len(chosen) < len(candidates):
        for restaurant in candidates:
            if restaurant.id in seen:
                continue
            chosen.append(restaurant)
            explanations[restaurant.id] = ""
            seen.add(restaurant.id)
            padded = True
            if len(chosen) >= preferences.limit:
                break

    cards = tuple(
        _card(rank, restaurant, explanations.get(restaurant.id, ""))
        for rank, restaurant in enumerate(chosen, start=1)
    )
    return RecommendationResult(
        summary=ranking.summary.strip(),
        applied_filters=filters,
        candidate_count=candidate_count,
        explanations_available=not padded,
        recommendations=cards,
    )


def _fallback(
    preferences: Preferences,
    candidates: tuple[Restaurant, ...],
    candidate_count: int,
    filters: dict[str, object],
) -> RecommendationResult:
    cards = tuple(
        _card(rank, restaurant, "")
        for rank, restaurant in enumerate(candidates[: preferences.limit], start=1)
    )
    return RecommendationResult(
        summary=FALLBACK_SUMMARY,
        applied_filters=filters,
        candidate_count=candidate_count,
        explanations_available=False,
        recommendations=cards,
    )


def _card(rank: int, restaurant: Restaurant, explanation: str) -> Recommendation:
    return Recommendation(
        rank=rank,
        id=restaurant.id,
        name=restaurant.name,
        location=restaurant.location,
        cuisines=list(restaurant.cuisines),
        rest_types=list(restaurant.rest_types),
        rating=restaurant.rating,
        votes=restaurant.votes,
        cost_for_two=restaurant.cost_for_two,
        explanation=explanation.strip(),
    )
