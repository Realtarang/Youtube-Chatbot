"""RAG chat endpoint: retrieve transcript context, then answer with Groq.

Reliability rules:
* retrieval is hybrid (vector + keyword) and always returns the closest passages;
* transient AI failures are retried, then answered from transcript excerpts;
* a question with no matching passages gets an honest "not covered" reply
  instead of a speculative one;
* repeated first questions on an unchanged transcript are served from a small
  in-process cache, which keeps follow-up traffic off Groq.
"""

import asyncio
import logging
import re
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence, Tuple, Union

from fastapi import APIRouter

from app.config import settings
from app.models.entities import ChatTurn, RetrievedChunk
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ClearChatResponse,
    SourceOut,
)
from app.services import generation_service, processing_service, vector_service
from app.services.retrieval_service import retriever
from app.utils.errors import AINotConfigured, AppError, VideoNotFound, VideoNotReady
from app.utils.timestamp import format_timestamp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

DEFAULT_FOLLOWUPS = [
    "What are the key takeaways?",
    "Where is this explained step by step?",
    "Can you summarise this in a paragraph?",
]

_MULTISPACE = re.compile(r"\s+")


# ------------------------------------------------------------------- helpers
def build_sources(chunks: List[RetrievedChunk]) -> List[SourceOut]:
    return [
        SourceOut(
            chunk_index=chunk.chunk_index,
            start_time=round(chunk.start_time, 2),
            end_time=round(chunk.end_time, 2),
            timestamp=format_timestamp(chunk.start_time),
            snippet=chunk.content.strip()[:280],
            similarity=round(chunk.similarity, 4),
        )
        for chunk in chunks
    ]


async def get_ready_video(video_id: str) -> dict:
    # Light projection: the full transcript JSON is not needed to answer.
    row = await vector_service.get_video_light(video_id)
    if not row:
        raise VideoNotFound()
    if not processing_service.get_video_ready(row):
        raise VideoNotReady(status=row.get("status") or "processing")
    return row


async def resolve_session(video_id: str, session_id: Optional[str]) -> str:
    """Reuse a session only when it belongs to this video."""
    if session_id:
        try:
            session = await vector_service.get_session(session_id)
        except Exception:
            session = None
        if session and session.get("video_id") == video_id:
            return str(session["id"])
    return await vector_service.create_session(video_id)


def _normalize(text: str) -> str:
    return _MULTISPACE.sub(" ", (text or "").lower()).strip(" ?.!,")


def suggest_followups(video: dict, asked: Sequence[str]) -> List[str]:
    """Cheap follow-ups: the video's own suggested questions, minus what was asked."""
    seen = {_normalize(item) for item in asked if item}
    candidates: List[str] = []
    for question in list(video.get("suggested_questions") or []) + DEFAULT_FOLLOWUPS:
        text = str(question).strip()
        key = _normalize(text)
        if not text or key in seen or text in candidates:
            continue
        candidates.append(text)
    return candidates[:3]


class AnswerCache:
    """Small TTL cache for first-question answers (no conversation context)."""

    def __init__(self, max_entries: int, ttl_seconds: float) -> None:
        self._entries: "OrderedDict[Tuple[str, int, str, str], Tuple[float, str, List[SourceOut]]]" = (
            OrderedDict()
        )
        self._max = max(1, max_entries)
        self._ttl = ttl_seconds

    def get(self, key: Tuple[str, int, str, str]) -> Optional[Tuple[str, List[SourceOut]]]:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, answer, sources = entry
        if self._ttl > 0 and time.time() - stored_at > self._ttl:
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return answer, sources

    def put(self, key: Tuple[str, int, str, str], answer: str, sources: List[SourceOut]) -> None:
        self._entries[key] = (time.time(), answer, sources)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max:
            self._entries.popitem(last=False)


answer_cache = AnswerCache(settings.answer_cache_entries, settings.answer_cache_ttl_seconds)


# ------------------------------------------------------------------- routes
@router.post("/chat", response_model=ChatResponse, summary="Ask a question about a video")
async def chat(payload: ChatRequest):
    video = await get_ready_video(payload.video_id)
    question = payload.question.strip()

    session_id = await resolve_session(payload.video_id, payload.session_id)
    stored = await vector_service.get_messages(
        session_id, limit=settings.max_history_messages * 2, newest_first=True
    )
    history = [
        ChatTurn(role=row["role"], content=row.get("content", ""))
        for row in stored
        if row.get("role") in {"user", "assistant"}
    ]

    cache_key: Optional[Tuple[str, int, str, str]] = None
    chunks: List[RetrievedChunk] = []
    degraded = False

    if not history:
        cache_key = (
            payload.video_id,
            int(video.get("chunk_count") or 0),
            _normalize(question),
            payload.detail,
        )
        cached = answer_cache.get(cache_key)
        if cached:
            answer, sources = cached
            logger.info("Serving cached answer for %s", payload.video_id)
            await vector_service.insert_exchange(
                session_id, question, answer, [source.model_dump() for source in sources]
            )
            await vector_service.touch_session(session_id)
            return ChatResponse(
                video_id=payload.video_id,
                session_id=session_id,
                answer=answer,
                sources=sources,
                model=settings.groq_model,
                followups=suggest_followups(video, [question]),
                degraded=False,
            )

    chunks = await retriever.retrieve(payload.video_id, question)
    logger.info(
        "Chat on %s: %s passage(s) for session %s",
        payload.video_id,
        len(chunks),
        session_id,
    )

    if not chunks:
        answer = generation_service.NO_CONTEXT_ANSWER
        sources: List[SourceOut] = []
    else:
        try:
            answer = await generation_service.answer_question(
                video_title=video.get("title") or "this video",
                question=question,
                chunks=chunks,
                history=history,
                detail=payload.detail,
            )
        except AINotConfigured:
            raise
        except AppError as exc:
            logger.warning("Chat generation failed (%s): %s", exc.code, exc.message)
            answer = generation_service.fallback_answer(question, chunks)
            degraded = True
        sources = build_sources(chunks)

    if cache_key and not degraded:
        answer_cache.put(cache_key, answer, sources)

    asked = [row.get("content", "") for row in stored if row.get("role") == "user"] + [question]

    await asyncio.gather(
        vector_service.insert_exchange(
            session_id, question, answer, [source.model_dump() for source in sources]
        ),
        vector_service.touch_session(session_id),
    )

    return ChatResponse(
        video_id=payload.video_id,
        session_id=session_id,
        answer=answer,
        sources=sources,
        model=settings.groq_model,
        followups=suggest_followups(video, asked),
        degraded=degraded,
    )


@router.delete(
    "/chat/{session_id}",
    response_model=ClearChatResponse,
    summary="Clear the messages in a chat session",
)
async def clear_chat(session_id: str):
    await vector_service.clear_messages(session_id)
    return ClearChatResponse(session_id=session_id, cleared=True)
