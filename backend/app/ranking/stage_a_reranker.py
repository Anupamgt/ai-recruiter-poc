"""Stage A fast re-ranking: weighted scoring using retrieval scores + metadata.

P0 weights:
  0.6 * retrieval_score
  + 0.25 * domain_years_match
  + 0.15 * education_match

Explicitly excludes protected-characteristic proxies:
  - No raw graduation year (derive domain_years instead)
  - No name-based inference
  - No photo analysis
"""
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# Education level hierarchy for matching
EDU_HIERARCHY = {
    'associate': 1,
    'bachelors': 2,
    'masters': 3,
    'phd': 4,
}

# P1.3 weights including behavioral signals
W_RETRIEVAL = 0.40
W_DOMAIN_YEARS = 0.20
W_EDUCATION = 0.10
W_SKILL_RECENCY = 0.15
W_SCOPE_GROWTH = 0.10
W_TENURE_STABILITY = 0.05

# Features that are EXPLICITLY BLOCKED as protected-characteristic proxies
BLOCKED_FEATURES = frozenset({
    'graduation_year', 'age', 'gender', 'name', 'photo',
    'ethnicity', 'race', 'religion', 'marital_status',
    'nationality', 'date_of_birth',
})


def _domain_years_match(required_years: float | None, candidate_years: float | None) -> float:
    """Score domain years fit. 1.0 if candidate >= requirement, linear scale down."""
    if required_years is None or required_years <= 0:
        return 0.5  # No requirement specified, neutral score
    if candidate_years is None:
        return 0.3  # Unknown, slight penalty but not exclusion
    if candidate_years >= required_years:
        return 1.0
    # Linear scale: candidate_years / required_years
    return max(0.0, candidate_years / required_years)


def _education_match(required_edu: str | None, candidate_edu: str | None) -> float:
    """Score education level match."""
    if required_edu is None:
        return 0.5  # No requirement, neutral
    if candidate_edu is None:
        return 0.3  # Unknown
    
    req_level = EDU_HIERARCHY.get(required_edu.lower(), 0)
    cand_level = EDU_HIERARCHY.get(candidate_edu.lower(), 0)
    
    if cand_level >= req_level:
        return 1.0  # Meets or exceeds
    if cand_level == req_level - 1:
        return 0.5  # One level below
    return 0.0  # Significantly below


def _validate_features(features: set[str]) -> None:
    """Assert no protected-characteristic proxy features are used."""
    blocked_used = features & BLOCKED_FEATURES
    if blocked_used:
        raise ValueError(
            f"Stage A scoring attempted to use blocked features "
            f"(protected-characteristic proxies): {blocked_used}"
        )


def rerank_stage_a(
    retrieval_results: list[dict[str, Any]],
    candidate_metadata: dict[str, dict[str, Any]],
    jd_requirements: dict[str, Any] | None = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Perform Stage A fast re-ranking on retrieval results.
    
    Args:
        retrieval_results: List of {candidate_id, chunk_id, score, text, section_label}
            from vector search.
        candidate_metadata: Dict mapping candidate_id -> structured_metadata dict.
        jd_requirements: Optional dict with 'domain_years' and 'education_level' from JD.
        top_k: Number of top candidates to return.
    
    Returns:
        List of top-k candidates sorted by stage_a_score, each with:
        {candidate_id, stage_a_score, dense_score, metadata, confidence}
    """
    # Validate we're not using protected features
    feature_names = {'retrieval_score', 'domain_years', 'education_level'}
    _validate_features(feature_names)
    
    jd_req = jd_requirements or {}
    jd_years = jd_req.get('domain_years')
    jd_edu = jd_req.get('education_level')
    
    # Aggregate scores per candidate (max score across chunks)
    candidate_scores: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'max_retrieval_score': 0.0,
        'chunk_scores': [],
    })
    
    for result in retrieval_results:
        cid = result['candidate_id']
        score = result.get('score', 0.0)
        candidate_scores[cid]['chunk_scores'].append(score)
        if score > candidate_scores[cid]['max_retrieval_score']:
            candidate_scores[cid]['max_retrieval_score'] = score
    
    # Compute composite score per candidate
    ranked = []
    for cid, scores_data in candidate_scores.items():
        meta = candidate_metadata.get(cid, {})
        
        retrieval_score = scores_data['max_retrieval_score']
        years_score = _domain_years_match(jd_years, meta.get('domain_years'))
        edu_score = _education_match(jd_edu, meta.get('education_level'))
        
        behavioral = meta.get('_behavioral_signals', {})
        recency_score = float(behavioral.get('skill_recency', 0.5))
        scope_score = float(behavioral.get('scope_growth_score', 0.5))
        
        tenures = behavioral.get('tenure_per_role', [18])
        avg_tenure = sum(tenures) / len(tenures) if tenures else 18
        tenure_score = min(1.0, avg_tenure / 18.0)
        
        stage_a_score = (
            W_RETRIEVAL * retrieval_score
            + W_DOMAIN_YEARS * years_score
            + W_EDUCATION * edu_score
            + W_SKILL_RECENCY * recency_score
            + W_SCOPE_GROWTH * scope_score
            + W_TENURE_STABILITY * tenure_score
        )
        
        # Determine confidence based on profile completeness
        completeness = behavioral.get('profile_completeness', 0.5)
        confidence = 'low' if completeness < 0.4 else ('high' if completeness > 0.7 else 'medium')
        
        ranked.append({
            'candidate_id': cid,
            'stage_a_score': round(stage_a_score, 4),
            'dense_score': round(retrieval_score, 4),
            'domain_years_score': round(years_score, 4),
            'education_score': round(edu_score, 4),
            'metadata': {k: v for k, v in meta.items() if not k.startswith('_')},
            'confidence': confidence,
        })
    
    # Sort by composite score descending
    ranked.sort(key=lambda x: x['stage_a_score'], reverse=True)
    
    top = ranked[:top_k]
    logger.info(
        "Stage A re-ranked %d candidates → top-%d (scores: %.4f to %.4f)",
        len(ranked), len(top),
        top[0]['stage_a_score'] if top else 0,
        top[-1]['stage_a_score'] if top else 0,
    )
    
    return top
