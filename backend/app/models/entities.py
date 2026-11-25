"""Domain models shared by the services."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VideoMetadata:
    video_id: str
    url: str
    title: str
    channel: Optional[str] = None
    channel_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    description: Optional[str] = None


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return {"start": round(self.start, 3), "end": round(self.end, 3), "text": self.text}

    @classmethod
    def from_dict(cls, payload: dict) -> "TranscriptSegment":
        start = float(payload.get("start", 0))
        end = float(payload.get("end", start))
        return cls(start=start, end=max(start, end), text=str(payload.get("text", "")))


@dataclass
class Transcript:
    video_id: str
    segments: List[TranscriptSegment]
    language: str = "unknown"
    language_name: Optional[str] = None
    source: str = "captions"  # "captions" | "whisper"
    is_generated: bool = False

    @property
    def duration_seconds(self) -> Optional[float]:
        return self.segments[-1].end if self.segments else None

    @property
    def text_length(self) -> int:
        return sum(len(segment.text) for segment in self.segments)


@dataclass
class TextChunk:
    index: int
    text: str
    start: float
    end: float
    token_estimate: int = 0

    def to_record(self, video_id: str, embedding: List[float]) -> dict:
        return {
            "video_id": video_id,
            "chunk_index": self.index,
            "content": self.text,
            "start_time": round(self.start, 3),
            "end_time": round(self.end, 3),
            "token_estimate": self.token_estimate,
            "embedding": _vector_literal(embedding),
        }


@dataclass
class RetrievedChunk:
    chunk_index: int
    content: str
    start_time: float
    end_time: float
    similarity: float
    id: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "RetrievedChunk":
        return cls(
            id=row.get("id"),
            chunk_index=int(row.get("chunk_index", 0)),
            content=row.get("content", ""),
            start_time=float(row.get("start_time", 0)),
            end_time=float(row.get("end_time", 0)),
            similarity=float(row.get("similarity", 0)),
        )


@dataclass
class ChatTurn:
    role: str
    content: str


@dataclass
class VideoRecord:
    video_id: str
    url: str
    title: str
    status: str = "processing"
    channel: Optional[str] = None
    channel_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    description: Optional[str] = None
    transcript_language: Optional[str] = None
    transcript_source: Optional[str] = None
    segment_count: int = 0
    chunk_count: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    suggested_questions: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    processed_at: Optional[str] = None


def _vector_literal(embedding: List[float]) -> str:
    """pgvector text literal. PostgREST casts this to the ``vector`` column type."""
    return "[" + ",".join(f"{value:.7f}" for value in embedding) + "]"
