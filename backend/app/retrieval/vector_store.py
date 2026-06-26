"""Qdrant vector store operations for candidate chunk storage and retrieval."""
import logging
from typing import Any

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level client singleton
_qdrant_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Get or create the Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        if settings.QDRANT_HOST in ("localhost", "127.0.0.1", "local"):
            import os
            db_path = "./data/qdrant_storage"
            os.makedirs(db_path, exist_ok=True)
            _qdrant_client = QdrantClient(path=db_path)
            logger.info("Connected to embedded Qdrant at %s", db_path)
        else:
            _qdrant_client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
            )
            logger.info(
                "Connected to Qdrant at %s:%d",
                settings.QDRANT_HOST,
                settings.QDRANT_PORT,
            )
    return _qdrant_client


def init_collection() -> None:
    """Create the candidate chunks collection if it doesn't exist."""
    client = _get_client()
    collection_name = settings.QDRANT_COLLECTION
    
    try:
        collections = client.get_collections().collections
        existing_names = [c.name for c in collections]
        
        if collection_name in existing_names:
            logger.info("Qdrant collection '%s' already exists", collection_name)
            return
        
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=settings.EMBEDDING_DIMENSIONS,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info(
            "Created Qdrant collection '%s' (dims=%d, cosine)",
            collection_name,
            settings.EMBEDDING_DIMENSIONS,
        )
    except Exception as e:
        logger.error("Failed to initialize Qdrant collection: %s", e)
        raise


def upsert_chunks(
    candidate_id: str,
    chunks_with_embeddings: list[dict[str, Any]],
) -> list[str]:
    """Upsert candidate chunks with embeddings into Qdrant.
    
    Args:
        candidate_id: The candidate's ID.
        chunks_with_embeddings: List of dicts with keys:
            - chunk_id: UUID string for the point
            - text: chunk text
            - section_label: section label
            - embedding: list[float] vector
    
    Returns:
        List of point IDs (chunk_ids) that were upserted.
    """
    client = _get_client()
    points = []
    point_ids = []
    
    for chunk in chunks_with_embeddings:
        point_id = chunk['chunk_id']
        points.append(
            models.PointStruct(
                id=point_id,
                vector=chunk['embedding'],
                payload={
                    'candidate_id': candidate_id,
                    'section_label': chunk.get('section_label', 'other'),
                    'text': chunk.get('text', ''),
                },
            )
        )
        point_ids.append(point_id)
    
    if points:
        client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=points,
        )
        logger.info(
            "Upserted %d chunks for candidate %s",
            len(points), candidate_id,
        )
    
    return point_ids


def search_dense(
    query_embedding: list[float],
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search for similar chunks using dense (cosine) similarity.
    
    Returns list of results with: candidate_id, chunk_id, score, text, section_label.
    """
    client = _get_client()
    
    results = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=query_embedding,
        limit=limit,
        with_payload=True,
    )
    
    search_results = []
    for point in results.points:
        search_results.append({
            'chunk_id': point.id,
            'score': point.score,
            'candidate_id': point.payload.get('candidate_id', ''),
            'text': point.payload.get('text', ''),
            'section_label': point.payload.get('section_label', 'other'),
        })
    
    logger.info("Dense search returned %d results", len(search_results))
    return search_results


def delete_candidate(candidate_id: str) -> None:
    """Remove all Qdrant points for a given candidate."""
    client = _get_client()
    
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="candidate_id",
                        match=models.MatchValue(value=candidate_id),
                    )
                ]
            )
        ),
    )
    logger.info("Deleted all chunks for candidate %s", candidate_id)
