"""Settings and startup checks for the Phase 1 foundation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import GROQ_BASE_URL, GROQ_MODEL, REPO_ROOT, Settings
from app.main import app

_SETTING_ENV_VARS = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "CATALOG_PATH",
    "MAX_CANDIDATES",
    "DEFAULT_LIMIT",
    "BUDGET_LOW_MAX",
    "BUDGET_MEDIUM_MAX",
    "CORS_ORIGINS",
)


@pytest.fixture
def settings_env(monkeypatch):
    for name in _SETTING_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _settings() -> Settings:
    return Settings(_env_file=None)


def test_default_budget_bands(settings_env):
    settings = _settings()

    assert settings.budget_bounds("low") == (1, 500)
    assert settings.budget_bounds("medium") == (501, 1000)
    high_lower, high_upper = settings.budget_bounds("high")
    assert high_lower == 1001
    assert high_upper is None


def test_unknown_budget_band_raises(settings_env):
    settings = _settings()

    with pytest.raises(ValueError, match="Unknown budget band"):
        settings.budget_bounds("cheap")


def test_max_candidates_reads_environment_override(settings_env):
    settings_env.setenv("MAX_CANDIDATES", "20")

    settings = _settings()

    assert settings.max_candidates == 20


def test_catalog_path_resolves_from_repository_root(settings_env):
    settings = _settings()

    assert settings.catalog_path == (REPO_ROOT / "data" / "processed" / "restaurants.parquet").resolve()
    assert settings.catalog_path.is_absolute()


def test_relative_catalog_path_override_stays_under_repository_root(settings_env):
    settings_env.setenv("CATALOG_PATH", "custom/restaurants.parquet")

    settings = _settings()

    assert settings.catalog_path == (REPO_ROOT / "custom" / "restaurants.parquet").resolve()


def test_absolute_catalog_path_is_preserved(settings_env, tmp_path: Path):
    catalog = tmp_path / "restaurants.parquet"
    settings_env.setenv("CATALOG_PATH", str(catalog))

    settings = _settings()

    assert settings.catalog_path == catalog.resolve()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MAX_CANDIDATES", "0"),
        ("MAX_CANDIDATES", "31"),
        ("DEFAULT_LIMIT", "0"),
        ("DEFAULT_LIMIT", "11"),
        ("LLM_TIMEOUT_SECONDS", "0"),
        ("LLM_TIMEOUT_SECONDS", "-1"),
    ],
)
def test_out_of_range_settings_are_rejected(settings_env, name, value):
    settings_env.setenv(name, value)

    with pytest.raises(ValidationError):
        _settings()


def test_model_credentials_default_to_groq_without_a_key(settings_env):
    settings = _settings()

    assert settings.llm_base_url == GROQ_BASE_URL
    assert settings.llm_api_key == ""
    assert settings.llm_model == GROQ_MODEL
    assert settings.llm_timeout_seconds == 30
    assert settings.default_limit == 5


def test_app_imports_without_loading_the_catalog():
    """Startup reads the Parquet file. Importing the module must not."""
    assert app.title == "Restaurant Recommendation API"


def test_cors_origins_split_exact_hosts_and_vercel_regex(settings_env):
    settings = _settings()

    assert "http://localhost:3000" in settings.cors_origin_list()
    assert all("*" not in origin for origin in settings.cors_origin_list())
    assert settings.cors_origin_regex() == r"https://.*\.vercel\.app"


def test_cors_origins_env_override(settings_env):
    settings_env.setenv(
        "CORS_ORIGINS",
        "https://bangalore-bites.vercel.app,http://localhost:3000",
    )

    settings = _settings()

    assert settings.cors_origin_list() == [
        "https://bangalore-bites.vercel.app",
        "http://localhost:3000",
    ]
    assert settings.cors_origin_regex() is None
