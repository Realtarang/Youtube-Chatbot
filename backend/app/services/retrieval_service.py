"""Hybrid retrieval over a single video's transcript chunks.

Vector search runs first. When it returns too few passages - a paraphrase, an
unusual phrasing, or a question about a term the embedding model handles badly -
the query is retried with a relaxed threshold and keyword (full-text) matches are
merged in. If the embedding model itself is unavailable, retrieval degrades to
keyword search instead of failing the request.
"""

import logging
from typing import Dict, List, Optional

from app.config import settings
from app.models.entities import RetrievedChunk
from app.services.embedding_service import embedding_service
from app.services import vector_service
from app.utils.errors import AppError

logger = logging.getLogger(__name__)


def dedupe_chunks(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    """Drop duplicate or nested chunks while keeping the strongest match."""
    seen_indices = set()
    seen_text = set()
    unique: List[RetrievedChunk] = []

    for chunk in sorted(chunks, key=lambda item: item.similarity, reverse=True):
        fingerprint = " ".join(chunk.content.lower().split())[:220]
        if chunk.chunk_index in seen_indices or fingerprint in seen_text:
            continue
        seen_indices.add(chunk.chunk_index)
        seen_text.add(fingerprint)
        unique.append(chunk)

    return sorted(unique, key=lambda item: item.chunk_index)


def _merge(into: Dict[int, RetrievedChunk], chunks: List[RetrievedChunk]) -> None:
    for chunk in chunks:
        current = into.get(chunk.chunk_index)
        if current is None or chunk.similarity > current.similarity:
            into[chunk.chunk_index] = chunk


class SemanticRetriever:
    """Hybrid (dense + keyword) retrieval scoped to one video."""

    async def retrieve(
        self,
        video_id: str,
        question: str,
        *,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> List[RetrievedChunk]:
        limit = top_k or settings.retrieval_top_k
        score_threshold = settings.similarity_threshold if threshold is None else threshold
        collected: Dict[int, RetrievedChunk] = {}

        embedding: Optional[List[float]] = None
        try:
            embedding = await embedding_service.aembed_query(question)
        except AppError as exc:
            logger.warning("Query embedding unavailable (%s); keyword search only", exc)

        if embedding:
            semantic = await vector_service.match_chunks(
                video_id,
                embedding,
                threshold=score_threshold,
                limit=limit,
            )
            _merge(collected, semantic)
            if len(semantic) < settings.retrieval_min_chunks:
                # Nearest neighbours regardless of score: better context than none.
                relaxed = await vector_service.match_chunks(
                    video_id, embedding, threshold=0.0, limit=limit
                )
                if len(relaxed) > len(semantic):
                    logger.info(
                        "Relaxed similarity threshold for %s (%s -> %s chunks)",
                        video_id,
                        len(semantic),
                        len(relaxed),
                    )
                _merge(collected, relaxed)

        lexical = await vector_service.search_chunks_lexical(video_id, question, limit=limit)
        _merge(collected, lexical)

        if not collected:
            logger.info("No transcript passage matched the question for video %s", video_id)
            return []

        best = sorted(collected.values(), key=lambda item: item.similarity, reverse=True)
        return dedupe_chunks(best[:limit])


retriever = SemanticRetriever()
