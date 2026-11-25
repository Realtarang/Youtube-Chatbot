"""Sentence Transformers embedding generation.

The model is loaded lazily on first use and cached for the process lifetime.
Long transcript chunks are embedded over sliding windows and mean-pooled so a
chunk's representation is not silently truncated to the model's token limit.
"""

import asyncio
import logging
import threading
from typing import List, Sequence

from app.config import settings
from app.utils.errors import EmbeddingError

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self._model = None
        self._token_limit = 256
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ model
    def _load_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer

                logger.info("Loading embedding model %s", settings.embedding_model)
                model = SentenceTransformer(settings.embedding_model)
            except Exception as exc:  # download/runtime failures
                logger.exception("Could not load embedding model")
                raise EmbeddingError(
                    "The embedding model could not be loaded. Check the server's internet "
                    "access and the EMBEDDING_MODEL setting."
                ) from exc

            token_limit = int(getattr(model, "max_seq_length", 256) or 256)
            self._token_limit = max(64, token_limit)
            self._model = model
            logger.info("Embedding model ready (max_seq_length=%s)", self._token_limit)
            return self._model

    def _dimension(self) -> int:
        model = self._load_model()
        getter = getattr(model, "get_embedding_dimension", None) or getattr(
            model, "get_sentence_embedding_dimension", None
        )
        try:
            return int(getter()) if getter else settings.embedding_dimensions
        except Exception:  # pragma: no cover - defensive
            return settings.embedding_dimensions

    # ------------------------------------------------------------- embedding
    def _windows(self, text: str) -> List[str]:
        window_chars = self._token_limit * 4
        if len(text) <= window_chars:
            return [text]
        return [text[i : i + window_chars] for i in range(0, len(text), window_chars)]

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed chunks, mean-pooling windows and L2-normalizing the result."""
        items = [text if text.strip() else " " for text in texts]
        if not items:
            return []

        model = self._load_model()
        dimension = self._dimension()
        if dimension != settings.embedding_dimensions:
            raise EmbeddingError(
                f"EMBEDDING_MODEL produces {dimension}-dimensional vectors but the database "
                f"schema expects {settings.embedding_dimensions}. Update the vector column "
                "size in database/schema.sql or choose a matching embedding model."
            )

        windows: List[str] = []
        owners: List[int] = []
        for index, text in enumerate(items):
            for window in self._windows(text):
                windows.append(window)
                owners.append(index)

        try:
            import numpy as np

            vectors = model.encode(
                windows,
                batch_size=32,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            logger.exception("Embedding generation failed")
            raise EmbeddingError() from exc

        pooled = np.zeros((len(items), dimension), dtype="float32")
        for row, owner in zip(vectors, owners):
            pooled[owner] += row
        counts = np.bincount(owners, minlength=len(items)).astype("float32")
        pooled /= counts[:, None]

        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        pooled = pooled / norms

        return [vector.tolist() for vector in pooled]

    def embed_query(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed an empty question.")
        model = self._load_model()
        try:
            vector = model.encode(
                [text.strip()[:4000]],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )[0]
        except Exception as exc:
            logger.exception("Query embedding failed")
            raise EmbeddingError("The question could not be embedded.") from exc
        return vector.tolist()

    def warm_up(self) -> None:
        """Load the model ahead of the first request so questions are fast."""
        self._load_model()

    # --------------------------------------------------------------- async
    async def aembed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return await asyncio.to_thread(self.embed_documents, list(texts))

    async def aembed_query(self, text: str) -> List[float]:
        return await asyncio.to_thread(self.embed_query, text)


embedding_service = EmbeddingService()
