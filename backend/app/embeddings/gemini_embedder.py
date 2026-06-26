"""Gemini embedding service using gemini-embedding-2 model."""
import logging
from typing import Any

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level client singleton
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Get or create the Gemini API client."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        logger.info("Initialized Gemini API client")
    return _client


BATCH_SIZE = 100  # Max texts per embedding batch call


async def embed_texts(
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Embed a list of texts using Gemini embedding model.
    
    Args:
        texts: List of text strings to embed.
        task_type: One of RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY,
                   SEMANTIC_SIMILARITY, CLASSIFICATION, CLUSTERING.
    
    Returns:
        List of embedding vectors.
    """
    if not texts:
        return []
    
    client = _get_client()
    all_embeddings: list[list[float]] = []
    
    # Process in batches
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        logger.debug(
            "Embedding batch %d-%d of %d texts",
            i, min(i + BATCH_SIZE, len(texts)), len(texts),
        )
        
        try:
            result = client.models.embed_content(
                model=settings.EMBEDDING_MODEL_ID,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                ),
            )
            
            for embedding in result.embeddings:
                all_embeddings.append(list(embedding.values))
                
        except Exception as e:
            logger.error("Embedding batch failed: %s", e)
            raise
    
    logger.info(
        "Embedded %d texts (dims=%d)",
        len(all_embeddings),
        len(all_embeddings[0]) if all_embeddings else 0,
    )
    
    return all_embeddings


async def embed_query(text: str) -> list[float]:
    """Embed a single query text for retrieval.
    
    Uses RETRIEVAL_QUERY task type for optimal query-document matching.
    """
    results = await embed_texts([text], task_type="RETRIEVAL_QUERY")
    if not results:
        raise ValueError("Failed to embed query text")
    return results[0]
