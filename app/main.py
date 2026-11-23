"""Restaurant recommendation API.

Startup loads the Parquet catalog. A missing or unreadable file is logged and
the process exits. Groq is used only when a recommendation request ranks matches.

Operator startup (from the repository root)::

    python -m venv .venv
    .venv\\Scripts\\Activate.ps1
    pip install -r requirements.txt
    python scripts/ingest.py
    uvicorn app.main:app --reload

Next.js UI (from ``web/``)::

    npm install
    npm run dev

Docker Compose (from repo root)::

    docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build

Free PaaS: Vercel (web/) + Railway (API). See docs/deploy-vercel-railway.md.

Place the model values in ``.env``::

    LLM_BASE_URL=
    LLM_API_KEY=
    LLM_MODEL=

After a fresh ingest, restart the API so it reloads the catalog.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.catalog.store import CatalogError, CatalogStore
from app.config import Settings
from app.recommender.llm import OpenAiCompatibleClient
from app.recommender.service import RecommendationService

logger = logging.getLogger(__name__)


def load_catalog(app: FastAPI) -> None:
    """Load the catalog, service, and Groq client. Exit if the file cannot be read."""
    settings = Settings()
    try:
        store = CatalogStore.load(settings.catalog_path, settings=settings)
    except CatalogError:
        logger.error("Catalog file cannot be loaded: %s", settings.catalog_path)
        raise SystemExit(1) from None
    if not store.restaurants:
        logger.error("Catalog file has no restaurants: %s", settings.catalog_path)
        raise SystemExit(1)
    app.state.settings = settings
    app.state.store = store
    app.state.service = RecommendationService()
    app.state.client = OpenAiCompatibleClient(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if getattr(app.state, "store", None) is None:
        load_catalog(app)
    else:
        if getattr(app.state, "service", None) is None:
            app.state.service = RecommendationService()
        if getattr(app.state, "client", None) is None:
            app.state.client = OpenAiCompatibleClient(getattr(app.state, "settings", None) or Settings())
    yield


app = FastAPI(title="Restaurant Recommendation API", lifespan=lifespan)

_cors_settings = Settings()
_cors_kwargs: dict[str, object] = {
    "allow_origins": _cors_settings.cors_origin_list(),
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
_cors_regex = _cors_settings.cors_origin_regex()
if _cors_regex:
    _cors_kwargs["allow_origin_regex"] = _cors_regex
app.add_middleware(CORSMiddleware, **_cors_kwargs)

app.include_router(router)
app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent / "ui", html=True),
    name="ui",
)


def main() -> None:
    """Used by a direct ``python -m app.main`` start. Uvicorn imports ``app`` itself."""
    import os

    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, factory=False)


if __name__ == "__main__":
    sys.exit(main())
