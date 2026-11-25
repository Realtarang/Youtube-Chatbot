"""Optional speech-to-text fallback using Groq-hosted Whisper.

Only used when ``ENABLE_WHISPER_FALLBACK=true`` and captions are unavailable.
Downloading audio must be permitted for the content you process; the fallback
is therefore opt-in and documented in the README.
"""

import asyncio
import logging
import os
import tempfile
from typing import List

from app.config import settings
from app.models.entities import Transcript, TranscriptSegment
from app.utils.errors import AINotConfigured, TranscriptUnavailable
from app.utils.text_processing import prepare_segments
from app.services.youtube_service import canonical_url

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def _download_audio(video_id: str) -> str:
    """Download the smallest audio stream to a temp file. Returns its path."""
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover
        raise TranscriptUnavailable("Audio download requires the yt-dlp package.") from exc

    target_dir = tempfile.mkdtemp(prefix="videomind-audio-")
    template = os.path.join(target_dir, f"{video_id}.%(ext)s")
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "worstaudio/worst",
        "outtmpl": template,
        "socket_timeout": settings.ytdlp_timeout_seconds,
        "max_filesize": 24 * 1024 * 1024,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(canonical_url(video_id), download=True)
        path = ydl.prepare_filename(info)

    if not os.path.exists(path):
        raise TranscriptUnavailable("The audio track could not be downloaded.")
    return path


async def _transcribe_with_groq(path: str) -> dict:
    if not settings.groq_configured:
        raise AINotConfigured()

    import httpx

    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    data = {
        "model": settings.whisper_model,
        "response_format": "verbose_json",
        "temperature": "0",
    }
    async with httpx.AsyncClient(timeout=600.0) as client:
        with open(path, "rb") as audio:
            files = {"file": (os.path.basename(path), audio, "audio/mpeg")}
            response = await client.post(
                GROQ_TRANSCRIPTION_URL, headers=headers, data=data, files=files
            )
    if response.status_code >= 400:
        logger.warning("Groq transcription failed (%s): %s", response.status_code, response.text[:400])
        raise TranscriptUnavailable(
            "Speech-to-text transcription failed. The audio may be too long or unavailable."
        )
    return response.json()


async def transcribe_video(video_id: str) -> Transcript:
    """Download audio and transcribe it with Whisper, preserving timestamps."""
    path = await asyncio.to_thread(_download_audio, video_id)
    try:
        payload = await _transcribe_with_groq(path)
    finally:
        try:
            os.remove(path)
            os.rmdir(os.path.dirname(path))
        except OSError:
            pass

    raw_segments: List[dict] = []
    for segment in payload.get("segments", []) or []:
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))
        raw_segments.append({"start": start, "end": end, "text": segment.get("text", "")})

    segments = prepare_segments(raw_segments)
    if not segments and payload.get("text"):
        # Whisper returned text without segment timings: keep it as one block.
        segments = [TranscriptSegment(start=0.0, end=0.0, text=payload["text"])]
    if not segments:
        raise TranscriptUnavailable("Speech-to-text produced an empty transcript.")

    logger.info("Whisper fallback produced %s segments for %s", len(segments), video_id)
    return Transcript(
        video_id=video_id,
        segments=segments,
        language=payload.get("language") or "unknown",
        source="whisper",
    )
