"""Request/response schemas for the chat endpoint."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    video_id: str = Field(..., min_length=11, max_length=11)
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(
        default=None, description="Existing chat session; omit to start a new one"
    )
    detail: Literal["brief", "balanced", "deep"] = Field(
        default="balanced", description="How much depth to put into the answer"
    )

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Ask a question about the video.")
        return cleaned


class SourceOut(BaseModel):
    chunk_index: int
    start_time: float
    end_time: float
    timestamp: str
    snippet: str
    similarity: float


class ChatResponse(BaseModel):
    video_id: str
    session_id: str
    answer: str
    sources: List[SourceOut]
    model: str
    followups: List[str] = Field(default_factory=list)
    # True when the AI call failed and the reply quotes transcript passages instead.
    degraded: bool = False


class ChatMessageOut(BaseModel):
    id: Optional[str] = None
    role: str
    content: str
    sources: List[SourceOut] = Field(default_factory=list)
    created_at: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    video_id: str
    session_id: Optional[str] = None
    messages: List[ChatMessageOut] = Field(default_factory=list)


class ClearChatResponse(BaseModel):
    session_id: str
    cleared: bool
