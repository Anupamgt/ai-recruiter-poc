"""Async database engine, session factory, and dependency injection helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

# ── Engine & session factory ────────────────────────────────────────────────
# For SQLite we need check_same_thread=False because async drivers use
# multiple threads internally.
_connect_args: dict = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables if they don't already exist."""
    # Ensure the directory for the SQLite file exists
    if settings.DATABASE_URL.startswith("sqlite"):
        db_path_str = settings.DATABASE_URL.split("///")[-1]
        db_dir = Path(db_path_str).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info("SQLite database directory ensured: %s", db_dir)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created / verified.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async session and commits/rollbacks."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
