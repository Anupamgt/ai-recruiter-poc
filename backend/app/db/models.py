"""SQLAlchemy 2.0 ORM models for the AI Recruiter PoC."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all models."""

    type_annotation_map = {
        dict[str, Any]: JSON,
        list[Any]: JSON,
    }


class CandidateProfile(Base):
    """Represents a parsed candidate resume / CV."""

    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    raw_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | parsed | rejected
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    dedup_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    structured_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    behavioral_signals: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )

    # Relationships
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    ranking_results: Mapped[list["RankingResult"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """A text chunk extracted from a candidate's resume."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_profiles.id"), nullable=False, index=True
    )
    section_label: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )  # References Qdrant point ID
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )

    # Relationships
    candidate: Mapped["CandidateProfile"] = relationship(
        back_populates="chunks"
    )


class JDDecomposition(Base):
    """A parsed / decomposed job description."""

    __tablename__ = "jd_decompositions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    must_have: Mapped[Optional[list[Any]]] = mapped_column(
        JSON, nullable=True
    )
    nice_to_have: Mapped[Optional[list[Any]]] = mapped_column(
        JSON, nullable=True
    )
    implied_seniority: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )
    non_negotiables: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    flexibility_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    search_query_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )

    # Relationships
    ranking_results: Mapped[list["RankingResult"]] = relationship(
        back_populates="jd", cascade="all, delete-orphan"
    )


class RankingResult(Base):
    """Stores per-candidate ranking output for a given JD."""

    __tablename__ = "ranking_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    jd_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jd_decompositions.id"), nullable=False, index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_profiles.id"), nullable=False, index=True
    )
    dense_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sparse_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fused_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stage_a_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stage_b_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stage_b_fit_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_flags: Mapped[Optional[list[Any]]] = mapped_column(
        JSON, nullable=True
    )
    confidence: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium"
    )  # low | medium | high
    feedback: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 1 or -1
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )

    # Relationships
    jd: Mapped["JDDecomposition"] = relationship(back_populates="ranking_results")
    candidate: Mapped["CandidateProfile"] = relationship(
        back_populates="ranking_results"
    )
