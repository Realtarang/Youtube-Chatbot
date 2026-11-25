"""Groq API service for VideoMind.

Wraps the Groq chat-completions endpoint using the configured API key.
"""

import logging
import re
from typing import Dict, List, Optional

import httpx

from app.config import settings
from app.utils.errors import AIError, AINotConfigured, RateLimited

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "openai/gpt-oss-120b"

REQUEST_TIMEOUT_SECONDS = 60.0

_RETRY_HINT_RE = re.compile(r"try again in ([\d.]+)\s*s", re.IGNORECASE)


def _retry_after(response: httpx.Response) -> Optional[float]:
    """Seconds to wait from the Retry-After header or Groq's message text."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return max(0.0, float(header))
        except ValueError:
            pass
    match = _RETRY_HINT_RE.search(response.text or "")
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except ValueError:
            return None
    return None


class GroqService:
    def __init__(self) -> None:
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model or DEFAULT_MODEL

    async def complete(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int = 1400,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        """Send a completion request to Groq and return the generated text."""
        if not self.api_key:
            raise AINotConfigured()

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Groq error %s for model %s: %s",
                exc.response.status_code,
                self.model,
                exc.response.text[:500],
            )
            if exc.response.status_code == 429:
                raise RateLimited(retry_after=_retry_after(exc.response)) from exc
            if exc.response.status_code in {401, 403}:
                raise AIError(
                    "The AI service rejected the API key. Check GROQ_API_KEY.",
                    status_code=502,
                    code="ai_auth_failed",
                ) from exc
            error_code = ""
            try:
                error_code = str((exc.response.json().get("error") or {}).get("code") or "")
            except ValueError:
                pass
            if error_code == "json_validate_failed":
                raise AIError(
                    "The AI service could not produce valid JSON. Please retry.",
                    code="ai_invalid_json",
                ) from exc
            if error_code == "model_not_found":
                raise AIError(
                    f"The model '{self.model}' is not available on this Groq account. "
                    "Set GROQ_MODEL to a chat model your key can use.",
                    code="ai_model_unavailable",
                ) from exc
            raise AIError("The AI service rejected the request. Please retry.") from exc
        except httpx.TimeoutException as exc:
            logger.error("Groq request timed out: %s", exc)
            raise AIError("The AI service timed out. Please retry.") from exc
        except httpx.HTTPError as exc:
            logger.error("Groq request failed: %s", exc)
            raise AIError("Could not reach the AI service. Please retry.") from exc

        choices = data.get("choices") or []
        if not choices:
            raise AIError("The AI service returned an empty response. Please retry.")

        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        if not content:
            raise AIError("The AI service returned an empty response. Please retry.")
        return content


# Module-level singleton, used as `from app.services.groq_service import groq_service`
groq_service = GroqService()


def get_groq_service() -> GroqService:
    """Return the shared Groq service instance."""
    return groq_service
