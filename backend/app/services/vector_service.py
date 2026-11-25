"""Persistence and vector search operations for videos, chunks and chats.

Uses Neon PostgreSQL (pgvector) through the database client.
"""

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.models.entities import RetrievedChunk, TextChunk
from app.utils.errors import DatabaseError

logger = logging.getLogger(__name__)

MAX_INSERT_BATCH = 50

# Columns the chat and generation paths need. Selecting these instead of `*`
# avoids shipping the full transcript JSON on every request.
VIDEO_LIGHT_COLUMNS = (
    "video_id,url,title,channel,channel_url,thumbnail_url,duration_seconds,"
    "transcript_language,transcript_source,segment_count,chunk_count,status,"
    "error_code,error_message,suggested_questions,created_at,processed_at"
)

_STOPWORDS = {
    "about", "after", "again", "against", "also", "because", "been", "before",
    "being", "between", "both", "could", "does", "doing", "during", "each",
    "explain", "from", "have", "here", "into", "just", "like", "make", "many",
    "more", "most", "much", "must", "only", "other", "over", "said", "same",
    "should", "some", "such", "tell", "than", "that", "their", "them", "then",
    "there", "these", "they", "this", "those", "through", "under", "video",
    "want", "were", "what", "when", "where", "which", "while", "will", "with",
    "would", "your",
}

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]{2,}")


def _keywords(text: str, limit: int = 4) -> List[str]:
    words: List[str] = []
    for match in _WORD_RE.findall(text or ""):
        word = match.lower()
        if word in _STOPWORDS or word.isdigit():
            continue
        if word not in words:
            words.append(word)
    words.sort(key=len, reverse=True)
    return words[:limit]


async def get_video(video_id: str) -> Optional[Dict[str, Any]]:
    return await get_db().select_one("videos", {"video_id": f"eq.{video_id}"})


async def get_video_light(video_id: str) -> Optional[Dict[str, Any]]:
    """Video row without the (potentially large) transcript payload."""
    rows = await get_db().select(
        "videos",
        columns=VIDEO_LIGHT_COLUMNS,
        filters={"video_id": f"eq.{video_id}"},
        limit=1,
    )
    return rows[0] if rows else None


async def upsert_video(record: Dict[str, Any]) -> Dict[str, Any]:
    rows = await get_db().upsert("videos", record, conflict_column="video_id")
    return rows[0] if rows else record


async def update_video(video_id: str, fields: Dict[str, Any]) -> None:
    await get_db().update("videos", {"video_id": f"eq.{video_id}"}, fields)


async def delete_video(video_id: str) -> bool:
    existing = await get_video(video_id)
    if not existing:
        return False
    # Chunks, sessions and messages cascade from the videos row.
    await get_db().delete("videos", {"video_id": f"eq.{video_id}"})
    logger.info("Deleted video %s and its associated records", video_id)
    return True


async def replace_chunks(video_id: str, chunks: List[TextChunk], embeddings: List[List[float]]) -> int:
    """Atomically-ish replace a video's chunk index.

    Chunks are deleted first so reprocessing never leaves duplicate embeddings.
    """
    db = get_db()
    await db.delete("transcript_chunks", {"video_id": f"eq.{video_id}"})

    records = [
        chunk.to_record(video_id, embedding)
        for chunk, embedding in zip(chunks, embeddings)
        if embedding
    ]
    for start in range(0, len(records), MAX_INSERT_BATCH):
        await db.insert("transcript_chunks", records[start : start + MAX_INSERT_BATCH])
    return len(records)


async def match_chunks(
    video_id: str,
    query_embedding: List[float],
    *,
    threshold: float,
    limit: int,
) -> List[RetrievedChunk]:
    # Build the cosine distance expression: 1 - (embedding <=> query_embedding)
    literal = "[" + ",".join(f"{value:.7f}" for value in query_embedding) + "]"
    rows = await get_db().fetch_all(
        """
        SELECT id, video_id, chunk_index, content, start_time, end_time,
               1 - (embedding <=> %s) as similarity
        FROM transcript_chunks
        WHERE video_id = %s AND embedding IS NOT NULL
        AND 1 - (embedding <=> %s) >= %s
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        [literal, video_id, literal, threshold, literal, limit],
    )
    return [RetrievedChunk.from_row(row) for row in (rows or [])]


async def search_chunks_lexical(
    video_id: str, query: str, *, limit: int = 8
) -> List[RetrievedChunk]:
    """Keyword retrieval used to complement (and rescue) vector search.

    Full-text search runs first; when the question only contains words Postgres
    treats as stopwords, a substring match over the significant terms backs it
    up so a question still finds transcript passages.
    """
    text = (query or "").strip()
    if not text:
        return []

    rows: List[dict] = []
    try:
        rows = await get_db().fetch_all(
            """
            SELECT id, chunk_index, content, start_time, end_time,
                   ts_rank_cd(to_tsvector('english', content),
                              websearch_to_tsquery('english', %s)) AS rank
            FROM transcript_chunks
            WHERE video_id = %s
              AND to_tsvector('english', content) @@ websearch_to_tsquery('english', %s)
            ORDER BY rank DESC, chunk_index ASC
            LIMIT %s
            """,
            [text, video_id, text, limit],
        )
    except DatabaseError:
        logger.warning("Full-text transcript search failed for %s", video_id, exc_info=True)

    results: List[RetrievedChunk] = []
    for row in rows or []:
        chunk = RetrievedChunk.from_row(row)
        rank = float(row.get("rank") or 0)
        chunk.similarity = min(0.95, 0.5 + rank * 4)
        results.append(chunk)
    if results:
        return results

    terms = _keywords(text)
    if not terms:
        return []

    clause = " OR ".join(["content ILIKE %s"] * len(terms))
    params: List[Any] = [video_id, *[f"%{term}%" for term in terms], limit]
    try:
        rows = await get_db().fetch_all(
            f"""
            SELECT id, chunk_index, content, start_time, end_time
            FROM transcript_chunks
            WHERE video_id = %s AND ({clause})
            ORDER BY chunk_index ASC
            LIMIT %s
            """,
            params,
        )
    except DatabaseError:
        logger.warning("Keyword transcript search failed for %s", video_id, exc_info=True)
        return []

    results = []
    for row in rows or []:
        chunk = RetrievedChunk.from_row(row)
        chunk.similarity = 0.35
        results.append(chunk)
    return results


async def get_all_chunks(video_id: str, limit: int = 2000) -> List[RetrievedChunk]:
    rows = await get_db().select(
        "transcript_chunks",
        columns="id,chunk_index,content,start_time,end_time",
        filters={"video_id": f"eq.{video_id}"},
        order="chunk_index.asc",
        limit=limit,
    )
    return [
        RetrievedChunk(
            id=row.get("id"),
            chunk_index=int(row.get("chunk_index", 0)),
            content=row.get("content", ""),
            start_time=float(row.get("start_time", 0)),
            end_time=float(row.get("end_time", 0)),
            similarity=0.0,
        )
        for row in rows
    ]


# --------------------------------------------------------------------- chats
def _ensure_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise DatabaseError("Invalid chat session identifier.") from exc


async def create_session(video_id: str) -> str:
    rows = await get_db().insert(
        "chat_sessions", {"video_id": video_id}, return_representation=True
    )
    if not rows:
        raise DatabaseError("Could not start a chat session.")
    return rows[0]["id"]


async def get_session(session_id: str) -> Optional[dict]:
    return await get_db().select_one("chat_sessions", {"id": f"eq.{_ensure_uuid(session_id)}"})


async def get_messages(session_id: str, limit: int = 20, newest_first: bool = False) -> List[dict]:
    """Load messages chronologically.

    ``newest_first`` selects the most recent N messages (the useful window for
    conversational memory) and still returns them oldest-to-newest.
    """
    rows = await get_db().select(
        "chat_messages",
        columns="id,role,content,sources,created_at",
        filters={"session_id": f"eq.{_ensure_uuid(session_id)}"},
        order="created_at.desc" if newest_first else "created_at.asc",
        limit=limit,
    )
    rows = rows or []
    if newest_first:
        rows.reverse()
    return rows


async def insert_message(
    session_id: str, role: str, content: str, sources: Optional[List[dict]] = None
) -> dict:
    payload = {
        "session_id": _ensure_uuid(session_id),
        "role": role,
        "content": content,
        "sources": sources or [],
    }
    rows = await get_db().insert("chat_messages", payload, return_representation=True)
    return rows[0] if rows else payload


async def insert_exchange(
    session_id: str, question: str, answer: str, sources: Optional[List[dict]] = None
) -> None:
    """Persist the question and answer in a single round trip."""
    sid = _ensure_uuid(session_id)
    await get_db().insert(
        "chat_messages",
        [
            {"session_id": sid, "role": "user", "content": question, "sources": []},
            {"session_id": sid, "role": "assistant", "content": answer, "sources": sources or []},
        ],
    )


async def clear_messages(session_id: str) -> None:
    await get_db().delete("chat_messages", {"session_id": f"eq.{_ensure_uuid(session_id)}"})


async def touch_session(session_id: str) -> None:
    from datetime import datetime, timezone

    await get_db().update(
        "chat_sessions",
        {"id": f"eq.{_ensure_uuid(session_id)}"},
        {"updated_at": datetime.now(timezone.utc).isoformat()},
    )
