"""Video processing, metadata, transcript and history endpoints."""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Query, Response, status

from app.schemas.chat import ChatHistoryResponse, ChatMessageOut, SourceOut
from app.schemas.video import (
    DeleteVideoResponse,
    ProcessVideoRequest,
    ProcessVideoResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
    TranscriptResponse,
    VideoOut,
)
from app.services import processing_service, vector_service
from app.services.retrieval_service import retriever
from app.utils.errors import VideoNotFound
from app.utils.timestamp import format_timestamp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video", tags=["video"])

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _require_video_id(video_id: str) -> str:
    if not _VIDEO_ID_RE.match(video_id or ""):
        raise VideoNotFound("That is not a valid YouTube video ID.")
    return video_id


@router.post(
    "/process",
    response_model=ProcessVideoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Extract, chunk, embed and index a YouTube video",
)
async def process_video(payload: ProcessVideoRequest, response: Response):
    record, already_processed = await processing_service.prepare_video(payload.url)
    video = VideoOut.from_row(record)
    if video.status == "ready":
        response.status_code = status.HTTP_200_OK
    return ProcessVideoResponse(
        video=video, status=video.status, already_processed=already_processed
    )


@router.get("/{video_id}", response_model=VideoOut, summary="Get video metadata and status")
async def get_video(video_id: str):
    row = await vector_service.get_video(_require_video_id(video_id))
    if not row:
        raise VideoNotFound()
    return VideoOut.from_row(row)


@router.get(
    "/{video_id}/transcript",
    response_model=TranscriptResponse,
    summary="Get the full transcript with timestamps",
)
async def get_transcript(video_id: str):
    row = await vector_service.get_video(_require_video_id(video_id))
    if not row:
        raise VideoNotFound()
    segments = row.get("transcript") or []
    if not segments:
        raise VideoNotFound("No transcript is stored for this video.")
    return TranscriptResponse.from_row(row, segments)


@router.post(
    "/{video_id}/search",
    response_model=SearchResponse,
    summary="Find the moments in a video that match a query",
)
async def search_video(video_id: str, payload: SearchRequest):
    """Hybrid search used by the \"find moments\" box in the app."""
    _require_video_id(video_id)
    row = await vector_service.get_video_light(video_id)
    if not row:
        raise VideoNotFound()

    chunks = await retriever.retrieve(video_id, payload.query, top_k=12, threshold=0.1)
    # Retrieval deliberately relaxes its threshold; the search box should still
    # say "nothing matched" rather than show unrelated passages.
    ordered = sorted(
        (chunk for chunk in chunks if chunk.similarity >= 0.18),
        key=lambda chunk: chunk.similarity,
        reverse=True,
    )[:8]
    return SearchResponse(
        video_id=video_id,
        query=payload.query,
        results=[
            SearchHit(
                chunk_index=chunk.chunk_index,
                start_time=round(chunk.start_time, 2),
                end_time=round(chunk.end_time, 2),
                timestamp=format_timestamp(chunk.start_time),
                snippet=chunk.content.strip()[:320],
                score=round(chunk.similarity, 4),
            )
            for chunk in ordered
        ],
    )


@router.get(
    "/{video_id}/history",
    response_model=ChatHistoryResponse,
    summary="Get conversation history for a session",
)
async def get_history(video_id: str, session_id: Optional[str] = Query(default=None)):
    row = await vector_service.get_video(_require_video_id(video_id))
    if not row:
        raise VideoNotFound()

    if not session_id:
        return ChatHistoryResponse(video_id=video_id, session_id=None, messages=[])

    try:
        session = await vector_service.get_session(session_id)
    except Exception:
        session = None

    if not session or session.get("video_id") != video_id:
        return ChatHistoryResponse(video_id=video_id, session_id=None, messages=[])

    rows = await vector_service.get_messages(session_id, limit=200)
    messages = [
        ChatMessageOut(
            id=message.get("id"),
            role=message.get("role", "assistant"),
            content=message.get("content", ""),
            sources=[SourceOut(**source) for source in (message.get("sources") or [])],
            created_at=message.get("created_at"),
        )
        for message in rows
    ]
    return ChatHistoryResponse(video_id=video_id, session_id=session_id, messages=messages)


@router.delete(
    "/{video_id}",
    response_model=DeleteVideoResponse,
    summary="Delete a video with its chunks, sessions and messages",
)
async def delete_video(video_id: str):
    deleted = await vector_service.delete_video(_require_video_id(video_id))
    if not deleted:
        raise VideoNotFound()
    return DeleteVideoResponse(video_id=video_id, deleted=True)
