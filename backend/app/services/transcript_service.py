"""Transcript extraction from YouTube captions.

Supports both the ``youtube-transcript-api`` 0.6.x (static helpers) and 1.x
(instance based) APIs so a version bump does not break the pipeline.
"""

import logging
from typing import List, Optional

from youtube_transcript_api import YouTubeTranscriptApi

from app.models.entities import Transcript, TranscriptSegment
from app.utils.errors import TranscriptUnavailable, VideoUnavailable
from app.utils.text_processing import prepare_segments

logger = logging.getLogger(__name__)

PREFERRED_LANGUAGES = ["en", "en-US", "en-GB", "en-IN"]

_ERROR_MESSAGES = {
    "TranscriptsDisabled": "Captions are disabled for this video, so there is no transcript to search.",
    "NoTranscriptFound": "No transcript is available for this video in any language.",
    "NoTranscriptAvailable": "No transcript is available for this video.",
    "VideoUnavailable": "This video is unavailable. It may be private, deleted or region-restricted.",
    "VideoUnplayable": "This video cannot be played here (it may be private or age-restricted).",
    "AgeRestricted": "This video is age-restricted, so its transcript cannot be retrieved.",
    "IpBlocked": "YouTube is blocking transcript requests from this server right now.",
    "RequestBlocked": "YouTube blocked the transcript request from this server.",
    "TooManyRequests": "YouTube is rate limiting transcript requests. Please retry shortly.",
    "CouldNotRetrieveTranscript": "The transcript could not be retrieved for this video.",
}


def _friendly_error(exc: Exception) -> TranscriptUnavailable:
    name = type(exc).__name__
    logger.info("Transcript extraction failed (%s): %s", name, exc)
    message = _ERROR_MESSAGES.get(name)
    if name in {"VideoUnavailable", "VideoUnplayable", "AgeRestricted"}:
        return VideoUnavailable(message or _ERROR_MESSAGES["VideoUnavailable"])
    if message:
        return TranscriptUnavailable(message)
    return TranscriptUnavailable(
        "We could not retrieve a transcript for this video. The video may have no captions "
        "or YouTube may be limiting access."
    )


def _list_transcripts(video_id: str):
    """Return a TranscriptList across library versions."""
    if hasattr(YouTubeTranscriptApi, "list"):  # youtube-transcript-api >= 1.0
        return YouTubeTranscriptApi().list(video_id)
    return YouTubeTranscriptApi.list_transcripts(video_id)


def _select_transcript(transcript_list):
    """Prefer manually written English, then generated English, then any language."""
    try:
        candidates = list(transcript_list)
    except TypeError:  # pragma: no cover - defensive for API changes
        candidates = []

    if not candidates:
        return None

    def score(transcript) -> tuple:
        language = (getattr(transcript, "language_code", "") or "").lower()
        is_english = language.split("-")[0] == "en"
        is_generated = bool(getattr(transcript, "is_generated", False))
        return (0 if is_english else 1, 1 if is_generated else 0)

    return sorted(candidates, key=score)[0]


def _snippets_to_dicts(fetched) -> List[dict]:
    raw_items = getattr(fetched, "snippets", fetched)
    segments: List[dict] = []
    for item in raw_items:
        if isinstance(item, dict):
            start = item.get("start", 0)
            duration = item.get("duration", 0)
            text = item.get("text", "")
        else:
            start = getattr(item, "start", 0)
            duration = getattr(item, "duration", 0)
            text = getattr(item, "text", "")
        start = float(start or 0)
        duration = float(duration or 0)
        segments.append({"start": start, "end": start + duration, "text": text})
    return segments


def _direct_fetch(video_id: str, languages: Optional[List[str]]) -> tuple:
    """Fallback path used when listing transcripts is unavailable."""
    if hasattr(YouTubeTranscriptApi, "fetch"):  # 1.x instance API
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages) if languages else api.fetch(video_id)
        return _snippets_to_dicts(fetched), getattr(fetched, "language_code", "unknown")
    fetched = (
        YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        if languages
        else YouTubeTranscriptApi.get_transcript(video_id)
    )
    return fetched, "unknown"


def fetch_transcript(video_id: str) -> Transcript:
    """Fetch and clean the best available transcript for a video."""
    language = "unknown"
    is_generated = False
    raw_segments: List[dict] = []

    try:
        transcript_list = _list_transcripts(video_id)
        chosen = _select_transcript(transcript_list)
        if chosen is not None:
            fetched = chosen.fetch()
            raw_segments = _snippets_to_dicts(fetched)
            language = getattr(chosen, "language_code", "unknown") or "unknown"
            is_generated = bool(getattr(chosen, "is_generated", False))
    except Exception as exc:
        logger.info("Listing transcripts failed for %s (%s)", video_id, type(exc).__name__)
        raise _friendly_error(exc) from exc

    if not raw_segments:
        # Some response shapes need an explicit language request.
        try:
            raw_segments, language = _direct_fetch(video_id, PREFERRED_LANGUAGES)
        except Exception as exc:
            raise _friendly_error(exc) from exc

    segments: List[TranscriptSegment] = prepare_segments(raw_segments)
    if not segments:
        raise TranscriptUnavailable("The transcript for this video is empty.")

    logger.info(
        "Extracted %s transcript segments for %s (language=%s, generated=%s)",
        len(segments),
        video_id,
        language,
        is_generated,
    )
    return Transcript(
        video_id=video_id,
        segments=segments,
        language=language,
        source="captions",
        is_generated=is_generated,
    )
