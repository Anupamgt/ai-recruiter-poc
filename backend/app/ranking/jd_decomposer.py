"""Phase 0: Job Description Decomposition Agent.

Decomposes raw JD text into structured constraints, preferences, seniority,
and an optimized dense search query string using Gemini 3.1 Pro.
"""

import json
import logging
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings, get_thinking_config

logger = logging.getLogger(__name__)


class JDDecompositionResult(BaseModel):
    """Structured decomposition of a Job Description."""
    must_have: list[str] = Field(
        description="Strict hard technical and functional requirements that cannot be compromised."
    )
    nice_to_have: list[str] = Field(
        description="Preferred skills, bonus qualifications, or nice-to-have experience."
    )
    implied_seniority: str = Field(
        description="Inferred seniority level (e.g. Junior, Mid-Level, Senior, Staff, Principal, Executive)."
    )
    non_negotiables: dict[str, Any] = Field(
        description="Hard filters such as minimum years of experience ('min_years': int), required location ('location': str), or required degree."
    )
    flexibility_notes: str = Field(
        description="Notes on where the hiring manager shows flexibility, openness to adjacent domains, or potential contradictions."
    )
    search_query_text: str = Field(
        description="Optimized dense semantic search query string representing the ideal candidate profile for vector retrieval."
    )


def decompose_jd(raw_text: str) -> JDDecompositionResult:
    """Decompose raw JD text into structured requirements and search query."""
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    prompt = f"""You are an expert AI Recruiter and Talent Strategist.
Your task is to analyze the following Job Description and decompose it into clear, actionable hiring constraints.

Job Description:
---
{raw_text}
---

Decompose this role accurately.
1. Separate strict 'must_have' constraints from 'nice_to_have' preferences.
2. Infer the seniority level based on tone, scope, and responsibilities.
3. Extract hard 'non_negotiables' (e.g., minimum years of experience as an integer 'min_years', specific location constraints).
4. Identify any flexibility notes or potential contradictions in requirements.
5. Generate a dense 'search_query_text' that summarizes the ideal candidate's experience, skills, and accomplishments. This text will be embedded to query a vector database of resume text chunks.

Return strictly conforming JSON matching the requested schema.
"""

    thinking_config = get_thinking_config("MEDIUM")
    
    try:
        response = client.models.generate_content(
            model=settings.LLM_MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JDDecompositionResult,
                thinking_config=thinking_config,
                temperature=0.2,
            ),
        )
        if not response.text:
            raise ValueError("Empty response from Gemini JD Decomposer")
            
        data = json.loads(response.text)
        return JDDecompositionResult.model_validate(data)
    except Exception as e:
        logger.error("Failed to decompose JD via Gemini: %s", e)
        # Fallback heuristic decomposition if quota/API fails
        return JDDecompositionResult(
            must_have=["Core domain experience matching JD"],
            nice_to_have=[],
            implied_seniority="Mid-Senior",
            non_negotiables={"min_years": 2},
            flexibility_notes="Fallback decomposition used due to LLM error.",
            search_query_text=raw_text[:500],
        )
