"""CV ingestion pipeline: dedup → parse → chunk → features → embed → store."""
import logging
import os
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateProfile, Chunk
from app.ingestion.dedup import compute_hash, check_duplicate
from app.parsing.pdf_parser import parse_file, parse_bytes
from app.parsing.chunker import chunk_resume
from app.parsing.feature_extractor import extract_features
from app.signals.behavioral_signals import extract_behavioral_signals
from app.embeddings.gemini_embedder import embed_texts
from app.retrieval.vector_store import upsert_chunks

logger = logging.getLogger(__name__)


async def process_cv(
    file_path: str | None = None,
    file_bytes: bytes | None = None,
    filename: str = "unknown.pdf",
    db: AsyncSession | None = None,
) -> CandidateProfile:
    """Process a CV file through the full ingestion pipeline.
    
    Accepts either a file_path (for watcher-triggered ingestion)
    or file_bytes + filename (for API upload).
    
    Pipeline:
    1. Dedup check (SHA-256 hash)
    2. Parse PDF/TXT to raw text
    3. Section-aware chunking
    4. Feature extraction (domain years, education, certs, location)
    5. Behavioral signal extraction (P0 stub)
    6. Embed chunks via Gemini
    7. Store in Qdrant (vectors) + SQLite (metadata)
    
    Returns: Created CandidateProfile
    Raises: ValueError for duplicates, RuntimeError for processing errors
    """
    from app.db.session import async_session
    
    own_session = db is None
    if own_session:
        session = async_session()
    else:
        session = db
    
    candidate_id = str(uuid.uuid4())
    source_path = file_path or filename
    
    try:
        # ── Step 1: Read file bytes ──────────────────────────────
        if file_bytes is None:
            if file_path is None:
                raise ValueError("Either file_path or file_bytes must be provided")
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
        
        # ── Step 2: Dedup check ──────────────────────────────────
        file_hash = compute_hash(file_bytes)
        is_dup, existing_id = await check_duplicate(file_hash, session)
        if is_dup:
            logger.info(
                "Duplicate CV detected: '%s' matches existing candidate %s",
                filename, existing_id,
            )
            raise ValueError(f"Duplicate CV. Matches existing candidate: {existing_id}")
        
        # ── Step 3: Parse text ───────────────────────────────────
        logger.info("Parsing CV: %s", filename)
        if file_path:
            raw_text = parse_file(file_path)
        else:
            raw_text = parse_bytes(file_bytes, filename)
        
        if not raw_text or len(raw_text.strip()) < 30:
            # Create rejected profile
            profile = CandidateProfile(
                id=candidate_id,
                raw_file_path=source_path,
                status="rejected",
                rejection_reason="Insufficient text extracted from file",
                dedup_hash=file_hash,
            )
            session.add(profile)
            if own_session:
                await session.commit()
            logger.warning("CV rejected (too little text): %s", filename)
            return profile
        
        # ── Step 4: Chunk ────────────────────────────────────────
        chunks = chunk_resume(raw_text)
        if not chunks:
            profile = CandidateProfile(
                id=candidate_id,
                raw_file_path=source_path,
                status="rejected",
                rejection_reason="No meaningful chunks could be extracted",
                dedup_hash=file_hash,
            )
            session.add(profile)
            if own_session:
                await session.commit()
            logger.warning("CV rejected (no chunks): %s", filename)
            return profile
        
        # ── Step 5: Extract features ─────────────────────────────
        metadata = extract_features(raw_text)
        
        # ── Step 6: Extract behavioral signals ───────────────────
        signals = extract_behavioral_signals(raw_text, chunks)
        
        # ── Step 7: Embed chunks ─────────────────────────────────
        chunk_texts = [c['text'] for c in chunks]
        logger.info("Embedding %d chunks...", len(chunk_texts))
        embeddings = await embed_texts(chunk_texts, task_type="RETRIEVAL_DOCUMENT")
        
        # ── Step 8: Create DB records ────────────────────────────
        profile = CandidateProfile(
            id=candidate_id,
            raw_file_path=source_path,
            status="parsed",
            dedup_hash=file_hash,
            structured_metadata=metadata,
            behavioral_signals=signals,
        )
        session.add(profile)
        
        # Create chunk records and prepare Qdrant data
        qdrant_chunks = []
        for i, (chunk_data, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = str(uuid.uuid4())
            
            db_chunk = Chunk(
                id=chunk_id,
                candidate_id=candidate_id,
                section_label=chunk_data['section_label'],
                text=chunk_data['text'],
                embedding_id=chunk_id,  # Same ID used in Qdrant
            )
            session.add(db_chunk)
            
            qdrant_chunks.append({
                'chunk_id': chunk_id,
                'text': chunk_data['text'],
                'section_label': chunk_data['section_label'],
                'embedding': embedding,
            })
        
        # ── Step 9: Store in Qdrant ──────────────────────────────
        upsert_chunks(candidate_id, qdrant_chunks)
        
        # ── Step 10: Commit DB ───────────────────────────────────
        if own_session:
            await session.commit()
            await session.refresh(profile)
        
        logger.info(
            "Successfully processed CV '%s' → candidate %s (%d chunks)",
            filename, candidate_id, len(chunks),
        )
        
        return profile
        
    except ValueError:
        if own_session:
            await session.rollback()
        raise
    except Exception as e:
        if own_session:
            await session.rollback()
        logger.error("Pipeline failed for '%s': %s", filename, e)
        
        # Try to create a rejected profile
        try:
            profile = CandidateProfile(
                id=candidate_id,
                raw_file_path=source_path,
                status="rejected",
                rejection_reason=f"Processing error: {str(e)}",
                dedup_hash=compute_hash(file_bytes) if file_bytes else None,
            )
            session.add(profile)
            if own_session:
                await session.commit()
        except Exception:
            pass
        
        raise RuntimeError(f"CV processing failed: {e}") from e
    finally:
        if own_session:
            await session.close()
