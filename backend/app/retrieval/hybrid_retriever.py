"""Hybrid retrieval combining dense cosine search and sparse BM25 search via RRF.

Applies Reciprocal Rank Fusion (RRF) and post-retrieval hard non_negotiable filters.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

RRF_K = 60


def hybrid_search_and_filter(
    dense_results: list[dict[str, Any]],
    sparse_results: list[dict[str, Any]],
    candidate_profiles: dict[str, Any],
    non_negotiables: dict[str, Any] | None = None,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Perform RRF fusion on dense and sparse results and apply hard filters.

    Args:
        dense_results: List of dicts with: candidate_id, chunk_id, score (dense).
        sparse_results: List of dicts with: candidate_id, chunk_id, sparse_score.
        candidate_profiles: Mapping of candidate_id -> metadata dict (e.g. domain_years, education_level).
        non_negotiables: Hard constraints from JD decomposition (e.g. {'min_years': 3}).
        top_k: Number of candidates to return.

    Returns:
        List of fused candidate dicts with: candidate_id, rrf_score, dense_score, sparse_score.
    """
    # 1. Aggregate max dense score per candidate
    cand_dense = {}
    for r in dense_results:
        cid = r["candidate_id"]
        if cid not in cand_dense or r["score"] > cand_dense[cid]["dense_score"]:
            cand_dense[cid] = {"dense_score": r["score"], "chunk_id": r["chunk_id"]}

    # Sort candidates by dense score descending
    dense_ranked = sorted(cand_dense.keys(), key=lambda c: cand_dense[c]["dense_score"], reverse=True)
    dense_ranks = {cid: rank + 1 for rank, cid in enumerate(dense_ranked)}

    # 2. Aggregate max sparse score per candidate
    cand_sparse = {}
    for r in sparse_results:
        cid = r["candidate_id"]
        if cid not in cand_sparse or r["sparse_score"] > cand_sparse[cid]["sparse_score"]:
            cand_sparse[cid] = {"sparse_score": r["sparse_score"], "chunk_id": r["chunk_id"]}

    sparse_ranked = sorted(cand_sparse.keys(), key=lambda c: cand_sparse[c]["sparse_score"], reverse=True)
    sparse_ranks = {cid: rank + 1 for rank, cid in enumerate(sparse_ranked)}

    # 3. Compute RRF scores across all unique candidate IDs
    all_cids = set(cand_dense.keys()) | set(cand_sparse.keys())
    fused_pool = []

    for cid in all_cids:
        d_rank = dense_ranks.get(cid)
        s_rank = sparse_ranks.get(cid)

        rrf = 0.0
        if d_rank:
            rrf += 1.0 / (RRF_K + d_rank)
        if s_rank:
            rrf += 1.0 / (RRF_K + s_rank)

        d_score = cand_dense[cid]["dense_score"] if cid in cand_dense else 0.0
        s_score = cand_sparse[cid]["sparse_score"] if cid in cand_sparse else 0.0

        fused_pool.append({
            "candidate_id": cid,
            "rrf_score": rrf,
            "dense_score": d_score,
            "sparse_score": s_score,
            "metadata": candidate_profiles.get(cid, {}),
        })

    # Sort pool descending by RRF score
    fused_pool.sort(key=lambda x: x["rrf_score"], reverse=True)

    # 4. Post-retrieval non_negotiable filtering
    filtered_pool = []
    min_years = non_negotiables.get("min_years") if non_negotiables and isinstance(non_negotiables, dict) else None
    req_degree = non_negotiables.get("degree") if non_negotiables and isinstance(non_negotiables, dict) else None

    for cand in fused_pool:
        cid = cand["candidate_id"]
        meta = cand.get("metadata", {})
        cand_years = meta.get("domain_years") or 0

        # Check min_years constraint
        if min_years is not None and isinstance(min_years, (int, float)):
            try:
                if float(cand_years) < float(min_years):
                    logger.info("Filtered out candidate %s: domain_years (%s) < min_years (%s)", cid, cand_years, min_years)
                    continue
            except (ValueError, TypeError):
                pass

        filtered_pool.append(cand)
        if len(filtered_pool) >= top_k:
            break

    logger.info("Hybrid RRF retrieval returned %d candidates (from %d un-fused)", len(filtered_pool), len(all_cids))
    return filtered_pool
