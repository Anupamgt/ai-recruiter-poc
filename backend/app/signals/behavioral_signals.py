"""Behavioral signal extractor.

Derives non-keyword behavioral features (tenure stability, velocity, scope growth,
completeness) from resume text.
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_behavioral_signals(text: str, chunks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Extract behavioral signals from raw resume text and section chunks."""
    # 1. Detect year spans (e.g., 2018 - 2021, 2022 to Present)
    years = [int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", text)]
    unique_years = sorted(list(set(years)))
    
    total_career_years = max(1, (unique_years[-1] - unique_years[0])) if len(unique_years) >= 2 else 2
    
    # Heuristic role count based on common experience bullet or title headings
    role_indicators = len(re.findall(r"\b(senior|lead|manager|director|engineer|developer|architect|consultant|specialist|head|vp)\b", text.lower()))
    role_count = max(1, min(10, role_indicators // 2))
    
    # Tenure per role (approximate average months)
    avg_tenure_months = int((total_career_years * 12) / role_count)
    tenure_per_role = [avg_tenure_months] * role_count
    
    # Title velocity (roles per year)
    title_velocity = round(role_count / total_career_years, 2)
    
    # Scope growth score (presence of leadership/scale terminology)
    scope_keywords = len(re.findall(r"\b(led|managed|spearheaded|scaled|architected|grew|budget|team of|mentored|strategy|owned)\b", text.lower()))
    scope_growth_score = min(1.0, round(scope_keywords / 10.0, 2))
    
    # Employment gap (mock heuristic: if span > 2 yrs between sequential matches)
    employment_gap_months = 0
    if len(unique_years) >= 3:
        for i in range(len(unique_years) - 1):
            gap = unique_years[i+1] - unique_years[i]
            if gap > 2:
                employment_gap_months = max(employment_gap_months, (gap - 1) * 12)
                
    # Skill recency score
    skill_recency = 0.85 if scope_growth_score > 0.3 else 0.50
    
    # Profile completeness score (check presence of standard section keywords)
    has_exp = bool(re.search(r"\b(experience|employment|work history)\b", text.lower()))
    has_edu = bool(re.search(r"\b(education|university|college|degree|bachelor|master)\b", text.lower()))
    has_skl = bool(re.search(r"\b(skills|technologies|tools|competencies)\b", text.lower()))
    
    completeness = round((has_exp * 0.45 + has_edu * 0.30 + has_skl * 0.25), 2)
    
    return {
        "tenure_per_role": tenure_per_role,
        "title_velocity": title_velocity,
        "scope_growth_score": scope_growth_score,
        "employment_gap_months": employment_gap_months,
        "skill_recency": skill_recency,
        "profile_completeness": completeness,
        # Mock field for future GitHub/StackOverflow/Kaggle API integration
        "external_engagement_score": None,
    }
