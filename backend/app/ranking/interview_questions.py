"""Targeted interview question generator.

Generates 3-5 custom interview questions grounded in specific candidate risk flags.
"""
import asyncio
import json
import logging
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings, get_thinking_config

logger = logging.getLogger(__name__)


class QuestionItem(BaseModel):
    question: str = Field(description="The interview question")
    target_risk: str = Field(description="The specific risk flag this question probes")


class InterviewQuestionsResult(BaseModel):
    questions: list[QuestionItem]


async def generate_questions(
    jd_text: str,
    resume_text: str,
    risk_flags: list[str],
) -> list[dict[str, str]]:
    """Generate risk-grounded interview questions."""
    if not risk_flags:
        return [{"question": "Could you walk us through your proudest technical achievement?", "target_risk": "General Fit"}]

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    prompt = f"""You are an expert technical interviewer.
Generate 3 targeted interview questions for a candidate based on their identified risk flags.

Job Description:
{jd_text[:1000]}

Identified Candidate Risks:
{json.dumps(risk_flags)}

Return strictly conforming JSON matching the schema. Each question must directly probe one of the risk flags.
"""

    thinking_config = get_thinking_config("LOW")

    def _call():
        return client.models.generate_content(
            model=settings.LLM_MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=InterviewQuestionsResult,
                thinking_config=thinking_config,
                temperature=0.3,
            ),
        )

    try:
        response = await asyncio.to_thread(_call)
        if not response.text:
            raise ValueError("Empty response from question generator")
        data = json.loads(response.text)
        validated = InterviewQuestionsResult.model_validate(data)
        return [q.model_dump() for q in validated.questions]
    except Exception as e:
        logger.error("Failed to generate questions: %s", e)
        return [{"question": f"Can you elaborate on your experience regarding: {rf}?", "target_risk": rf} for rf in risk_flags]
