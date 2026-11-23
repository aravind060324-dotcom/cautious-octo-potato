"""Catalog load and the six filter steps. No model calls."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from app.catalog.models import Preferences, Restaurant
from app.catalog.store import CatalogError, CatalogStore
from app.config import Settings

MEDIUM_LOW = 501
MEDIUM_HIGH = 1000


def _restaurant(**overrides: object) -> Restaurant:
    fields: dict[str, object] = {
        "id": "r",
        "name": "Place",
        "address": "1 Street",
        "location": "Banashankari",
        "cuisines": ["North Indian"],
        "cost_for_two": 400,
        "rating": 4.0,
        "votes": 10,
        "rest_types": ["Casual Dining"],
        "dishes_liked": ["Dosa"],
        "online_order": True,
        "book_table": False,
        "listed_types": ["Delivery"],
        "review_snippets": ["Quick service."],
        "url": "https://example.test/place",
    }
    fields.update(overrides)
    return Restaurant.model_validate(fields)


def _sample_restaurants() -> tuple[Restaurant, ...]:
    return (
        _restaurant(
            id="it-bana",
            name="Onesta",
            location="Banashankari",
            cuisines=["Italian"],
            cost_for_two=600,
            rating=4.6,
            votes=2556,
        ),
        _restaurant(
            id="ch-bana",
            name="Wok",
            location="Banashankari",
            cuisines=["Chinese"],
            cost_for_two=300,
            rating=3.7,
            votes=100,
        ),
        _restaurant(
            id="it-jayanagar",
            name="Pasta House",
            location="Jayanagar",
            cuisines=["Italian"],
            cost_for_two=700,
            rating=4.2,
            votes=400,
        ),
        _restaurant(
            id="nulls",
            name="New Place",
            location="Banashankari",
            cuisines=["Italian"],
            cost_for_two=None,
            rating=None,
            votes=0,
        ),
        _restaurant(
            id="mix",
            name="Cafe Mex",
            location="Banashankari",
            cuisines=["Cafe", "Mexican", "Italian"],
            cost_for_two=800,
            rating=4.1,
            votes=50,
        ),
        _restaurant(
            id="hi-1",
            name="High One",
            cuisines=["South Indian"],
            cost_for_two=450,
            rating=4.9,
            votes=900,
        ),
        _restaurant(
            id="hi-2",
            name="High Two",
            cuisines=["South Indian"],
            cost_for_two=450,
            rating=4.8,
            votes=800,
        ),
        _restaurant(
            id="hi-3",
            name="High Three",
            cuisines=["South Indian"],
            cost_for_two=450,
            rating=4.7,
            votes=700,
        ),
    )


def _store(max_candidates: int = 15) -> CatalogStore:
    return CatalogStore(_sample_restaurants(), max_candidates=max_candidates)


def _prefs(**overrides: object) -> Preferences:
    fields: dict[str, object] = {"location": "Banashankari"}
    fields.update(overrides)
    return Preferences.model_validate(fields)


def test_combined_filters_keep_matching_banashankari_italian_rows():
    result = _store().filter(
        _prefs(location="Banashankari", cuisine="Italian", budget="medium", min_rating=4.0)
    )

    assert result.candidate_count == 2
    assert [row.id for row in result.restaurants] == ["it-bana", "mix"]
    for row in result.restaurants:
        assert row.location == "Banashankari"
        assert any("italian" in cuisine.casefold() for cuisine in row.cuisines)
        assert row.cost_for_two is not None
        assert MEDIUM_LOW <= row.cost_for_two <= MEDIUM_HIGH
        assert row.rating is not None and row.rating >= 4.0


def test_all_bangalore_italian_includes_other_neighborhoods():
    result = _store().filter(_prefs(location=" All Bangalore ", cuisine="italian"))

    ids = [row.id for row in result.restaurants]
    assert "it-jayanagar" in ids
    assert "it-bana" in ids
    assert "mix" in ids
    assert {row.location for row in result.restaurants} == {"Banashankari", "Jayanagar"}


def test_neighborhood_only_keeps_nulls_and_sorts_by_rating_then_votes():
    result = _store().filter(_prefs(location="banashankari"))

    assert [row.id for row in result.restaurants] == [
        "hi-1",
        "hi-2",
        "hi-3",
        "it-bana",
        "mix",
        "ch-bana",
        "nulls",
    ]
    assert result.candidate_count == 7
    assert result.restaurants[-1].rating is None
    assert result.restaurants[-1].cost_for_two is None


def test_null_rating_and_cost_drop_when_those_filters_are_set():
    store = _store()

    by_rating = store.filter(_prefs(min_rating=0))
    by_budget = store.filter(_prefs(budget="low"))

    assert "nulls" not in [row.id for row in by_rating.restaurants]
    assert "nulls" not in [row.id for row in by_budget.restaurants]
    assert all(row.rating is not None for row in by_rating.restaurants)
    assert all(row.cost_for_two is not None for row in by_budget.restaurants)


def test_cap_length_is_max_candidates_and_count_is_larger():
    result = _store(max_candidates=3).filter(_prefs())

    assert len(result.restaurants) == 3
    assert result.candidate_count == 7
    assert [row.id for row in result.restaurants] == ["hi-1", "hi-2", "hi-3"]


def test_empty_match_returns_no_rows():
    result = _store().filter(_prefs(location="Mysore", cuisine="Italian"))

    assert result.restaurants == ()
    assert result.candidate_count == 0


def test_extra_wishes_do_not_add_or_remove_rows():
    store = _store()
    plain = store.filter(_prefs(cuisine="Italian"))
    wished = store.filter(_prefs(cuisine="Italian", preferences="not Italian, only quick service"))

    assert [row.id for row in wished.restaurants] == [row.id for row in plain.restaurants]
    assert wished.candidate_count == plain.candidate_count


def test_equal_ratings_order_by_votes_and_stay_stable():
    first = _restaurant(id="a", name="A", rating=4.2, votes=20, address="1 Road")
    second = _restaurant(id="b", name="B", rating=4.2, votes=50, address="2 Road")
    third = _restaurant(id="c", name="C", rating=4.2, votes=20, address="3 Road")
    store = CatalogStore((first, second, third))

    once = store.filter(_prefs())
    twice = store.filter(_prefs())

    assert [row.id for row in once.restaurants] == ["b", "a", "c"]
    assert [row.id for row in twice.restaurants] == ["b", "a", "c"]


def test_cuisine_fragment_matches_tokens_that_contain_it():
    result = _store().filter(_prefs(cuisine="Indian"))

    ids = {row.id for row in result.restaurants}
    assert {"hi-1", "hi-2", "hi-3"} <= ids
    assert "it-bana" not in ids


def test_blank_cuisine_skips_the_cuisine_step():
    preferences = _prefs(cuisine="   ")

    assert preferences.cuisine is None
    result = _store().filter(preferences)
    assert result.candidate_count == 7


def test_empty_cuisine_list_is_excluded_when_a_cuisine_is_set():
    empty = _restaurant(id="empty", cuisines=[], rating=4.9, votes=9999)
    store = CatalogStore((_sample_restaurants()[0], empty))

    result = store.filter(_prefs(cuisine="Italian"))

    assert [row.id for row in result.restaurants] == ["it-bana"]


@pytest.mark.parametrize(
    ("cost", "budget", "kept"),
    [
        (500, "low", True),
        (500, "medium", False),
        (501, "low", False),
        (501, "medium", True),
        (1000, "medium", True),
        (1000, "high", False),
        (1001, "high", True),
        (1001, "medium", False),
    ],
)
def test_budget_bounds_are_inclusive(cost: int, budget: str, kept: bool):
    store = CatalogStore((_restaurant(id=f"c{cost}", cost_for_two=cost, rating=4.0),))

    result = store.filter(_prefs(budget=budget))

    assert result.candidate_count == (1 if kept else 0)


def test_minimum_rating_keeps_an_equal_score_and_drops_nulls():
    rated = _restaurant(id="exact", rating=4.0, votes=5)
    perfect = _restaurant(id="five", rating=5, votes=1, address="2 Road")
    missing = _restaurant(id="missing", rating=None, votes=9, address="3 Road")
    store = CatalogStore((rated, perfect, missing))

    at_four = store.filter(_prefs(min_rating=4))
    only_five = store.filter(_prefs(min_rating=5))
    zero = store.filter(_prefs(min_rating=0))

    assert [row.id for row in at_four.restaurants] == ["five", "exact"]
    assert [row.id for row in only_five.restaurants] == ["five"]
    assert [row.id for row in zero.restaurants] == ["five", "exact"]


def test_indexes_list_sorted_neighborhoods_and_cuisines_by_frequency():
    store = _store()

    assert store.locations == ("Banashankari", "Jayanagar")
    assert store.cuisines[0] == ("Italian", 4)
    assert store.cuisines[1] == ("South Indian", 3)
    counts = [item.count for item in store.cuisines]
    assert counts == sorted(counts, reverse=True)


def test_repeated_cuisine_on_one_restaurant_counts_once():
    store = CatalogStore((_restaurant(cuisines=["Italian", "Italian", " Pizza "]),))

    assert store.cuisines == (("Italian", 1), ("Pizza", 1))


def test_missing_catalog_raises():
    missing = Path("data/processed/does-not-exist.parquet")

    with pytest.raises(CatalogError, match="missing"):
        CatalogStore.load(missing)


def test_unreadable_catalog_raises(tmp_path: Path):
    broken = tmp_path / "restaurants.parquet"
    broken.write_text("not parquet", encoding="utf-8")

    with pytest.raises(CatalogError, match="unreadable"):
        CatalogStore.load(broken)


def test_load_reads_lists_and_null_numbers(tmp_path: Path):
    frame = pd.DataFrame(
        [
            {
                "id": "a",
                "name": "A",
                "address": "1 Road",
                "location": "Banashankari",
                "cuisines": ["Italian", "Pizza"],
                "cost_for_two": None,
                "rating": None,
                "votes": 10,
                "rest_types": ["Casual Dining"],
                "dishes_liked": ["Pasta"],
                "online_order": True,
                "book_table": False,
                "listed_types": ["Delivery"],
                "review_snippets": ["Nice pasta"],
                "url": "https://example.test/a",
            },
            {
                "id": "b",
                "name": "B",
                "address": "2 Road",
                "location": "Jayanagar",
                "cuisines": ["Chinese"],
                "cost_for_two": 1200,
                "rating": 4.4,
                "votes": 3,
                "rest_types": [],
                "dishes_liked": [],
                "online_order": False,
                "book_table": True,
                "listed_types": [],
                "review_snippets": [],
                "url": "",
            },
        ]
    )
    path = tmp_path / "restaurants.parquet"
    frame.to_parquet(path, index=False)

    store = CatalogStore.load(path, settings=Settings(_env_file=None))
    loaded = {row.id: row for row in store.restaurants}

    assert len(store.restaurants) == 2
    assert loaded["a"].rating is None
    assert loaded["a"].cost_for_two is None
    assert loaded["a"].cuisines == ["Italian", "Pizza"]
    assert loaded["b"].cost_for_two == 1200
    assert loaded["b"].rating == 4.4
    assert store.locations == ("Banashankari", "Jayanagar")


def test_preferences_reject_bad_rating_budget_and_long_wishes():
    with pytest.raises(ValidationError):
        _prefs(min_rating=6)
    with pytest.raises(ValidationError):
        _prefs(min_rating=-0.1)
    with pytest.raises(ValidationError):
        _prefs(budget="Low")
    with pytest.raises(ValidationError):
        _prefs(preferences="x" * 501)
    with pytest.raises(ValidationError):
        Preferences.model_validate({"location": "   "})

    blank = _prefs(preferences="   ", budget="")
    assert blank.preferences is None
    assert blank.budget is None
    assert blank.limit == 5
