"""Recommendation service: join model output to catalog rows, and fall back."""

from __future__ import annotations

import json

from app.catalog.models import Preferences, Restaurant
from app.catalog.store import CatalogStore
from app.recommender.llm import LlmError
from app.recommender.service import (
    EMPTY_SUMMARY,
    FALLBACK_SUMMARY,
    RecommendationService,
)


class FakeClient:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls = 0
        self.messages: list[dict[str, str]] | None = None

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        self.messages = list(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _restaurant(**overrides: object) -> Restaurant:
    fields: dict[str, object] = {
        "id": "a",
        "name": "Alpha",
        "address": "1 Street",
        "location": "Banashankari",
        "cuisines": ["Italian"],
        "cost_for_two": 600,
        "rating": 4.0,
        "votes": 10,
        "rest_types": ["Cafe"],
        "dishes_liked": ["Pasta"],
        "online_order": True,
        "book_table": True,
        "listed_types": ["Delivery"],
        "review_snippets": ["Good pasta."],
        "url": "https://example.test/a",
    }
    fields.update(overrides)
    return Restaurant.model_validate(fields)


def _catalog() -> tuple[Restaurant, ...]:
    return (
        _restaurant(id="a", name="Alpha", rating=4.8, votes=100, cost_for_two=700),
        _restaurant(id="b", name="Bravo", rating=4.2, votes=80, cost_for_two=800, address="2 Street"),
        _restaurant(id="c", name="Charlie", rating=3.9, votes=50, cost_for_two=550, address="3 Street"),
    )


def _store(restaurants: tuple[Restaurant, ...] | None = None, max_candidates: int = 15) -> CatalogStore:
    return CatalogStore(restaurants if restaurants is not None else _catalog(), max_candidates=max_candidates)


def _preferences(**overrides: object) -> Preferences:
    fields: dict[str, object] = {"location": "Banashankari", "limit": 3}
    fields.update(overrides)
    return Preferences.model_validate(fields)


def _ranking(items: list[dict[str, object]], summary: str = "Ranked.") -> str:
    return json.dumps({"summary": summary, "recommendations": items})


def test_empty_filter_does_not_call_the_client():
    client = FakeClient(_ranking([]))
    result = RecommendationService().recommend(
        _preferences(location="Mysore"),
        _store(),
        client,
    )

    assert client.calls == 0
    assert result.recommendations == ()
    assert result.candidate_count == 0
    assert result.explanations_available is False
    assert result.summary == EMPTY_SUMMARY
    assert result.applied_filters == {"location": "Mysore"}


def test_model_order_is_kept_and_card_facts_come_from_the_catalog():
    client = FakeClient(
        _ranking(
            [
                {"id": "c", "rank": 1, "explanation": "Best for a quick meal, rated 9.9."},
                {"id": "b", "rank": 2, "explanation": "Quiet room."},
                {"id": "a", "rank": 3, "explanation": "Popular."},
            ]
        )
    )
    catalog = {row.id: row for row in _catalog()}
    result = RecommendationService().recommend(_preferences(), _store(), client)

    assert [card.id for card in result.recommendations] == ["c", "b", "a"]
    assert [card.rank for card in result.recommendations] == [1, 2, 3]
    assert result.explanations_available is True
    for card in result.recommendations:
        source = catalog[card.id]
        assert card.rating == source.rating
        assert card.cost_for_two == source.cost_for_two
        assert card.name == source.name
        assert card.cuisines == source.cuisines
    assert result.recommendations[0].explanation == "Best for a quick meal, rated 9.9."
    assert result.recommendations[0].rating == 3.9
    assert result.candidate_count == 3


def test_unknown_id_is_dropped_and_the_shortfall_is_filled_in_catalog_order():
    client = FakeClient(
        _ranking(
            [
                {"id": "invented", "rank": 1, "explanation": "Not in the list."},
                {"id": "b", "rank": 2, "explanation": "Keep this reason."},
            ]
        )
    )
    result = RecommendationService().recommend(_preferences(limit=3), _store(), client)

    assert [card.id for card in result.recommendations] == ["b", "a", "c"]
    assert result.recommendations[0].explanation == "Keep this reason."
    assert result.recommendations[1].explanation == ""
    assert result.recommendations[2].explanation == ""
    assert result.explanations_available is False
    assert "invented" not in [card.id for card in result.recommendations]


def test_llm_error_returns_catalog_order_without_explanations():
    client = FakeClient(LlmError("Model request timed out"))
    result = RecommendationService().recommend(_preferences(limit=2), _store(), client)

    assert client.calls == 1
    assert [card.id for card in result.recommendations] == ["a", "b"]
    assert [card.explanation for card in result.recommendations] == ["", ""]
    assert result.explanations_available is False
    assert result.summary == FALLBACK_SUMMARY
    assert result.candidate_count == 3


def test_unparseable_text_uses_the_same_fallback():
    client = FakeClient("I recommend Alpha and Bravo.")
    result = RecommendationService().recommend(_preferences(), _store(), client)

    assert [card.id for card in result.recommendations] == ["a", "b", "c"]
    assert result.explanations_available is False
    assert result.summary == FALLBACK_SUMMARY


def test_duplicate_unknown_case_and_extra_items_collapse_to_the_limit():
    client = FakeClient(
        _ranking(
            [
                {"id": "B", "rank": 1, "explanation": "Wrong case."},
                {"id": "c", "rank": 5, "explanation": "Later rank."},
                {"id": "a", "rank": 4, "explanation": "First copy."},
                {"id": "a", "rank": 2, "explanation": "Better rank."},
                {"id": "b", "rank": 9, "explanation": "Past the limit."},
            ],
            summary="Trimmed.",
        )
    )
    result = RecommendationService().recommend(_preferences(limit=2), _store(), client)

    assert [card.id for card in result.recommendations] == ["a", "c"]
    assert [card.rank for card in result.recommendations] == [1, 2]
    assert result.recommendations[0].explanation == "Better rank."
    assert result.explanations_available is True
    assert result.summary == "Trimmed."


def test_missing_ranks_sort_last_and_are_renumbered_from_one():
    client = FakeClient(
        _ranking(
            [
                {"id": "a", "explanation": "No rank."},
                {"id": "c", "rank": 4, "explanation": "Has a rank."},
                {"id": "b", "rank": 8, "explanation": "Also ranked."},
            ]
        )
    )
    result = RecommendationService().recommend(_preferences(limit=3), _store(), client)

    assert [card.id for card in result.recommendations] == ["c", "b", "a"]
    assert [card.rank for card in result.recommendations] == [1, 2, 3]


def test_empty_model_list_is_filled_from_the_catalog():
    client = FakeClient(_ranking([], summary="Nothing useful."))
    result = RecommendationService().recommend(_preferences(limit=2), _store(), client)

    assert [card.id for card in result.recommendations] == ["a", "b"]
    assert [card.explanation for card in result.recommendations] == ["", ""]
    assert result.explanations_available is False
    assert result.summary == "Nothing useful."


def test_numeric_id_does_not_match_and_whitespace_explanation_is_empty():
    client = FakeClient(
        json.dumps(
            {
                "summary": "Partial.",
                "recommendations": [
                    {"id": 123, "rank": 1, "explanation": "Number"},
                    {"id": "a", "rank": 2, "explanation": "   "},
                ],
            }
        )
    )
    result = RecommendationService().recommend(_preferences(limit=1), _store(), client)

    assert [card.id for card in result.recommendations] == ["a"]
    assert result.recommendations[0].explanation == ""
    assert result.recommendations[0].rating == 4.8


def test_candidate_count_is_the_total_before_the_cap():
    rows = tuple(
        _restaurant(
            id=f"r{index}",
            name=f"Place {index}",
            rating=5 - index / 10,
            votes=100 - index,
            address=f"{index} Road",
        )
        for index in range(6)
    )
    client = FakeClient(
        _ranking([{"id": "r0", "rank": 1, "explanation": "Top of the short list."}])
    )
    result = RecommendationService().recommend(
        _preferences(limit=1),
        _store(rows, max_candidates=2),
        client,
    )

    assert result.candidate_count == 6
    assert [card.id for card in result.recommendations] == ["r0"]
    assert client.messages is not None
    assert "r0" in client.messages[1]["content"]
    assert "r2" not in client.messages[1]["content"]


def test_applied_filters_omit_unset_preferences():
    client = FakeClient(_ranking([{"id": "a", "rank": 1, "explanation": "Fits."}]))
    result = RecommendationService().recommend(
        _preferences(cuisine="Italian", preferences="family-friendly", limit=1),
        _store(),
        client,
    )

    assert result.applied_filters == {
        "location": "Banashankari",
        "cuisine": "Italian",
        "preferences": "family-friendly",
    }
