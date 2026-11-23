"""HTTP handlers. Ranking stays in the recommendation service."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import (
    CuisinesResponse,
    HealthResponse,
    LocationsResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.catalog.models import Preferences
from app.catalog.store import CatalogStore
from app.config import ALL_BANGALORE
from app.recommender.service import RecommendationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    store = _store(request)
    return HealthResponse(status="ok", restaurants=len(store.restaurants))


@router.get("/api/locations", response_model=LocationsResponse)
def locations(request: Request) -> LocationsResponse:
    store = _store(request)
    names = [ALL_BANGALORE]
    names.extend(
        name for name in store.locations if name.casefold() != ALL_BANGALORE.casefold()
    )
    return LocationsResponse(locations=names)


@router.get("/api/cuisines", response_model=CuisinesResponse)
def cuisines(request: Request) -> CuisinesResponse:
    store = _store(request)
    return CuisinesResponse(
        cuisines=[{"name": item.name, "count": item.count} for item in store.cuisines if item.name.strip()]
    )


@router.post("/api/recommendations", response_model=RecommendationResponse)
def recommendations(body: RecommendationRequest, request: Request) -> RecommendationResponse:
    store, service, client = _runtime(request)
    if not _location_is_known(store, body.location):
        raise HTTPException(
            status_code=422,
            detail="location must be All Bangalore or a catalog neighborhood",
        )
    preferences = Preferences(
        location=body.location,
        budget=body.budget,
        cuisine=body.cuisine,
        min_rating=body.min_rating,
        preferences=body.preferences,
        limit=body.limit,
    )
    started = time.perf_counter()
    try:
        result = service.recommend(preferences, store, client)
    except Exception as exc:
        _log_recommendations(body, candidate_count=None, started=started)
        logger.exception("recommendation service failed")
        raise HTTPException(status_code=503, detail="Recommendations are unavailable.") from exc
    _log_recommendations(body, candidate_count=result.candidate_count, started=started)
    return RecommendationResponse.model_validate(asdict(result))


def _store(request: Request) -> CatalogStore:
    store = getattr(request.app.state, "store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="The catalog is unavailable.")
    return store


def _runtime(request: Request) -> tuple[CatalogStore, RecommendationService, object]:
    store = _store(request)
    service = getattr(request.app.state, "service", None)
    client = getattr(request.app.state, "client", None)
    if service is None or client is None:
        raise HTTPException(status_code=503, detail="Recommendations are unavailable.")
    return store, service, client


def _location_is_known(store: CatalogStore, location: str) -> bool:
    if location.casefold() == ALL_BANGALORE.casefold():
        return True
    folded = location.casefold()
    return any(name.casefold() == folded for name in store.locations)


def _log_recommendations(
    body: RecommendationRequest,
    *,
    candidate_count: int | None,
    started: float,
) -> None:
    wishes = body.preferences or ""
    digest = hashlib.sha256(wishes.encode("utf-8")).hexdigest()
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "recommendations location=%s candidate_count=%s latency_ms=%.0f preferences_len=%s preferences_sha256=%s",
        body.location,
        candidate_count,
        elapsed_ms,
        len(wishes),
        digest,
    )
