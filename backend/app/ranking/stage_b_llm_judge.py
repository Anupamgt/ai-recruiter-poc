"""Stage B LLM Judge: Deep candidate evaluation and explainability.

Evaluates top Stage A shortlisted candidates against JD constraints
using Gemini 3.1 Pro with structured JSON justification.
"""
import asyncio
import json
import logging
from typing import Any, Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings, get_thinking_config

logger = logging.getLogger(__name__)


class StageBEvaluation(BaseModel):
    """Structured evaluation of a candidate by Gemini Judge."""
    candidate_id: str
    fit_score: float = Field(ge=0.0, le=100.0, description="Overall match score between 0 and 100")
    justification: str = Field(description="Evidence-backed justification explicitly contrasting JD requirements against resume evidence.")
    risk_flags: list[str] = Field(description="Specific potential risks, short tenures, or missing requirements.")
    confidence: Literal["low", "medium", "high"] = Field(description="Confidence level in evaluation.")


async def evaluate_candidate(
    jd_text: str,
    candidate_id: str,
    resume_text: str,
    metadata: dict[str, Any],
    behavioral: dict[str, Any],
) -> StageBEvaluation:
    """Evaluate a single candidate against a JD."""
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    prompt = f"""You are an elite AI Recruiter acting as an unbiased hiring judge.
Evaluate Candidate {candidate_id} for the following Job Description.

Job Description:
---
{jd_text}
---

Candidate Resume Evidence:
---
{resume_text[:2500]}
---

Extracted Metadata: {json.dumps(metadata)}
Behavioral Signals: {json.dumps(behavioral)}

Rules:
1. Ground your fit_score strictly in technical/functional evidence.
2. If profile_completeness is low (<0.4), set confidence to 'low'.
3. List 1-3 specific risk_flags (e.g. lack of scale experience, gap in recent years).

Return strictly conforming JSON matching the schema.
"""

    thinking_config = get_thinking_config("MEDIUM")

    def _call():
        return client.models.generate_content(
            model=settings.LLM_MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=StageBEvaluation,
                thinking_config=thinking_config,
                temperature=0.2,
            ),
        )

    try:
        # Run synchronous SDK call in threadpool
        response = await asyncio.to_thread(_call)
        if not response.text:
            raise ValueError("Empty response from Gemini Judge")
        data = json.loads(response.text)
        data["candidate_id"] = candidate_id
        return StageBEvaluation.model_validate(data)
    except Exception as e:
        logger.error("Stage B judge failed for candidate %s: %s", candidate_id, e)
        # Fallback evaluation
        return StageBEvaluation(
            candidate_id=candidate_id,
            fit_score=75.0,
            justification="Fallback evaluation used due to LLM error. Candidate passed Stage A vector retrieval.",
            risk_flags=["LLM verification unavailable"],
            confidence="medium",
        )
