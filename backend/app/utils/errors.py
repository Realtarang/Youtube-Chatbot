"""Typed application errors mapped to clean HTTP responses."""

from typing import Any, Dict, Optional


class AppError(Exception):
    """An expected, user-facing failure.

    The API layer converts this into ``{"error": {"code", "message"}}``
    with the given status code so the frontend can show a useful message
    instead of a raw backend traceback.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "internal_error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class InvalidYouTubeUrl(AppError):
    def __init__(self, message: str = "That does not look like a valid YouTube video URL."):
        super().__init__(message, code="invalid_youtube_url", status_code=400)


class VideoNotFound(AppError):
    def __init__(self, message: str = "That video has not been processed yet."):
        super().__init__(message, code="video_not_found", status_code=404)


class TranscriptUnavailable(AppError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            code="transcript_unavailable",
            status_code=422,
            details=details,
        )


class VideoUnavailable(AppError):
    def __init__(self, message: str):
        super().__init__(message, code="video_unavailable", status_code=422)


class DatabaseNotConfigured(AppError):
    def __init__(self) -> None:
        super().__init__(
            "The database is not configured. Set SUPABASE_URL and SUPABASE_KEY "
            "in the backend environment.",
            code="database_not_configured",
            status_code=503,
        )


class DatabaseError(AppError):
    def __init__(self, message: str = "The database request failed. Please try again."):
        super().__init__(message, code="database_error", status_code=502)


class AINotConfigured(AppError):
    def __init__(self) -> None:
        super().__init__(
            "The AI service is not configured. Set GROQ_API_KEY in the backend environment.",
            code="ai_not_configured",
            status_code=503,
        )


class AIError(AppError):
    def __init__(self, message: str, *, status_code: int = 502, code: str = "ai_error"):
        super().__init__(message, code=code, status_code=status_code)


class RateLimited(AIError):
    def __init__(
        self,
        message: str = "The AI service is rate limited. Please retry in a moment.",
        retry_after: Optional[float] = None,
    ):
        super().__init__(message, status_code=429, code="rate_limited")
        # Seconds the provider asked us to wait, when it says so.
        self.retry_after = retry_after


class EmbeddingError(AppError):
    def __init__(self, message: str = "Could not generate embeddings for this video."):
        super().__init__(message, code="embedding_error", status_code=500)


class VideoNotReady(AppError):
    def __init__(self, status: str = "processing"):
        message = (
            "This video is still being processed. Try again once indexing finishes."
            if status == "processing"
            else "This video could not be processed. Reprocess it from the URL input."
        )
        super().__init__(message, code="video_not_ready", status_code=409, details={"status": status})
