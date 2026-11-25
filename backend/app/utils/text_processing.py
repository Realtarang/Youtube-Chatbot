"""Transcript cleaning and timestamp-aware chunking."""

import html
import re
from typing import Iterable, List, Sequence, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.entities import TextChunk, TranscriptSegment

_WHITESPACE_RE = re.compile(r"\s+")
_INLINE_TIMESTAMP_RE = re.compile(r"\[?\b\d{1,2}:\d{2}(?::\d{2})?\b\]?\s*")
_CHARS_PER_TOKEN = 4


def clean_segment_text(text: str) -> str:
    """Normalize a single caption line while keeping sentence boundaries."""
    if not text:
        return ""
    cleaned = html.unescape(text)
    cleaned = cleaned.replace("\u200b", " ").replace("\xa0", " ")
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    # Captions sometimes arrive with baked-in cue timestamps; drop them.
    cleaned = _INLINE_TIMESTAMP_RE.sub(" ", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def prepare_segments(raw_segments: Iterable[dict]) -> List[TranscriptSegment]:
    """Clean raw caption segments, dropping empties and duplicate consecutive lines."""
    prepared: List[TranscriptSegment] = []
    previous_text = ""
    for raw in raw_segments:
        text = clean_segment_text(str(raw.get("text", "")))
        if not text:
            continue
        if text == previous_text:
            # Rolling captions often repeat the same line; extend the previous segment.
            if prepared:
                prepared[-1].end = max(prepared[-1].end, float(raw.get("end", prepared[-1].end)))
            continue
        start = max(0.0, float(raw.get("start", 0)))
        end = max(start, float(raw.get("end", start)))
        prepared.append(TranscriptSegment(start=start, end=end, text=text))
        previous_text = text
    return prepared


def _build_text(segments: Sequence[TranscriptSegment]) -> Tuple[str, List[Tuple[int, int, int]]]:
    """Concatenate segments into one string and record character spans."""
    parts: List[str] = []
    spans: List[Tuple[int, int, int]] = []
    cursor = 0
    for index, segment in enumerate(segments):
        if parts:
            parts.append("\n")
            cursor += 1
        start = cursor
        parts.append(segment.text)
        cursor += len(segment.text)
        spans.append((start, cursor, index))
    return "".join(parts), spans


def _span_bounds(
    spans: Sequence[Tuple[int, int, int]], start: int, end: int
) -> Tuple[int, int]:
    indices = [index for (char_start, char_end, index) in spans if char_end > start and char_start < end]
    if not indices:
        return -1, -1
    return indices[0], indices[-1]


def chunk_transcript(
    segments: Sequence[TranscriptSegment],
    chunk_size_chars: int,
    chunk_overlap_chars: int,
) -> List[TextChunk]:
    """Split a transcript into overlapping chunks that keep accurate timestamps.

    LangChain's ``RecursiveCharacterTextSplitter`` handles the text boundaries;
    we map every resulting character range back onto the caption segments that
    produced it, so a chunk's ``start``/``end`` always come from real caption
    metadata rather than from an estimate.
    """
    if not segments:
        return []

    text, spans = _build_text(segments)
    if not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size_chars,
        chunk_overlap=min(chunk_overlap_chars, max(0, chunk_size_chars - 100)),
        separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
        keep_separator=True,
    )

    chunks: List[TextChunk] = []
    cursor = 0
    for piece in splitter.split_text(text):
        body = piece.strip()
        if not body:
            continue

        offset = text.find(body, cursor)
        if offset == -1:
            offset = text.find(body)
        if offset == -1:
            continue
        cursor = offset + 1

        first, last = _span_bounds(spans, offset, offset + len(body))
        if first == -1:
            continue

        start_time = segments[first].start
        end_time = max(start_time, segments[last].end)
        chunks.append(
            TextChunk(
                index=len(chunks),
                text=body,
                start=start_time,
                end=end_time,
                token_estimate=max(1, len(body) // _CHARS_PER_TOKEN),
            )
        )

    return chunks


def build_full_text(segments: Sequence[TranscriptSegment]) -> str:
    return "\n".join(segment.text for segment in segments if segment.text)
