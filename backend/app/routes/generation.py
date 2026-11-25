"""Summary, quiz and structured-notes endpoints."""

import logging

from fastapi import APIRouter, Query

from app.routes.chat import get_ready_video
from app.schemas.generation import (
    FlashcardsResponse,
    NotesResponse,
    QuizResponse,
    SummaryResponse,
)
from app.services import generation_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video", tags=["generation"])


@router.post("/{video_id}/summary", response_model=SummaryResponse, summary="Summarize the video")
async def summarize_video(video_id: str):
    video = await get_ready_video(video_id)
    return await generation_service.generate_summary(video)


@router.post(
    "/{video_id}/quiz",
    response_model=QuizResponse,
    summary="Generate multiple-choice questions from the transcript",
)
async def quiz_video(video_id: str, count: int = Query(default=5, ge=3, le=10)):
    video = await get_ready_video(video_id)
    return await generation_service.generate_quiz(video, count=count)


@router.post(
    "/{video_id}/notes",
    response_model=NotesResponse,
    summary="Generate structured notes from the transcript",
)
async def notes_video(video_id: str):
    video = await get_ready_video(video_id)
    return await generation_service.generate_notes(video)


@router.post(
    "/{video_id}/flashcards",
    response_model=FlashcardsResponse,
    summary="Generate study flashcards with review timestamps",
)
async def flashcards_video(video_id: str, count: int = Query(default=8, ge=4, le=15)):
    video = await get_ready_video(video_id)
    return await generation_service.generate_flashcards(video, count=count)
