"""HTTP API. The model client is a fake, and the catalog is the Phase 3 fixture."""

from __future__ import annotations

import hashlib
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.catalog.store import CatalogStore
from app.main import app, load_catalog
from app.recommender.llm import LlmError
from app.recommender.service import EMPTY_SUMMARY, FALLBACK_SUMMARY, RecommendationService
from tests.test_filters import _sample_restaurants


class FakeClient:
    def __init__(self, response: str | Exception | None = None) -> None:
        self.response: str | Exception = response or json.dumps(
            {"summary": "Listed.", "recommendations": []}
        )
        self.calls = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _clear_app_state() -> None:
    for name in ("store", "service", "client", "settings"):
        if hasattr(app.state, name):
            delattr(app.state, name)


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def api(fake_client: FakeClient):
    _clear_app_state()
    app.state.store = CatalogStore(_sample_restaurants())
    app.state.service = RecommendationService()
    app.state.client = fake_client
    with TestClient(app) as client:
        yield client
    _clear_app_state()


def test_homepage_serves_the_form(api: TestClient):
    response = api.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    page = response.text
    assert 'id="location"' in page
    assert 'for="budget"' in page
    assert "/app.js" in page
    assert "/styles.css" in page


def test_health_reports_the_fixture_count(api: TestClient):
    response = api.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "restaurants": 8}


def test_locations_begin_with_all_bangalore(api: TestClient):
    response = api.get("/api/locations")

    assert response.status_code == 200
    locations = response.json()["locations"]
    assert locations[0] == "All Bangalore"
    assert locations.count("All Bangalore") == 1
    assert locations[1:] == sorted(locations[1:])
    assert "Banashankari" in locations
    assert "Jayanagar" in locations


def test_cuisines_are_named_counts_most_common_first(api: TestClient):
    response = api.get("/api/cuisines")

    assert response.status_code == 200
    cuisines = response.json()["cuisines"]
    assert cuisines[0] == {"name": "Italian", "count": 4}
    counts = [item["count"] for item in cuisines]
    assert counts == sorted(counts, reverse=True)
    assert all(item["name"].strip() for item in cuisines)


def test_unknown_location_is_422_and_does_not_call_the_model(api: TestClient, fake_client: FakeClient):
    response = api.post("/api/recommendations", json={"location": "Mysore", "cuisine": "Italian"})

    assert response.status_code == 422
    assert fake_client.calls == 0


def test_rating_above_five_is_422(api: TestClient, fake_client: FakeClient):
    response = api.post(
        "/api/recommendations",
        json={"location": "Banashankari", "min_rating": 6},
    )

    assert response.status_code == 422
    assert fake_client.calls == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"budget": "medium"},
        {"location": "Banashankari", "budget": "Low"},
        {"location": "Banashankari", "budget": "cheap"},
        {"location": "Banashankari", "budget": ""},
        {"location": "Banashankari", "min_rating": -0.1},
        {"location": "Banashankari", "preferences": "x" * 501},
        {"location": "Banashankari", "limit": 0},
        {"location": "Banashankari", "limit": 11},
    ],
)
def test_invalid_bodies_are_422(api: TestClient, fake_client: FakeClient, payload: dict):
    response = api.post("/api/recommendations", json=payload)

    assert response.status_code == 422
    assert fake_client.calls == 0


def test_no_matches_returns_an_empty_200_without_calling_the_model(
    api: TestClient, fake_client: FakeClient
):
    response = api.post(
        "/api/recommendations",
        json={"location": "Banashankari", "cuisine": "Ethiopian"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "summary": EMPTY_SUMMARY,
        "applied_filters": {"location": "Banashankari", "cuisine": "Ethiopian"},
        "candidate_count": 0,
        "explanations_available": False,
        "recommendations": [],
    }
    assert fake_client.calls == 0


def test_matching_request_keeps_catalog_facts_in_model_order(api: TestClient, fake_client: FakeClient):
    fake_client.response = json.dumps(
        {
            "summary": "Two Italian places.",
            "recommendations": [
                {"id": "mix", "rank": 1, "explanation": "Cafe setting."},
                {"id": "it-bana", "rank": 2, "explanation": "Pizza and pasta."},
            ],
        }
    )
    response = api.post(
        "/api/recommendations",
        json={
            "location": "banashankari",
            "cuisine": "Italian",
            "budget": "medium",
            "min_rating": 4,
            "preferences": "family-friendly",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [card["id"] for card in body["recommendations"]] == ["mix", "it-bana"]
    assert [card["rating"] for card in body["recommendations"]] == [4.1, 4.6]
    assert [card["cost_for_two"] for card in body["recommendations"]] == [800, 600]
    assert body["recommendations"][0]["name"] == "Cafe Mex"
    assert body["recommendations"][1]["name"] == "Onesta"
    assert body["recommendations"][0]["explanation"] == "Cafe setting."
    assert body["explanations_available"] is True
    assert fake_client.calls == 1


def test_model_error_returns_catalog_order_with_empty_explanations(
    api: TestClient, fake_client: FakeClient
):
    fake_client.response = LlmError("Model request timed out")
    response = api.post("/api/recommendations", json={"location": "Banashankari", "limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == FALLBACK_SUMMARY
    assert body["explanations_available"] is False
    assert [card["id"] for card in body["recommendations"]] == ["hi-1", "hi-2"]
    assert [card["explanation"] for card in body["recommendations"]] == ["", ""]
    assert [card["rating"] for card in body["recommendations"]] == [4.9, 4.8]


def test_recommendation_log_records_a_hash_instead_of_the_wishes(
    api: TestClient, fake_client: FakeClient, caplog: pytest.LogCaptureFixture
):
    wishes = "family-friendly secret wish"
    fake_client.response = json.dumps(
        {
            "summary": "One place.",
            "recommendations": [{"id": "hi-1", "rank": 1, "explanation": "Top rated."}],
        }
    )
    with caplog.at_level(logging.INFO, logger="app.api.routes"):
        response = api.post(
            "/api/recommendations",
            json={"location": "Banashankari", "preferences": wishes, "limit": 1},
        )

    assert response.status_code == 200
    assert wishes not in caplog.text
    assert "location=Banashankari" in caplog.text
    assert "candidate_count=" in caplog.text
    assert "latency_ms=" in caplog.text
    assert f"preferences_len={len(wishes)}" in caplog.text
    assert hashlib.sha256(wishes.encode("utf-8")).hexdigest() in caplog.text


def test_startup_exits_when_the_catalog_file_is_missing(monkeypatch, tmp_path, caplog):
    missing = tmp_path / "missing.parquet"
    monkeypatch.setenv("CATALOG_PATH", str(missing))
    _clear_app_state()
    with caplog.at_level(logging.ERROR, logger="app.main"):
        with pytest.raises(SystemExit) as caught:
            load_catalog(app)

    assert caught.value.code == 1
    assert str(missing) in caplog.text
    _clear_app_state()


def test_load_catalog_rejects_an_unreadable_file(monkeypatch, tmp_path, caplog):
    broken = tmp_path / "restaurants.parquet"
    broken.write_text("not parquet", encoding="utf-8")
    monkeypatch.setenv("CATALOG_PATH", str(broken))
    _clear_app_state()
    with caplog.at_level(logging.ERROR, logger="app.main"):
        with pytest.raises(SystemExit) as caught:
            load_catalog(app)

    assert caught.value.code == 1
    assert str(broken) in caplog.text
    _clear_app_state()
