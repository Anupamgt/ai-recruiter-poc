"""FastAPI API routes for the AI Recruiter PoC."""
import logging
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateProfile, Chunk, JDDecomposition, RankingResult
from app.db.session import get_db
from app.ingestion.pipeline import process_cv
from app.embeddings.gemini_embedder import embed_query
from app.retrieval.vector_store import search_dense
from app.ranking.stage_a_reranker import rerank_stage_a

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# Request / Response Models
# ═══════════════════════════════════════════════════════════

class JDCreateRequest(BaseModel):
    text: str = Field(..., min_length=50, description="Job description text")


class JDCreateResponse(BaseModel):
    jd_id: str
    raw_text: str


class FeedbackRequest(BaseModel):
    jd_id: str
    candidate_id: str
    signal: Literal[1, -1]


class CandidateChunkResponse(BaseModel):
    id: str
    section_label: str | None
    text: str


class CandidateResponse(BaseModel):
    id: str
    raw_file_path: str
    status: str
    rejection_reason: str | None = None
    structured_metadata: dict[str, Any] | None = None
    behavioral_signals: dict[str, Any] | None = None
    chunks: list[CandidateChunkResponse] = []
    created_at: str


class CVUploadResponse(BaseModel):
    candidate_id: str
    status: str
    filename: str
    rejection_reason: str | None = None
    num_chunks: int = 0


class ShortlistCandidate(BaseModel):
    candidate_id: str
    rank: int
    stage_a_score: float
    dense_score: float
    confidence: str
    metadata: dict[str, Any] = {}
    name: str = "Candidate"  # Derived from file path or metadata


class ShortlistResponse(BaseModel):
    jd_id: str
    jd_summary: str
    stage: str = "A"
    candidates: list[ShortlistCandidate]
    total_pool_size: int


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"


# ═══════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse()


@router.post("/cv", response_model=CVUploadResponse)
async def upload_cv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a CV file for processing.
    
    Accepts PDF and TXT files. Triggers the full ingestion pipeline:
    dedup → parse → chunk → embed → store.
    """
    if not file.filename:
        raise HTTPException(400, "Filename is required")
    
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ('pdf', 'txt'):
        raise HTTPException(400, f"Unsupported file type: .{ext}. Use .pdf or .txt")
    
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(400, "Empty file")
    
    try:
        profile = await process_cv(
            file_bytes=file_bytes,
            filename=file.filename,
            db=db,
        )
        await db.commit()
        
        # Count chunks
        chunk_count = 0
        if profile.status == "parsed":
            result = await db.execute(
                select(Chunk).where(Chunk.candidate_id == profile.id)
            )
            chunk_count = len(result.scalars().all())
        
        return CVUploadResponse(
            candidate_id=profile.id,
            status=profile.status,
            filename=file.filename,
            rejection_reason=profile.rejection_reason,
            num_chunks=chunk_count,
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        logger.error("CV upload failed: %s", e)
        raise HTTPException(500, f"Processing error: {str(e)}")


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full candidate profile with chunks."""
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, f"Candidate {candidate_id} not found")
    
    # Fetch chunks
    chunks_result = await db.execute(
        select(Chunk).where(Chunk.candidate_id == candidate_id)
    )
    chunks = chunks_result.scalars().all()
    
    return CandidateResponse(
        id=profile.id,
        raw_file_path=profile.raw_file_path,
        status=profile.status,
        rejection_reason=profile.rejection_reason,
        structured_metadata=profile.structured_metadata,
        behavioral_signals=profile.behavioral_signals,
        chunks=[
            CandidateChunkResponse(
                id=c.id,
                section_label=c.section_label,
                text=c.text,
            )
            for c in chunks
        ],
        created_at=profile.created_at.isoformat() if profile.created_at else "",
    )


@router.post("/jd", response_model=JDCreateResponse)
async def create_jd(
    request: JDCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Upload a job description for candidate matching.
    
    P1: Runs JD Decomposition Agent for structured analysis.
    """
    jd_id = str(uuid.uuid4())
    
    # Run JD Decomposition Agent
    from app.ranking.jd_decomposer import decompose_jd
    decomp = decompose_jd(request.text)
    
    jd = JDDecomposition(
        id=jd_id,
        raw_text=request.text,
        must_have=decomp.must_have,
        nice_to_have=decomp.nice_to_have,
        implied_seniority=decomp.implied_seniority,
        non_negotiables=decomp.non_negotiables,
        flexibility_notes=decomp.flexibility_notes,
        search_query_text=decomp.search_query_text,
    )
    
    db.add(jd)
    await db.commit()
    
    logger.info("Created & Decomposed JD %s (%d chars)", jd_id, len(request.text))
    
    return JDCreateResponse(jd_id=jd_id, raw_text=request.text)


@router.get("/jd/{jd_id}/shortlist", response_model=ShortlistResponse)
async def get_shortlist(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get ranked candidate shortlist for a job description.
    
    Runs the full Stage A pipeline:
    1. Embed JD text
    2. Dense vector search (top-20)
    3. Stage A weighted re-ranking
    4. Return top-10 with scores
    """
    # Fetch JD
    result = await db.execute(
        select(JDDecomposition).where(JDDecomposition.id == jd_id)
    )
    jd = result.scalar_one_or_none()
    if not jd:
        raise HTTPException(404, f"JD {jd_id} not found")
    
    # Use search_query_text (P1: decomposed search query)
    query_text = jd.search_query_text or jd.raw_text
    
    # Embed JD query
    try:
        query_embedding = await embed_query(query_text)
    except Exception as e:
        logger.error("Failed to embed JD: %s", e)
        raise HTTPException(500, f"Embedding error: {str(e)}")
    
    # Dense search
    retrieval_results = search_dense(query_embedding, limit=20)
    
    if not retrieval_results:
        return ShortlistResponse(
            jd_id=jd_id,
            jd_summary=query_text[:200] + "..." if len(query_text) > 200 else query_text,
            stage="A",
            candidates=[],
            total_pool_size=0,
        )
    
    # Fetch candidate metadata for re-ranking
    candidate_ids = list({r['candidate_id'] for r in retrieval_results})
    candidates_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.id.in_(candidate_ids))
    )
    candidates = candidates_result.scalars().all()
    
    candidate_metadata = {}
    for c in candidates:
        meta = c.structured_metadata or {}
        if c.behavioral_signals:
            meta['_behavioral_signals'] = c.behavioral_signals
        candidate_metadata[c.id] = meta
    
    # Stage A re-rank
    # Extract JD requirements for matching
    jd_requirements = {
        'domain_years': jd.non_negotiables.get('min_years') if jd.non_negotiables and isinstance(jd.non_negotiables, dict) else None,
        'education_level': jd.non_negotiables.get('degree') if jd.non_negotiables and isinstance(jd.non_negotiables, dict) else None,
    }
    
    ranked = rerank_stage_a(
        retrieval_results=retrieval_results,
        candidate_metadata=candidate_metadata,
        jd_requirements=jd_requirements,
        top_k=10,
    )
    
    # Store ranking results
    for i, r in enumerate(ranked):
        ranking = RankingResult(
            jd_id=jd_id,
            candidate_id=r['candidate_id'],
            dense_score=r['dense_score'],
            sparse_score=0.0,  # P1: hybrid retrieval
            fused_score=r['dense_score'],  # P0: dense only
            stage_a_score=r['stage_a_score'],
            confidence=r['confidence'],
        )
        db.add(ranking)
    
    await db.commit()
    
    # Build response
    # Map candidate_id to file path for display name
    candidate_names = {}
    for c in candidates:
        import os
        name = os.path.splitext(os.path.basename(c.raw_file_path))[0]
        # Clean up filename to a display name
        name = name.replace('_', ' ').replace('-', ' ').title()
        candidate_names[c.id] = name
    
    shortlist_candidates = []
    for i, r in enumerate(ranked):
        shortlist_candidates.append(
            ShortlistCandidate(
                candidate_id=r['candidate_id'],
                rank=i + 1,
                stage_a_score=r['stage_a_score'],
                dense_score=r['dense_score'],
                confidence=r['confidence'],
                metadata=r.get('metadata', {}),
                name=candidate_names.get(r['candidate_id'], f"Candidate {i+1}"),
            )
        )
    
    return ShortlistResponse(
        jd_id=jd_id,
        jd_summary=query_text[:200] + "..." if len(query_text) > 200 else query_text,
        stage="A",
        candidates=shortlist_candidates,
        total_pool_size=len(candidate_ids),
    )


@router.get("/jd/{jd_id}/shortlist/stream")
async def get_shortlist_stream(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming endpoint for progressive Stage A → Stage B shortlist."""
    from sse_starlette.sse import EventSourceResponse
    import json as json_mod
    from app.ranking.stage_b_llm_judge import evaluate_candidate

    # Fetch shortlist (runs Stage A)
    shortlist_resp = await get_shortlist(jd_id, db)
    
    # Fetch JD text
    jd_res = await db.execute(select(JDDecomposition).where(JDDecomposition.id == jd_id))
    jd_obj = jd_res.scalar_one_or_none()
    jd_text = jd_obj.raw_text if jd_obj else ""

    async def event_generator():
        # 1. Yield Stage A results immediately
        yield {
            "event": "stage_a",
            "data": shortlist_resp.model_dump_json()
        }

        # 2. Progressively evaluate top candidates in Stage B
        candidates = shortlist_resp.candidates
        for cand in candidates:
            cid = cand.candidate_id
            
            # Fetch profile text and signals
            cand_res = await db.execute(select(CandidateProfile).where(CandidateProfile.id == cid))
            cand_obj = cand_res.scalar_one_or_none()
            
            # Fetch chunks text
            chunk_res = await db.execute(select(Chunk).where(Chunk.candidate_id == cid))
            chunks = chunk_res.scalars().all()
            resume_text = "\n".join([c.text for c in chunks])

            meta = cand_obj.structured_metadata if cand_obj and cand_obj.structured_metadata else {}
            behav = cand_obj.behavioral_signals if cand_obj and cand_obj.behavioral_signals else {}

            eval_res = await evaluate_candidate(
                jd_text=jd_text,
                candidate_id=cid,
                resume_text=resume_text,
                metadata=meta,
                behavioral=behav,
            )

            # Update ranking DB record
            rank_res = await db.execute(
                select(RankingResult).where(RankingResult.jd_id == jd_id, RankingResult.candidate_id == cid)
            )
            ranking = rank_res.scalar_one_or_none()
            if ranking:
                ranking.stage_b_fit_score = eval_res.fit_score
                ranking.justification = eval_res.justification
                ranking.risk_flags = eval_res.risk_flags
                ranking.confidence = eval_res.confidence
                await db.commit()

            yield {
                "event": "stage_b",
                "data": json_mod.dumps({
                    "candidate_id": cid,
                    "fit_score": eval_res.fit_score,
                    "justification": eval_res.justification,
                    "risk_flags": eval_res.risk_flags,
                    "confidence": eval_res.confidence,
                })
            }
            await asyncio.sleep(0.1)  # brief yield for SSE flush

    return EventSourceResponse(event_generator())


@router.get("/jd/{jd_id}/candidate/{candidate_id}/interview-questions")
async def get_interview_questions(
    jd_id: str,
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate risk-grounded interview questions on demand."""
    from app.ranking.interview_questions import generate_questions

    jd_res = await db.execute(select(JDDecomposition).where(JDDecomposition.id == jd_id))
    jd_obj = jd_res.scalar_one_or_none()
    jd_text = jd_obj.raw_text if jd_obj else ""

    chunk_res = await db.execute(select(Chunk).where(Chunk.candidate_id == candidate_id))
    chunks = chunk_res.scalars().all()
    resume_text = "\n".join([c.text for c in chunks])

    rank_res = await db.execute(
        select(RankingResult).where(RankingResult.jd_id == jd_id, RankingResult.candidate_id == candidate_id)
    )
    ranking = rank_res.scalar_one_or_none()
    risks = ranking.risk_flags if ranking and ranking.risk_flags else []

    questions = await generate_questions(jd_text, resume_text, risks)
    return {"candidate_id": candidate_id, "questions": questions}


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit +1/-1 feedback on a candidate for a given JD."""
    result = await db.execute(
        select(RankingResult).where(
            RankingResult.jd_id == request.jd_id,
            RankingResult.candidate_id == request.candidate_id,
        )
    )
    ranking = result.scalar_one_or_none()
    
    if not ranking:
        raise HTTPException(
            404,
            f"No ranking found for JD {request.jd_id} / candidate {request.candidate_id}",
        )
    
    ranking.feedback = request.signal
    await db.commit()
    
    logger.info(
        "Feedback recorded: JD=%s, candidate=%s, signal=%d",
        request.jd_id, request.candidate_id, request.signal,
    )
    
    return {"status": "ok", "jd_id": request.jd_id, "candidate_id": request.candidate_id, "signal": request.signal}
