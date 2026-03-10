# This project was developed with assistance from AI tools.
"""Embedding provider abstraction.

Supports two providers:
- ``local``: in-process inference via sentence-transformers (no external service needed).
- ``openai_compatible``: remote call to any OpenAI-compatible ``/v1/embeddings`` endpoint.

The active provider is determined by the ``embedding`` model config in
``config/models.yaml``.  Set ``provider: local`` to run the model in-process,
or ``provider: openai_compatible`` to delegate to a remote server.
"""

import logging
import os
from abc import ABC, abstractmethod

import numpy as np
from sentence_transformers import SentenceTransformer

from .config import get_model_config

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Common interface for embedding providers."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for *texts*."""


class LocalEmbeddingProvider(EmbeddingProvider):
    """In-process embedding using sentence-transformers.

    The model is loaded lazily on first call and cached for the process
    lifetime.  CPU inference is used by default; nomic-embed-text-v1.5
    (~270 MB) loads in ~2 s and embeds a single query in < 50 ms on CPU.
    """

    def __init__(self, model_name: str, dimensions: int = 768) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self._model: SentenceTransformer | None = None

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading local embedding model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name, trust_remote_code=True)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        # sentence-transformers returns numpy ndarray
        vectors = model.encode(texts, normalize_embeddings=True)
        if isinstance(vectors, np.ndarray):
            return vectors.tolist()
        return [v.tolist() if hasattr(v, "tolist") else list(v) for v in vectors]


class RemoteEmbeddingProvider(EmbeddingProvider):
    """Embedding via an OpenAI-compatible ``/v1/embeddings`` endpoint."""

    def __init__(self, endpoint: str, model_name: str, api_key: str = "not-needed") -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(base_url=endpoint, api_key=api_key)
        self._model_name = model_name

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model_name,
            input=texts,
        )
        return [item.embedding for item in response.data]


# --- singleton management ---

_provider: EmbeddingProvider | None = None


def _build_provider() -> EmbeddingProvider:
    """Construct the provider from the current ``embedding`` model config."""
    cfg = get_model_config("embedding")
    provider_type = cfg.get("provider", "openai_compatible")

    if provider_type == "local":
        return LocalEmbeddingProvider(
            model_name=cfg["model_name"],
            dimensions=cfg.get("dimensions", 768),
        )

    # Default: openai_compatible (covers vLLM, LMStudio, TEI, etc.)
    # Fall back to LLM_BASE_URL / LLM_API_KEY when embedding-specific vars
    # are not set (keeps the common single-endpoint dev setup working).
    endpoint = cfg.get("endpoint") or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    api_key = cfg.get("api_key") or os.environ.get("LLM_API_KEY", "not-needed")
    return RemoteEmbeddingProvider(
        endpoint=endpoint,
        model_name=cfg["model_name"],
        api_key=api_key,
    )


def get_embedding_provider() -> EmbeddingProvider:
    """Return the cached embedding provider, building it on first access."""
    global _provider  # noqa: PLW0603
    if _provider is None:
        _provider = _build_provider()
    return _provider


def reset_embedding_provider() -> None:
    """Discard the cached provider (e.g. after config reload)."""
    global _provider  # noqa: PLW0603
    _provider = None
