"""Response schemas for summaries, quizzes and notes."""

from typing import List, Optional

from pydantic import BaseModel, Field


class SummaryTopic(BaseModel):
    title: str
    summary: str = ""
    timestamp: Optional[str] = None
    timestamp_seconds: Optional[float] = None


class SummaryResponse(BaseModel):
    video_id: str
    short_summary: str = ""
    detailed_summary: str = ""
    topics: List[SummaryTopic] = Field(default_factory=list)
    key_takeaways: List[str] = Field(default_factory=list)
    model: str


class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_index: int
    explanation: str = ""
    timestamp: Optional[str] = None
    timestamp_seconds: Optional[float] = None


class QuizResponse(BaseModel):
    video_id: str
    questions: List[QuizQuestion]
    model: str


class NotesSection(BaseModel):
    heading: str
    timestamp: Optional[str] = None
    timestamp_seconds: Optional[float] = None
    points: List[str] = Field(default_factory=list)


class NotesDefinition(BaseModel):
    term: str
    meaning: str
    timestamp: Optional[str] = None
    timestamp_seconds: Optional[float] = None


class NotesResponse(BaseModel):
    video_id: str
    title: str
    sections: List[NotesSection] = Field(default_factory=list)
    definitions: List[NotesDefinition] = Field(default_factory=list)
    key_takeaways: List[str] = Field(default_factory=list)
    model: str


class Flashcard(BaseModel):
    front: str
    back: str
    timestamp: Optional[str] = None
    timestamp_seconds: Optional[float] = None


class FlashcardsResponse(BaseModel):
    video_id: str
    cards: List[Flashcard] = Field(default_factory=list)
    model: str
