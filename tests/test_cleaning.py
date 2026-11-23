"""Cleaning, identity, and merge rules for ingest."""

from __future__ import annotations

import json
from pathlib import Path

from app.catalog.cleaning import (
    extract_snippets,
    make_id,
    merge_listings,
    merge_with_stats,
    parse_cost,
    parse_rating,
    parse_votes,
    parse_yes_no,
    split_list,
)
from app.catalog.models import Restaurant

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_listings.json"
PHONE_MARKER = "080 42297555"
MENU_MARKER = "Secret Paneer Platter"


def _listings() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _by_name(restaurants: list[Restaurant]) -> dict[str, Restaurant]:
    return {restaurant.name: restaurant for restaurant in restaurants}


def test_parse_rating_accepts_fraction_and_bare_numbers():
    assert parse_rating("4.1/5") == 4.1
    assert parse_rating("4.1 /5") == 4.1
    assert parse_rating(" 4.1/5 ") == 4.1
    assert parse_rating("0") == 0.0
    assert parse_rating(4) == 4.0
    assert parse_rating(5) == 5.0


def test_parse_rating_rejects_sentinels_and_out_of_range():
    assert parse_rating("NEW") is None
    assert parse_rating("new") is None
    assert parse_rating("-") is None
    assert parse_rating("") is None
    assert parse_rating(None) is None
    assert parse_rating("Excellent") is None
    assert parse_rating("-0.1") is None
    assert parse_rating("5.1") is None
    assert parse_rating("6/5") is None


def test_parse_cost_strips_commas_and_rejects_non_positive():
    assert parse_cost("800") == 800
    assert parse_cost("1,200") == 1200
    assert parse_cost("1, 200") == 1200
    assert parse_cost(800) == 800
    assert parse_cost("") is None
    assert parse_cost(None) is None
    assert parse_cost("cheap") is None
    assert parse_cost("800.5") is None
    assert parse_cost("0") is None
    assert parse_cost("-12") is None


def test_parse_votes_accepts_commas_and_defaults_missing_to_zero():
    assert parse_votes(775) == 775
    assert parse_votes("2,556") == 2556
    assert parse_votes(None) == 0
    assert parse_votes("") == 0
    assert parse_votes("many") == 0


def test_split_list_trims_drops_empties_and_keeps_first_seen():
    assert split_list(None) == []
    assert split_list("North Indian, Chinese,") == ["North Indian", "Chinese"]
    assert split_list(" North Indian , , Chinese ") == ["North Indian", "Chinese"]
    assert split_list("Italian, Cafe, Italian") == ["Italian", "Cafe"]


def test_parse_yes_no_is_case_insensitive():
    assert parse_yes_no("Yes") is True
    assert parse_yes_no(" yes ") is True
    assert parse_yes_no("YES") is True
    assert parse_yes_no("No") is False
    assert parse_yes_no("") is False
    assert parse_yes_no(None) is False


def test_extract_snippets_keeps_two_cleaned_bodies():
    raw = (
        "[('Rated 4.0', 'RATED\\n First review body.'), "
        "('Rated 5.0', 'RATED\\n Second review body.'), "
        "('Rated 3.0', 'RATED\\n Third should be ignored.')]"
    )
    snippets = extract_snippets(raw)
    assert snippets == ["First review body.", "Second review body."]
    assert all(len(snippet) <= 280 for snippet in snippets)


def test_extract_snippets_truncates_to_280_and_rejects_non_lists():
    long_body = "A" * 400
    raw = f"[('Rated 4.0', 'RATED\\n {long_body}')]"
    snippets = extract_snippets(raw)
    assert len(snippets) == 1
    assert len(snippets[0]) == 280
    assert extract_snippets("this is not a python list") == []
    assert extract_snippets(None) == []


def test_long_review_string_uses_bounded_scan(monkeypatch):
    import app.catalog.cleaning as cleaning

    def boom(_text: str):
        raise AssertionError("literal_eval should not parse long review strings")

    monkeypatch.setattr(cleaning.ast, "literal_eval", boom)
    padding = "x" * 100_001
    raw = (
        "[('Rated 4.0', 'RATED\\n First bounded review'), "
        "('Rated 5.0', 'RATED\\n Second bounded review'), "
        f"('Rated 1.0', 'RATED\\n {padding}')]"
    )
    assert len(raw) > 100_000
    assert extract_snippets(raw) == ["First bounded review", "Second bounded review"]


def test_make_id_is_stable_for_normalized_name_and_address():
    address = "942, 21st Main Road, 2nd Stage, Banashankari, Bangalore"
    first = make_id("Jalsa", address)
    second = make_id("  jalsa  ", address)
    assert first == second
    assert len(first) == 12


def test_duplicate_listings_merge_on_higher_votes_and_union_lists():
    restaurants = merge_listings(_listings())
    jalsa = _by_name(restaurants)["Jalsa"]

    assert jalsa.rating == 4.1
    assert jalsa.cost_for_two == 800
    assert jalsa.votes == 775
    assert jalsa.online_order is True
    assert jalsa.book_table is True
    assert jalsa.cuisines == ["North Indian", "Chinese", "Mughlai"]
    assert jalsa.listed_types == ["Buffet", "Delivery"]
    assert jalsa.dishes_liked == [
        "Pasta",
        "Lunch Buffet",
        "Masala Papad",
        "Dum Biryani",
        "Tomato Shorba",
    ]
    assert len(jalsa.review_snippets) == 2
    assert all(len(snippet) <= 280 for snippet in jalsa.review_snippets)
    assert jalsa.review_snippets[0].startswith("A beautiful place to dine in.")
    assert "Later listing review" not in " ".join(jalsa.review_snippets)


def test_id_is_stable_across_two_merges():
    rows = _listings()
    first = {item.name: item.id for item in merge_listings(rows)}
    second = {item.name: item.id for item in merge_listings(rows)}
    assert first == second
    jalsa_id = first["Jalsa"]
    jalsa_row = next(row for row in rows if row["name"] == "Jalsa")
    assert jalsa_id == make_id(jalsa_row["name"], jalsa_row["address"])


def test_blank_name_row_is_dropped():
    stats = merge_with_stats(_listings())
    names = {restaurant.name for restaurant in stats.restaurants}

    assert "" not in names
    assert all(restaurant.name.strip() for restaurant in stats.restaurants)
    assert stats.dropped == 1
    assert "Brand New Place" in names
    assert "Onesta" in names
    assert "Odd Reviews" in names


def test_new_rating_and_blank_cost_stay_null():
    restaurant = _by_name(merge_listings(_listings()))["Brand New Place"]
    assert restaurant.rating is None
    assert restaurant.cost_for_two is None
    assert restaurant.online_order is True


def test_comma_cost_and_votes_and_broken_encoding():
    restaurants = _by_name(merge_listings(_listings()))
    onesta = restaurants["Onesta"]
    assert onesta.cost_for_two == 1200
    assert onesta.votes == 2556

    cafe = next(item for item in restaurants.values() if "Down The Alley" in item.name)
    assert "Café" in cafe.name
    assert cafe.cost_for_two == 1200
    assert cafe.rating == 4.1


def test_merged_record_contains_no_phone_or_menu_text():
    jalsa = _by_name(merge_listings(_listings()))["Jalsa"]
    dumped = jalsa.model_dump()

    assert "phone" not in dumped
    assert "menu_item" not in dumped
    serialized = json.dumps(dumped)
    assert PHONE_MARKER not in serialized
    assert MENU_MARKER not in serialized
    assert "Hidden Biryani" not in serialized


def test_invalid_review_string_yields_empty_snippets():
    restaurant = _by_name(merge_listings(_listings()))["Odd Reviews"]
    assert restaurant.review_snippets == []
