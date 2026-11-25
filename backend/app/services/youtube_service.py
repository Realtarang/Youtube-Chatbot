"""YouTube URL parsing and metadata retrieval."""

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import settings
from app.models.entities import VideoMetadata
from app.utils.errors import InvalidYouTubeUrl

logger = logging.getLogger(__name__)

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PATH_PREFIXES = ("embed", "v", "shorts", "live", "watch")
_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be"}


def normalize_url(raw_url: str) -> str:
    """Trim input and add a scheme when the user pasted ``youtu.be/...``."""
    candidate = (raw_url or "").strip()
    if not candidate:
        raise InvalidYouTubeUrl("Paste a YouTube video URL to get started.")
    if not re.match(r"^https?://", candidate, re.IGNORECASE):
        candidate = "https://" + candidate
    return candidate


def parse_video_id(raw_url: str) -> str:
    """Validate a YouTube URL and return its 11-character video ID."""
    url = normalize_url(raw_url)
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if host not in _HOSTS:
        raise InvalidYouTubeUrl("Only youtube.com and youtu.be links are supported.")

    segments = [segment for segment in parsed.path.split("/") if segment]
    video_id: Optional[str] = None

    if host.endswith("youtu.be"):
        video_id = segments[0] if segments else None
    elif segments and segments[0] == "watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    elif segments and segments[0] in _PATH_PREFIXES[1:]:
        video_id = segments[1] if len(segments) > 1 else None
    elif segments and segments[0] == "embed":
        video_id = segments[1] if len(segments) > 1 else None

    if not video_id:
        raise InvalidYouTubeUrl("The YouTube link is missing a video ID.")

    video_id = video_id.strip()
    if not _VIDEO_ID_RE.match(video_id):
        raise InvalidYouTubeUrl("The YouTube video ID in that link is not valid.")

    return video_id


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _ytdlp_metadata(video_id: str) -> Optional[dict]:
    """Best-effort metadata via yt-dlp (title, channel, duration, thumbnail)."""
    try:
        import yt_dlp  # imported lazily: heavy module, optional at runtime
    except ImportError:  # pragma: no cover - dependency is installed in requirements
        logger.warning("yt-dlp is not installed; falling back to oEmbed metadata")
        return None

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": settings.ytdlp_timeout_seconds,
        "extract_flat": False,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(canonical_url(video_id), download=False)
    except Exception as exc:  # yt-dlp raises many extractor-specific errors
        logger.info("yt-dlp metadata failed for %s: %s", video_id, exc)
        return None
    if not isinstance(info, dict):
        return None
    return info


async def _oembed_metadata(video_id: str) -> Optional[dict]:
    url = "https://www.youtube.com/oembed"
    params = {"url": canonical_url(video_id), "format": "json"}
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        logger.info("oEmbed metadata request failed for %s: %s", video_id, exc)
        return None
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


async def fetch_metadata(video_id: str) -> VideoMetadata:
    """Resolve video metadata, degrading gracefully to a minimal record."""
    info = await asyncio.to_thread(_ytdlp_metadata, video_id)

    if info:
        duration = info.get("duration")
        return VideoMetadata(
            video_id=video_id,
            url=info.get("webpage_url") or canonical_url(video_id),
            title=info.get("title") or f"YouTube video {video_id}",
            channel=info.get("channel") or info.get("uploader"),
            channel_url=info.get("channel_url") or info.get("uploader_url"),
            thumbnail_url=info.get("thumbnail") or thumbnail_url(video_id),
            duration_seconds=float(duration) if duration else None,
            description=(info.get("description") or "")[:2000] or None,
        )

    oembed = await _oembed_metadata(video_id)
    if oembed:
        return VideoMetadata(
            video_id=video_id,
            url=canonical_url(video_id),
            title=oembed.get("title") or f"YouTube video {video_id}",
            channel=oembed.get("author_name"),
            channel_url=oembed.get("author_url"),
            thumbnail_url=oembed.get("thumbnail_url") or thumbnail_url(video_id),
            duration_seconds=None,
        )

    # Metadata is nice-to-have; transcript extraction may still succeed.
    logger.info("No metadata available for %s; using placeholder record", video_id)
    return VideoMetadata(
        video_id=video_id,
        url=canonical_url(video_id),
        title=f"YouTube video {video_id}",
        thumbnail_url=thumbnail_url(video_id),
    )
