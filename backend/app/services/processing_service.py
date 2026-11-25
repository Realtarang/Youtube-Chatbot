"""Video processing orchestration: extract -> chunk -> embed -> index.

Metadata and transcript extraction run before the response so the UI can show
video details immediately; chunking and embedding continue in a background
task while the client polls the video status.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.config import settings
from app.models.entities import TextChunk, Transcript, TranscriptSegment
from app.services import generation_service, vector_service, youtube_service
from app.services.embedding_service import embedding_service
from app.services.transcript_service import fetch_transcript
from app.services.whisper_service import transcribe_video
from app.utils.errors import AppError, TranscriptUnavailable
from app.utils.text_processing import chunk_transcript

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_stale(row: dict) -> bool:
    updated = row.get("updated_at") or row.get("created_at")
    if not updated:
        return True
    try:
        parsed = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - parsed).total_seconds()
    return age > settings.stale_processing_seconds


def _schedule(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _extract_transcript(video_id: str) -> Transcript:
    try:
        return await asyncio.to_thread(fetch_transcript, video_id)
    except TranscriptUnavailable as exc:
        if not settings.enable_whisper_fallback:
            raise TranscriptUnavailable(
                f"{exc.message} Speech-to-text fallback is disabled on this server."
            ) from exc
        logger.info("Falling back to Whisper transcription for %s", video_id)
        try:
            return await transcribe_video(video_id)
        except AppError:
            raise
        except Exception as exc:
            logger.exception("Whisper fallback failed for %s", video_id)
            raise TranscriptUnavailable("Captions are unavailable and transcription failed.") from exc


async def prepare_video(url: str) -> Tuple[dict, bool]:
    """Validate, extract and persist a video. Returns (record, already_indexed)."""
    video_id = youtube_service.parse_video_id(url)
    existing = await vector_service.get_video(video_id)

    if existing:
        status = existing.get("status")
        if status == "ready" and int(existing.get("chunk_count") or 0) > 0:
            logger.info("Video %s already indexed; reusing cached embeddings", video_id)
            return existing, True
        if status == "processing" and not _is_stale(existing):
            logger.info("Video %s is already being processed", video_id)
            return existing, True
        if status == "processing" and _is_stale(existing):
            logger.warning("Video %s has a stale processing job; restarting", video_id)

    metadata = await youtube_service.fetch_metadata(video_id)
    transcript = await _extract_transcript(video_id)

    duration = metadata.duration_seconds or transcript.duration_seconds
    record = {
        "video_id": video_id,
        "url": metadata.url,
        "title": metadata.title,
        "channel": metadata.channel,
        "channel_url": metadata.channel_url,
        "thumbnail_url": metadata.thumbnail_url,
        "duration_seconds": duration,
        "description": metadata.description,
        "transcript_language": transcript.language,
        "transcript_source": transcript.source,
        "transcript": [segment.to_dict() for segment in transcript.segments],
        "segment_count": len(transcript.segments),
        "chunk_count": 0,
        "status": "processing",
        "error_code": None,
        "error_message": None,
        "suggested_questions": [],
        "updated_at": _now(),
    }

    saved = await vector_service.upsert_video(record)
    _schedule(_index_video(video_id))
    return saved or record, False


async def _index_video(video_id: str) -> None:
    try:
        row = await vector_service.get_video(video_id)
        if not row:
            logger.warning("Video %s disappeared before indexing", video_id)
            return

        segments = [
            TranscriptSegment.from_dict(item) for item in (row.get("transcript") or [])
        ]
        chunks: list[TextChunk] = chunk_transcript(
            segments,
            chunk_size_chars=settings.chunk_size_chars,
            chunk_overlap_chars=settings.chunk_overlap_chars,
        )
        if not chunks:
            raise TranscriptUnavailable("The transcript is too short to build a searchable index.")

        logger.info("Embedding %s chunks for %s", len(chunks), video_id)
        embeddings = await embedding_service.aembed_documents([chunk.text for chunk in chunks])
        indexed = await vector_service.replace_chunks(video_id, chunks, embeddings)

        questions = await generation_service.generate_suggestions(
            row.get("title") or "this video", chunks
        )

        await vector_service.update_video(
            video_id,
            {
                "status": "ready",
                "chunk_count": indexed,
                "suggested_questions": questions,
                "processed_at": _now(),
                "updated_at": _now(),
                "error_code": None,
                "error_message": None,
            },
        )
        logger.info("Indexed %s chunks for %s", indexed, video_id)
    except AppError as exc:
        logger.error("Indexing failed for %s: %s", video_id, exc.message)
        await _mark_failed(video_id, exc.code, exc.message)
    except Exception:
        logger.exception("Unexpected indexing failure for %s", video_id)
        await _mark_failed(
            video_id,
            "processing_failed",
            "Processing failed while generating embeddings. Please try again.",
        )


async def _mark_failed(video_id: str, code: str, message: str) -> None:
    try:
        await vector_service.update_video(
            video_id,
            {
                "status": "failed",
                "error_code": code,
                "error_message": message,
                "updated_at": _now(),
            },
        )
    except Exception:  # pragma: no cover - best effort
        logger.exception("Could not persist failure status for %s", video_id)


def get_video_ready(row: Optional[dict]) -> bool:
    return bool(row and row.get("status") == "ready" and int(row.get("chunk_count") or 0) > 0)
