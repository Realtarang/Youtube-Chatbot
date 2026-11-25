"""Timestamp formatting, parsing and grounding helpers."""

import re
from typing import Iterable, Optional

_TIMESTAMP_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?$")


def format_timestamp(seconds: Optional[float]) -> str:
    """Format seconds as MM:SS, or HH:MM:SS for videos over an hour."""
    if seconds is None:
        return "00:00"
    total = max(0, int(round(float(seconds))))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_timestamp(value: object) -> Optional[float]:
    """Parse ``MM:SS`` / ``HH:MM:SS`` / seconds into a float. Returns None when invalid."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.replace(".", "", 1).isdigit():
        return max(0.0, float(raw))
    match = _TIMESTAMP_RE.match(raw)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = float(f"0.{match.group(4)}") if match.group(4) else 0.0
    return hours * 3600 + minutes * 60 + seconds + millis


def snap_to_nearest(
    value: Optional[float],
    candidates: Iterable[float],
    tolerance: float = 90.0,
) -> Optional[float]:
    """Ground a model-produced timestamp onto a real transcript timestamp.

    Hallucinated or out-of-range timestamps are discarded instead of shown,
    which keeps every citation traceable to an actual chunk.
    """
    if value is None:
        return None
    options = [float(c) for c in candidates]
    if not options:
        return None
    closest = min(options, key=lambda item: abs(item - value))
    if abs(closest - value) > tolerance:
        return None
    return closest
