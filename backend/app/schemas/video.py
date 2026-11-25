"""Request/response schemas for video processing."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class ProcessVideoRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=512, description="YouTube video URL")

    @field_validator("url")
    @classmethod
    def strip_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A YouTube video URL is required.")
        return cleaned


class VideoOut(BaseModel):
    video_id: str
    url: str
    title: str
    channel: Optional[str] = None
    channel_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    transcript_language: Optional[str] = None
    transcript_source: Optional[str] = None
    transcript_available: bool = True
    segment_count: int = 0
    chunk_count: int = 0
    status: str = "processing"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    suggested_questions: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    processed_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "VideoOut":
        status = str(row.get("status") or "processing")
        if status not in {"processing", "ready", "failed"}:
            status = "processing"
        return cls(
            video_id=row["video_id"],
            url=row.get("url") or f"https://www.youtube.com/watch?v={row['video_id']}",
            title=row.get("title") or f"YouTube video {row['video_id']}",
            channel=row.get("channel"),
            channel_url=row.get("channel_url"),
            thumbnail_url=row.get("thumbnail_url"),
            duration_seconds=row.get("duration_seconds"),
            transcript_language=row.get("transcript_language"),
            transcript_source=row.get("transcript_source"),
            transcript_available=bool(int(row.get("segment_count") or 0) > 0),
            segment_count=int(row.get("segment_count") or 0),
            chunk_count=int(row.get("chunk_count") or 0),
            status=status,
            error_code=row.get("error_code"),
            error_message=row.get("error_message"),
            suggested_questions=[str(q) for q in (row.get("suggested_questions") or [])],
            created_at=row.get("created_at"),
            processed_at=row.get("processed_at"),
        )


class ProcessVideoResponse(BaseModel):
    video: VideoOut
    status: str
    already_processed: bool = False


class TranscriptSegmentOut(BaseModel):
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    video_id: str
    title: str
    language: Optional[str] = None
    source: Optional[str] = None
    duration_seconds: Optional[float] = None
    segments: List[TranscriptSegmentOut]

    @classmethod
    def from_row(cls, row: dict, segments: List[dict]) -> "TranscriptResponse":
        return cls(
            video_id=row["video_id"],
            title=row.get("title") or "Untitled video",
            language=row.get("transcript_language"),
            source=row.get("transcript_source"),
            duration_seconds=row.get("duration_seconds"),
            segments=[TranscriptSegmentOut(**segment) for segment in segments],
        )


class DeleteVideoResponse(BaseModel):
    video_id: str
    deleted: bool


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Type something to search for.")
        return cleaned


class SearchHit(BaseModel):
    chunk_index: int
    start_time: float
    end_time: float
    timestamp: str
    snippet: str
    score: float


class SearchResponse(BaseModel):
    video_id: str
    query: str
    results: List[SearchHit] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    services: dict[str, Any]
    embedding_model: str
    chat_model: str
