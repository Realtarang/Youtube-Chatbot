"""Configuration for VideoMind using pydantic-settings.

Env vars are read from backend/.env at import time. Attribute names are
lower-case (pydantic-settings convention); where the env var name differs
from the attribute name, a `validation_alias` maps it.
"""

from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve backend/.env relative to this file (backend/app/config.py)
_ENV_FILE = str(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------------------------------------------------------- Groq
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_temperature: float = 0.2
    groq_max_tokens: int = 900
    groq_max_attempts: int = 3

    # ----------------------------------------------------- Supabase (legacy)
    supabase_url: str = ""
    supabase_key: str = ""

    # ---------------------------------------------------- Neon PostgreSQL
    neon_dsn: str = ""

    # ----------------------------------------------------------- Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # -------------------------------------------------------------- Chunking
    chunk_size_chars: int = Field(
        default=3200,
        validation_alias=AliasChoices("CHUNK_SIZE_CHARS", "CHUNK_SIZE_TOKENS"),
    )
    chunk_overlap_chars: int = Field(
        default=600,
        validation_alias=AliasChoices("CHUNK_OVERLAP_CHARS", "CHUNK_OVERLAP_TOKENS"),
    )

    # ----------------------------------------------------------- Retrieval
    retrieval_top_k: int = 4
    # Below this many vector hits, relax the threshold and merge keyword matches.
    retrieval_min_chunks: int = 3
    similarity_threshold: float = 0.25
    # Kept compact: Groq's on-demand tier limits tokens per minute, and a smaller
    # prompt both answers faster and avoids rate limits on long videos.
    generation_context_chars: int = 7000
    max_history_messages: int = 4

    # ------------------------------------------------------------- Caching
    answer_cache_entries: int = 256
    answer_cache_ttl_seconds: float = 900.0

    # ------------------------------------------------------------ Whisper
    enable_whisper_fallback: bool = False
    whisper_model: str = "whisper-large-v3-turbo"

    # ------------------------------------------------------------- Timing
    http_timeout_seconds: float = 30.0
    ytdlp_timeout_seconds: float = 30.0
    stale_processing_seconds: float = 900.0
    warm_up_on_startup: bool = True

    # -------------------------------------------------------------- CORS
    frontend_url: str = "http://localhost:5173"

    # --------------------------------------------------------------- Misc
    log_level: str = "INFO"

    # ---------------------------------------------------------- validators
    @field_validator("neon_dsn", mode="before")
    @classmethod
    def _normalize_dsn(cls, value: object) -> object:
        """Accept a pasted `psql 'postgresql://...'` string or a bare URL."""
        if not isinstance(value, str):
            return value
        dsn = value.strip()
        # Strip a leading `psql` command token.
        if dsn.lower().startswith("psql"):
            dsn = dsn[4:].strip()
        # Strip surrounding single/double quotes.
        if len(dsn) >= 2 and dsn[0] in {"'", '"'} and dsn[-1] == dsn[0]:
            dsn = dsn[1:-1]
        # Drop query params that older libpq builds reject (channel_binding).
        try:
            parts = urlsplit(dsn)
            if parts.scheme:
                query = [
                    (key, val)
                    for key, val in parse_qsl(parts.query, keep_blank_values=True)
                    if key != "channel_binding"
                ]
                dsn = urlunsplit(
                    (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
                )
        except ValueError:
            pass
        return dsn

    # ------------------------------------------------------------ helpers
    @property
    def supabase_configured(self) -> bool:
        """True if the legacy Supabase URL and key are set."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def neon_configured(self) -> bool:
        """True if the Neon connection string is set."""
        return bool(self.neon_dsn)

    @property
    def groq_configured(self) -> bool:
        """True if the Groq API key is set."""
        return bool(self.groq_api_key)

    @property
    def cors_origins(self) -> List[str]:
        """Allowed browser origins parsed from FRONTEND_URL (comma-separated)."""
        return [origin.strip() for origin in self.frontend_url.split(",") if origin.strip()]

    @property
    def cors_allow_origin_regex(self) -> Optional[str]:
        return None

    def missing_services(self) -> List[str]:
        """Return the names of required services that are not configured."""
        missing: List[str] = []
        if not self.neon_configured:
            missing.append("database")
        if not self.groq_configured:
            missing.append("groq")
        return missing


# Module-level instance for `from app.config import settings`
settings = Settings()
