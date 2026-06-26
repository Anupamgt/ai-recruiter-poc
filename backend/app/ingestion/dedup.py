"""Deduplication via SHA-256 hash of raw file bytes."""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateProfile

logger = logging.getLogger(__name__)


def compute_hash(file_bytes: bytes) -> str:
    """Return the hex SHA-256 digest for the given bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


async def check_duplicate(
    file_bytes: bytes,
    db_session: AsyncSession,
) -> tuple[bool, str | None]:
    """Check whether a file with the same content already exists.

    Returns
    -------
    (is_duplicate, existing_candidate_id)
        ``True`` and the existing ``CandidateProfile.id`` if a duplicate is
        found, otherwise ``(False, None)``.
    """
    file_hash = compute_hash(file_bytes)
    stmt = select(CandidateProfile).where(CandidateProfile.dedup_hash == file_hash)
    result = await db_session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        logger.info(
            "Duplicate detected — hash %s already belongs to candidate %s",
            file_hash,
            existing.id,
        )
        return True, existing.id

    return False, None
