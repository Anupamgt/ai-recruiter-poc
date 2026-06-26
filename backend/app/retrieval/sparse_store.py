"""Sparse retrieval operations using BM25.

Provides BM25 scoring across resume chunks to complement dense vector search.
"""
import logging
import re
from typing import Any

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


def tokenize(text: str) -> list[str]:
    """Simple lowercase alphanumeric word tokenizer."""
    return re.findall(r"\b\w+\b", text.lower())


def search_sparse(
    query_text: str,
    all_chunks: list[dict[str, Any]],
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Score chunks using BM25Okapi against query text.
    
    Args:
        query_text: The search query string.
        all_chunks: List of dicts with: chunk_id, candidate_id, text, section_label.
        limit: Top N chunks to return.
        
    Returns:
        List of results with: chunk_id, candidate_id, text, section_label, sparse_score.
    """
    if not all_chunks or not query_text:
        return []

    tokenized_corpus = [tokenize(c.get("text", "")) for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    
    tokenized_query = tokenize(query_text)
    scores = bm25.get_scores(tokenized_query)
    
    scored_chunks = []
    for chunk, score in zip(all_chunks, scores):
        if score > 0:
            scored_chunks.append({
                "chunk_id": chunk["chunk_id"],
                "candidate_id": chunk["candidate_id"],
                "text": chunk.get("text", ""),
                "section_label": chunk.get("section_label", "other"),
                "sparse_score": float(score),
            })
            
    # Sort descending by BM25 score
    scored_chunks.sort(key=lambda x: x["sparse_score"], reverse=True)
    results = scored_chunks[:limit]
    logger.info("Sparse BM25 search returned %d results", len(results))
    return results
