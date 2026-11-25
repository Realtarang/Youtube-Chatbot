"""Prompt construction and grounded content generation.

Everything here is built from retrieved transcript chunks only. Model-provided
timestamps are snapped onto real chunk start times; timestamps that cannot be
grounded are discarded rather than shown to the user.

Transient AI failures are retried with a short backoff. If the chat model still
cannot answer, :func:`fallback_answer` returns the most relevant transcript
passages so the user gets something useful instead of an error.
"""

import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, TypeVar

from app.config import settings
from app.models.entities import ChatTurn, RetrievedChunk
from app.services import vector_service
from app.services.groq_service import groq_service
from app.utils.errors import AIError, AINotConfigured, RateLimited
from app.utils.timestamp import format_timestamp, parse_timestamp, snap_to_nearest

logger = logging.getLogger(__name__)

T = TypeVar("T")

SYSTEM_PROMPT = """You are VideoMind, an AI assistant that answers questions about a specific YouTube video.

Your answers must be based primarily and strictly on the transcript context supplied to you.

Rules:
1. Never invent information that is not present in the supplied transcript.
2. If the answer is unavailable in the transcript, clearly say that the video does not provide enough information.
3. Do not use unrelated general knowledge as if it came from the video.
4. Give clear, structured, and easy-to-understand explanations.
5. When possible, cite the relevant transcript timestamps.
6. For comparison questions, retrieve and compare the relevant parts of the transcript.
7. For summary requests, summarize only the supplied video content.
8. Maintain conversational context for follow-up questions.
9. Do not fabricate timestamps or quotations.
10. Be concise by default, but provide detailed explanations when requested.
11. Open with the direct answer, then add the reasoning or supporting detail."""

JSON_SYSTEM_PROMPT = """You are VideoMind, an assistant that analyses one YouTube video transcript.
You only use the transcript supplied by the user. You never invent facts, quotes or timestamps.
Reply with a single valid JSON object and nothing else - no markdown, no code fences, no commentary."""

ANSWER_FORMAT_INSTRUCTIONS = """Respond in plain text (no markdown headings or tables).
Cite transcript timestamps inline like [02:15] only when they appear in the context above.
If the context does not answer the question, say the video does not cover it.
Default to 2-5 short paragraphs or a compact list."""

WEAK_CONTEXT_INSTRUCTIONS = """
The retrieved passages may be only loosely related to the question. Use them only if they
genuinely answer it. If they do not, say the video does not cover this clearly and name the
closest topic it does cover, so the viewer knows what to ask instead."""

NO_CONTEXT_ANSWER = (
    "I could not find anything in this video's transcript that answers that question. "
    "Try rephrasing it, or ask about a topic the video actually covers."
)

# Errors worth retrying: rate limits, timeouts, upstream 5xx and malformed JSON.
_RETRYABLE_CODES = {"ai_error", "ai_invalid_json", "rate_limited"}
_NON_RETRYABLE_CODES = {"ai_auth_failed", "ai_not_configured", "ai_model_unavailable"}
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _is_retryable(exc: AIError) -> bool:
    if isinstance(exc, AINotConfigured):
        return False
    if exc.code in _NON_RETRYABLE_CODES:
        return False
    return exc.code in _RETRYABLE_CODES or exc.status_code in _RETRYABLE_STATUS


async def ai_retry(
    factory: Callable[[], Awaitable[T]],
    *,
    attempts: Optional[int] = None,
    base_delay: float = 0.6,
) -> T:
    """Run an AI call, retrying transient failures with exponential backoff."""
    total = max(1, attempts or settings.groq_max_attempts)
    last: Optional[AIError] = None
    for attempt in range(total):
        try:
            return await factory()
        except RateLimited as exc:
            # Tokens-per-minute limits reset on a window, so wait for the
            # provider's own hint. One wait only: a second failure falls back.
            last = exc
            if attempt >= 1:
                break
            hinted = exc.retry_after if exc.retry_after else 8.0
            delay = min(hinted + 0.5, 14.0)
        except AIError as exc:
            if not _is_retryable(exc):
                raise
            last = exc
            delay = base_delay * (2**attempt)
        if attempt == total - 1:
            break
        logger.info(
            "Retrying AI call in %.1fs after %s: %s",
            delay,
            getattr(last, "code", "error"),
            getattr(last, "message", last),
        )
        await asyncio.sleep(delay)
    assert last is not None
    raise last


# ----------------------------------------------------------------- helpers
def _chunk_text(chunk: Any) -> str:
    """Chunk text, whether it is a retrieved chunk or a freshly indexed one."""
    text = getattr(chunk, "content", None)
    if text is None:
        text = getattr(chunk, "text", "")
    return str(text or "")


def _chunk_time(chunk: Any, start: bool) -> float:
    """Start/end seconds, supporting both chunk shapes used in this project."""
    value = getattr(chunk, "start_time" if start else "end_time", None)
    if value is None:
        value = getattr(chunk, "start" if start else "end", 0)
    return float(value or 0)


def format_context(chunks: Sequence[Any], max_chars: int = 14_000) -> str:
    """Render chunks with their real time ranges."""
    blocks: List[str] = []
    used = 0
    for chunk in chunks:
        header = f"[{format_timestamp(_chunk_time(chunk, True))} - {format_timestamp(_chunk_time(chunk, False))}]"
        block = f"{header}\n{_chunk_text(chunk).strip()}"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining < 400:
                break
            block = block[:remaining]
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


def format_history(history: Sequence[ChatTurn], max_chars: int = 6000) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    used = 0
    for turn in history[-settings.max_history_messages :]:
        content = turn.content.strip()
        if not content:
            continue
        if used + len(content) > max_chars:
            break
        used += len(content)
        messages.append({"role": turn.role, "content": content})
    return messages


def extract_json(raw: str) -> Optional[dict]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _clean_str(value: Any, limit: int = 1200) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _clean_paragraphs(value: Any, limit: int = 4000) -> str:
    """Normalize spacing while keeping paragraph breaks for the UI."""
    if not isinstance(value, str):
        return ""
    text = re.sub(r"[ \t]+", " ", value)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:limit]


def _clean_list(value: Any, limit: int = 8, item_limit: int = 400) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned = [_clean_str(item, item_limit) for item in value]
    return [item for item in cleaned if item][:limit]


def _timestamp_list(chunks: Sequence[RetrievedChunk]) -> List[float]:
    return sorted({round(chunk.start_time, 2) for chunk in chunks})


def _ground_timestamp(value: Any, chunks: Sequence[RetrievedChunk]) -> Optional[float]:
    return snap_to_nearest(parse_timestamp(value), _timestamp_list(chunks), tolerance=120.0)


def _select_context(chunks: Sequence[Any], budget: Optional[int] = None) -> List[Any]:
    """Use the whole transcript when it fits, otherwise sample it evenly."""
    limit = budget or settings.generation_context_chars
    total = sum(len(_chunk_text(chunk)) for chunk in chunks)
    if total <= limit or not chunks:
        return list(chunks)

    ratio = limit / max(total, 1)
    keep = max(8, int(len(chunks) * ratio))
    step = max(1, len(chunks) // keep)
    sampled = list(chunks)[::step]
    logger.info(
        "Transcript too long (%s chars); sampling %s of %s chunks for generation",
        total,
        len(sampled),
        len(chunks),
    )
    return sampled


def _transcript_block(chunks: Sequence[Any], budget: Optional[int] = None) -> str:
    return format_context(_select_context(chunks, budget), max_chars=budget or settings.generation_context_chars)


async def _load_chunks(video_id: str) -> List[RetrievedChunk]:
    chunks = await vector_service.get_all_chunks(video_id)
    if not chunks:
        raise AIError("This video has no indexed transcript yet.", status_code=409, code="video_not_ready")
    return chunks


async def _json_call(messages: List[Dict[str, str]], *, max_tokens: int = 2200) -> dict:
    """Ask Groq for JSON and repair one malformed response before failing."""
    conversation = list(messages)
    for attempt in range(2):
        raw = await ai_retry(
            lambda: groq_service.complete(
                conversation,
                temperature=0.15,
                max_tokens=max_tokens,
                json_mode=True,
            )
        )
        parsed = extract_json(raw)
        if parsed is not None:
            return parsed
        logger.warning("Groq returned unparseable JSON (attempt %s)", attempt + 1)
        conversation = [
            *messages,
            {"role": "assistant", "content": raw[:4000]},
            {
                "role": "user",
                "content": "That reply was not valid JSON. Reply again with only a valid JSON object.",
            },
        ]
    raise AIError("The AI service returned an unreadable response. Please retry.")


# ------------------------------------------------------------------ answers
# Answer depth presets. Smaller presets also protect Groq's tokens-per-minute budget.
DEPTH_SETTINGS: Dict[str, Dict[str, Any]] = {
    "brief": {
        "top_k": 3,
        "context_chars": 4000,
        "max_tokens": 400,
        "instruction": "Answer in at most three short sentences. No lists, no preamble.",
    },
    "balanced": {
        "top_k": 4,
        "context_chars": 7000,
        "max_tokens": 900,
        "instruction": "Answer in 2-5 short paragraphs or a compact list.",
    },
    "deep": {
        "top_k": 6,
        "context_chars": 13000,
        "max_tokens": 1500,
        "instruction": (
            "Give a thorough, well-structured answer: a one-sentence summary first, then detail "
            "with short paragraphs or bullets, each backed by a transcript timestamp."
        ),
    },
}


def fallback_answer(question: str, chunks: Sequence[RetrievedChunk]) -> str:
    """Return transcript evidence when the chat model cannot answer.

    Keeps the conversation useful during an outage or a rate limit, and it is
    clearly labelled so nobody mistakes it for a generated answer.
    """
    excerpts = [chunk for chunk in chunks if _chunk_text(chunk).strip()][:3]
    if not excerpts:
        return NO_CONTEXT_ANSWER

    lines = [
        "I couldn't reach the AI service to write a full answer just now, so here are "
        "the transcript passages closest to your question:",
    ]
    for chunk in excerpts:
        snippet = re.sub(r"\s+", " ", _chunk_text(chunk).strip())
        trimmed = snippet[:420].rstrip()
        suffix = "…" if len(snippet) > 420 else ""
        lines.append(f"[{format_timestamp(_chunk_time(chunk, True))}] {trimmed}{suffix}")
    lines.append("Ask again in a moment for a written answer.")
    return "\n\n".join(lines)


async def answer_question(
    *,
    video_title: str,
    question: str,
    chunks: Sequence[RetrievedChunk],
    history: Sequence[ChatTurn] = (),
    detail: str = "balanced",
) -> str:
    if not chunks:
        return NO_CONTEXT_ANSWER

    profile = DEPTH_SETTINGS.get(detail) or DEPTH_SETTINGS["balanced"]
    context = format_context(
        chunks[: profile["top_k"]], max_chars=int(profile["context_chars"])
    )
    best_similarity = max((chunk.similarity for chunk in chunks), default=0.0)
    instructions = f"{ANSWER_FORMAT_INSTRUCTIONS}\n{profile['instruction']}"
    if best_similarity < 0.45:
        instructions = f"{instructions}{WEAK_CONTEXT_INSTRUCTIONS}"

    messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(format_history(history))
    messages.append(
        {
            "role": "user",
            "content": (
                f'Video: "{video_title}"\n\n'
                f"TRANSCRIPT CONTEXT (time ranges are real transcript timestamps):\n{context}\n\n"
                f"QUESTION: {question.strip()}\n\n"
                f"{instructions}"
            ),
        }
    )

    return await ai_retry(
        lambda: groq_service.complete(
            messages,
            temperature=settings.groq_temperature,
            max_tokens=int(profile["max_tokens"]),
            json_mode=False,
        )
    )


# -------------------------------------------------------------- suggestions
async def generate_suggestions(video_title: str, chunks: Sequence[Any]) -> List[str]:
    """Best-effort suggested questions; never fails video processing."""
    if not chunks:
        return []
    try:
        context = _transcript_block(chunks, budget=9000)
        payload = await _json_call(
            [
                {"role": "system", "content": JSON_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f'Video: "{video_title}"\n\nTranscript:\n{context}\n\n'
                        "Write 4 short, specific questions a viewer could ask about this video. "
                        'Return {"questions": ["...", "..."]}. Each question must end with a question mark.'
                    ),
                },
            ],
            max_tokens=500,
        )
        questions = _clean_list(payload.get("questions"), limit=5, item_limit=180)
        return [q if q.endswith("?") else f"{q}?" for q in questions]
    except Exception as exc:
        logger.info("Suggested question generation skipped: %s", exc)
        return []


# ------------------------------------------------------------------ summary
async def generate_summary(video: dict) -> dict:
    chunks = await _load_chunks(video["video_id"])
    context = _transcript_block(chunks)
    payload = await _json_call(
        [
            {"role": "system", "content": JSON_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f'Video: "{video.get("title")}"\n\nTranscript:\n{context}\n\n'
                    "Summarize ONLY this transcript. Return JSON with keys:\n"
                    '"short_summary": 2-3 sentences,\n'
                    '"detailed_summary": 2-3 paragraphs as one string,\n'
                    '"topics": [{"title": "...", "summary": "1-2 sentences", "timestamp": "MM:SS"}],\n'
                    '"key_takeaways": ["...", "..."] (3-5 items).\n'
                    "Every timestamp must come from the transcript time ranges above."
                ),
            },
        ]
    )

    topics = []
    for item in payload.get("topics") or []:
        if not isinstance(item, dict):
            continue
        title = _clean_str(item.get("title"), 160)
        if not title:
            continue
        seconds = _ground_timestamp(item.get("timestamp"), chunks)
        topics.append(
            {
                "title": title,
                "summary": _clean_str(item.get("summary"), 600),
                "timestamp_seconds": seconds,
                "timestamp": format_timestamp(seconds) if seconds is not None else None,
            }
        )

    short_summary = _clean_str(payload.get("short_summary"), 1000)
    detailed_summary = _clean_paragraphs(payload.get("detailed_summary"))
    if not short_summary and not detailed_summary:
        raise AIError("The AI service returned an empty summary. Please retry.")

    return {
        "video_id": video["video_id"],
        "short_summary": short_summary,
        "detailed_summary": detailed_summary,
        "topics": topics[:8],
        "key_takeaways": _clean_list(payload.get("key_takeaways"), limit=6),
        "model": settings.groq_model,
    }


# --------------------------------------------------------------------- quiz
async def generate_quiz(video: dict, count: int = 5) -> dict:
    chunks = await _load_chunks(video["video_id"])
    context = _transcript_block(chunks)
    payload = await _json_call(
        [
            {"role": "system", "content": JSON_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f'Video: "{video.get("title")}"\n\nTranscript:\n{context}\n\n'
                    f"Create {count} multiple-choice questions answerable ONLY from this transcript. "
                    'Return JSON: {"questions": [{"question": "...", '
                    '"options": ["...", "...", "...", "..."], "correct_index": 0, '
                    '"explanation": "why the answer is correct, using the transcript", '
                    '"timestamp": "MM:SS"}]}. '
                    "Each question must have exactly 4 options and the timestamp of the relevant moment."
                ),
            },
        ],
        max_tokens=2600,
    )

    questions = []
    for item in payload.get("questions") or []:
        if not isinstance(item, dict):
            continue
        question = _clean_str(item.get("question"), 400)
        options = _clean_list(item.get("options"), limit=4, item_limit=240)
        correct_index = item.get("correct_index")
        if isinstance(correct_index, str) and correct_index.isdigit():
            correct_index = int(correct_index)
        if not question or len(options) != 4 or not isinstance(correct_index, int):
            continue
        if not 0 <= correct_index <= 3:
            continue
        seconds = _ground_timestamp(item.get("timestamp"), chunks)
        questions.append(
            {
                "question": question,
                "options": options,
                "correct_index": correct_index,
                "explanation": _clean_str(item.get("explanation"), 700),
                "timestamp_seconds": seconds,
                "timestamp": format_timestamp(seconds) if seconds is not None else None,
            }
        )

    if not questions:
        raise AIError("The AI service could not produce a valid quiz. Please retry.")

    return {
        "video_id": video["video_id"],
        "questions": questions[:count],
        "model": settings.groq_model,
    }


# -------------------------------------------------------------------- notes
async def generate_notes(video: dict) -> dict:
    chunks = await _load_chunks(video["video_id"])
    context = _transcript_block(chunks)
    payload = await _json_call(
        [
            {"role": "system", "content": JSON_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f'Video: "{video.get("title")}"\n\nTranscript:\n{context}\n\n'
                    "Write structured study notes using ONLY this transcript. Return JSON:\n"
                    '{"title": "...", "sections": [{"heading": "...", "timestamp": "MM:SS", '
                    '"points": ["...", "..."]}], '
                    '"definitions": [{"term": "...", "meaning": "...", "timestamp": "MM:SS"}], '
                    '"key_takeaways": ["..."]}.\n'
                    "Use 4-8 sections, 2-5 points each. Only define terms the video actually defines."
                ),
            },
        ],
        max_tokens=2800,
    )

    sections = []
    for item in payload.get("sections") or []:
        if not isinstance(item, dict):
            continue
        heading = _clean_str(item.get("heading"), 160)
        points = _clean_list(item.get("points"), limit=8, item_limit=500)
        if not heading or not points:
            continue
        seconds = _ground_timestamp(item.get("timestamp"), chunks)
        sections.append(
            {
                "heading": heading,
                "timestamp_seconds": seconds,
                "timestamp": format_timestamp(seconds) if seconds is not None else None,
                "points": points,
            }
        )

    definitions = []
    for item in payload.get("definitions") or []:
        if not isinstance(item, dict):
            continue
        term = _clean_str(item.get("term"), 120)
        meaning = _clean_str(item.get("meaning"), 500)
        if not term or not meaning:
            continue
        seconds = _ground_timestamp(item.get("timestamp"), chunks)
        definitions.append(
            {
                "term": term,
                "meaning": meaning,
                "timestamp_seconds": seconds,
                "timestamp": format_timestamp(seconds) if seconds is not None else None,
            }
        )

    if not sections:
        raise AIError("The AI service could not produce notes for this video. Please retry.")

    return {
        "video_id": video["video_id"],
        "title": _clean_str(payload.get("title"), 200) or video.get("title") or "Video notes",
        "sections": sections[:10],
        "definitions": definitions[:10],
        "key_takeaways": _clean_list(payload.get("key_takeaways"), limit=6),
        "model": settings.groq_model,
    }


# ----------------------------------------------------------------- flashcards
async def generate_flashcards(video: dict, count: int = 8) -> dict:
    chunks = await _load_chunks(video["video_id"])
    context = _transcript_block(chunks)
    payload = await _json_call(
        [
            {"role": "system", "content": JSON_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f'Video: "{video.get("title")}"\n\nTranscript:\n{context}\n\n'
                    f"Create {count} study flashcards answerable ONLY from this transcript. "
                    'Return JSON: {"cards": [{"front": "a question or term", '
                    '"back": "concise answer in at most 3 sentences", "timestamp": "MM:SS"}]}. '
                    "Fronts must be specific questions, never yes/no. "
                    "Each answer must stand on its own without the video."
                ),
            },
        ],
        max_tokens=2200,
    )

    cards = []
    for item in payload.get("cards") or []:
        if not isinstance(item, dict):
            continue
        front = _clean_str(item.get("front"), 260)
        back = _clean_str(item.get("back"), 800)
        if not front or not back:
            continue
        seconds = _ground_timestamp(item.get("timestamp"), chunks)
        cards.append(
            {
                "front": front,
                "back": back,
                "timestamp_seconds": seconds,
                "timestamp": format_timestamp(seconds) if seconds is not None else None,
            }
        )

    if not cards:
        raise AIError("The AI service could not build flashcards for this video. Please retry.")

    return {
        "video_id": video["video_id"],
        "cards": cards[:count],
        "model": settings.groq_model,
    }
