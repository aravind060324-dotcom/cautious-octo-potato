"""Application settings loaded from the environment."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ALL_BANGALORE = "All Bangalore"

# Groq's OpenAI-compatible chat API. Phase 4 posts to ``{llm_base_url}/chat/completions``.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration. Ranking uses Groq. The API key stays empty until a live call."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = GROQ_BASE_URL
    llm_api_key: str = ""
    llm_model: str = GROQ_MODEL
    llm_timeout_seconds: float = Field(default=30, gt=0)
    catalog_path: Path = Path("data/processed/restaurants.parquet")
    max_candidates: int = Field(default=15, ge=1, le=30)
    default_limit: int = Field(default=5, ge=1, le=10)
    budget_low_max: int = Field(default=500, ge=1)
    budget_medium_max: int = Field(default=1000, ge=1)
    # Comma-separated browser origins (local Next + Vercel). Empty uses built-in defaults.
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,https://*.vercel.app"
    )

    def cors_origin_list(self) -> list[str]:
        """Exact origins for CORSMiddleware.allow_origins (no wildcards)."""
        origins: list[str] = []
        for part in self.cors_origins.split(","):
            origin = part.strip()
            if origin and "*" not in origin:
                origins.append(origin)
        return origins

    def cors_origin_regex(self) -> str | None:
        """Regex for preview/prod Vercel hosts when ``*.vercel.app`` is configured."""
        if "*.vercel.app" in self.cors_origins.replace(" ", ""):
            return r"https://.*\.vercel\.app"
        return None

    @field_validator("catalog_path", mode="after")
    @classmethod
    def resolve_catalog_path(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return (REPO_ROOT / value).resolve()

    def budget_bounds(self, band: str) -> tuple[int, int | None]:
        """Return ``(inclusive_lower, inclusive_upper)`` for a budget band.

        ``high`` has no upper bound, so its second value is ``None``.
        """
        if band == "low":
            return (1, self.budget_low_max)
        if band == "medium":
            return (self.budget_low_max + 1, self.budget_medium_max)
        if band == "high":
            return (self.budget_medium_max + 1, None)
        raise ValueError(f"Unknown budget band: {band}")
