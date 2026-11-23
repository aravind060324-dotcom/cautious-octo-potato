"""Run Phase 7 API verification checks against the real Parquet catalog.

Usage (from the repository root):

    python scripts/verify_phase7.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from app.catalog.models import Preferences
from app.catalog.store import CatalogStore
from app.config import Settings
from app.main import app
from app.recommender.llm import LlmError
from app.recommender.service import RecommendationService


class RecordingClient:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _clear_state() -> None:
    for name in ("store", "service", "client", "settings"):
        if hasattr(app.state, name):
            delattr(app.state, name)


def main() -> int:
    settings = Settings(_env_file=None)
    if not settings.catalog_path.is_file():
        print(f"FAIL: catalog missing at {settings.catalog_path}")
        return 1

    store = CatalogStore.load(settings.catalog_path, settings=settings)
    print(f"loaded restaurants: {len(store.restaurants)}")
    if len(store.restaurants) <= 0 or len(store.restaurants) >= 51_717:
        print("FAIL: unique restaurant count out of expected range")
        return 1

    fake_payload = {
        "summary": "Top matches for Banashankari Italian.",
        "recommendations": [],
    }
    client = RecordingClient(json.dumps(fake_payload))
    _clear_state()
    app.state.settings = settings
    app.state.store = store
    app.state.service = RecommendationService()
    app.state.client = client

    failures: list[str] = []

    with TestClient(app) as api:
        health = api.get("/api/health")
        body = health.json()
        if health.status_code != 200 or body.get("status") != "ok" or body.get("restaurants", 0) <= 0:
            failures.append(f"health: {health.status_code} {body}")
        else:
            print(f"health ok: {body}")

        # Location filter
        client.calls = 0
        location_resp = api.post(
            "/api/recommendations",
            json={"location": "Banashankari", "limit": 10},
        )
        location_body = location_resp.json()
        if location_resp.status_code != 200:
            failures.append(f"location status: {location_resp.status_code}")
        elif not location_body["recommendations"]:
            failures.append("location: expected some recommendations")
        elif any(card["location"] != "Banashankari" for card in location_body["recommendations"]):
            failures.append("location: non-Banashankari card returned")
        else:
            print(f"location filter ok: {len(location_body['recommendations'])} cards")

        # Cuisine and budget
        client.response = json.dumps(
            {
                "summary": "Italian medium budget picks.",
                "recommendations": [],
            }
        )
        client.calls = 0
        cuisine_resp = api.post(
            "/api/recommendations",
            json={
                "location": "Banashankari",
                "cuisine": "Italian",
                "budget": "medium",
                "limit": 10,
            },
        )
        cuisine_body = cuisine_resp.json()
        if cuisine_resp.status_code != 200:
            failures.append(f"cuisine/budget status: {cuisine_resp.status_code}")
        else:
            cards = cuisine_body["recommendations"]
            bad_cuisine = [
                card
                for card in cards
                if not any("italian" in token.casefold() for token in card["cuisines"])
            ]
            bad_cost = [
                card
                for card in cards
                if card["cost_for_two"] is not None
                and not (501 <= card["cost_for_two"] <= 1000)
            ]
            if bad_cuisine or bad_cost:
                failures.append(f"cuisine/budget: bad_cuisine={bad_cuisine} bad_cost={bad_cost}")
            else:
                print(f"cuisine/budget ok: {len(cards)} cards")

        # Minimum rating
        client.calls = 0
        rating_resp = api.post(
            "/api/recommendations",
            json={
                "location": "Banashankari",
                "cuisine": "Italian",
                "budget": "medium",
                "min_rating": 4,
                "limit": 10,
            },
        )
        rating_body = rating_resp.json()
        if rating_resp.status_code != 200:
            failures.append(f"min_rating status: {rating_resp.status_code}")
        else:
            cards = rating_body["recommendations"]
            bad_rating = [
                card
                for card in cards
                if card["rating"] is not None and card["rating"] < 4
            ]
            if bad_rating:
                failures.append(f"min_rating: {bad_rating}")
            else:
                print(f"min_rating ok: {len(cards)} cards")

            # Model contract vs CatalogStore.filter
            prefs = Preferences(
                location="Banashankari",
                cuisine="Italian",
                budget="medium",
                min_rating=4,
                limit=10,
            )
            filtered = store.filter(prefs)
            by_id = {row.id: row for row in filtered.restaurants}
            for card in cards:
                row = by_id.get(card["id"])
                if row is None:
                    failures.append(f"model contract: unknown id {card['id']}")
                    continue
                if card["name"] != row.name or card["rating"] != row.rating or card["cost_for_two"] != row.cost_for_two:
                    failures.append(f"model contract: fact mismatch for {card['id']}")
            if not any(item.startswith("model contract") for item in failures):
                print(f"model contract ok: {len(cards)} cards match catalog")

        # Empty filters — find a zero-match preference set
        empty_payload = {
            "location": "Banashankari",
            "cuisine": "zzzz-no-such-cuisine",
            "budget": "high",
            "min_rating": 5,
            "limit": 5,
        }
        client.calls = 0
        empty_resp = api.post("/api/recommendations", json=empty_payload)
        empty_body = empty_resp.json()
        if empty_resp.status_code != 200:
            failures.append(f"empty status: {empty_resp.status_code}")
        elif empty_body["recommendations"] or empty_body["candidate_count"] != 0:
            failures.append(f"empty: unexpected body {empty_body}")
        elif client.calls != 0:
            failures.append(f"empty: model was called {client.calls} times")
        else:
            print("empty filters ok: 200, no cards, no model call")

        # Fallback when the model fails
        fail_client = RecordingClient(LlmError("unreachable"))
        app.state.client = fail_client
        fallback_resp = api.post(
            "/api/recommendations",
            json={"location": "Banashankari", "limit": 5},
        )
        fallback_body = fallback_resp.json()
        cards = fallback_body.get("recommendations", [])
        if fallback_resp.status_code != 200:
            failures.append(f"fallback status: {fallback_resp.status_code}")
        elif not cards:
            failures.append("fallback: expected catalog cards")
        elif fallback_body.get("explanations_available") is not False:
            failures.append("fallback: explanations_available should be false")
        elif any(card.get("explanation") for card in cards):
            failures.append("fallback: explanations should be empty")
        else:
            ratings = [card["rating"] if card["rating"] is not None else -1 for card in cards]
            if ratings != sorted(ratings, reverse=True):
                failures.append(f"fallback: not rating order {ratings}")
            else:
                print(f"fallback ok: {len(cards)} cards, explanations unavailable")

    _clear_state()

    if failures:
        print("FAIL:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("Phase 7 API verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
