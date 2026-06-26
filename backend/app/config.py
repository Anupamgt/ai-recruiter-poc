"""Application configuration loaded from environment variables / .env file."""

import logging
from functools import lru_cache

from google.genai import types
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Central configuration sourced from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Google AI ────────────────────────────────────────────────────────
    GOOGLE_API_KEY: str

    LLM_MODEL_ID: str = "gemini-3.1-pro-preview"
    EMBEDDING_MODEL_ID: str = "gemini-embedding-2"
    DEFAULT_THINKING_LEVEL: str = "LOW"

    # ── Qdrant ───────────────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "candidate_chunks"

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/recruiter.db"

    # ── File watcher ─────────────────────────────────────────────────────
    WATCH_DIR: str = "./data/sample_resumes"

    # ── CORS / server ────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # ── Embedding dimensions (verified at runtime) ──────────────────────
    EMBEDDING_DIMENSIONS: int = 3072


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()


def get_thinking_config(level: str | None = None) -> types.ThinkingConfig:
    """Return a ``ThinkingConfig`` for the requested level.

    Parameters
    ----------
    level:
        One of MINIMAL, LOW, MEDIUM, HIGH.  Falls back to the default
        configured in ``settings.DEFAULT_THINKING_LEVEL``.
    """
    resolved = (level or settings.DEFAULT_THINKING_LEVEL).upper()
    valid_levels = {"MINIMAL", "LOW", "MEDIUM", "HIGH"}
    if resolved not in valid_levels:
        logger.warning(
            "Invalid thinking level '%s', falling back to '%s'",
            resolved,
            settings.DEFAULT_THINKING_LEVEL,
        )
        resolved = settings.DEFAULT_THINKING_LEVEL.upper()
    return types.ThinkingConfig(thinking_level=resolved)
