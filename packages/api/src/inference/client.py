# This project was developed with assistance from AI tools.
"""Thin OpenAI-compatible LLM client.

Wraps the openai Python SDK with configurable base_url so it works
against any OpenAI-compatible endpoint (OpenAI, vLLM, LlamaStack, etc.).
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from .config import get_model_config

logger = logging.getLogger(__name__)

# Per-tier client cache (avoids re-creating HTTP connections)
_clients: dict[str, AsyncOpenAI] = {}


def _get_client(tier: str) -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client for the given model tier."""
    if tier not in _clients:
        model_cfg = get_model_config(tier)
        _clients[tier] = AsyncOpenAI(
            base_url=model_cfg["endpoint"],
            api_key=model_cfg.get("api_key", "not-needed"),
        )
    return _clients[tier]


def clear_client_cache() -> None:
    """Clear cached clients (useful after config reload)."""
    _clients.clear()


async def get_completion(
    messages: list[dict[str, str]],
    tier: str = "llm",
    **kwargs: Any,
) -> str:
    """Get a non-streaming completion from the specified model tier."""
    client = _get_client(tier)
    model_cfg = get_model_config(tier)

    response = await client.chat.completions.create(
        model=model_cfg["model_name"],
        messages=messages,
        **kwargs,
    )
    return response.choices[0].message.content or ""


async def get_embeddings(texts: list[str], tier: str = "embedding") -> list[list[float]]:
    """Get embeddings for a list of texts from the configured provider.

    The provider (local sentence-transformers or remote OpenAI-compatible)
    is determined by the ``embedding`` model config in ``config/models.yaml``.
    """
    from .embeddings import get_embedding_provider

    provider = get_embedding_provider()
    return await provider.embed(texts)


async def get_streaming_completion(
    messages: list[dict[str, str]],
    tier: str = "llm",
    **kwargs: Any,
) -> AsyncIterator[str]:
    """Get a streaming completion, yielding content deltas."""
    client = _get_client(tier)
    model_cfg = get_model_config(tier)

    stream = await client.chat.completions.create(
        model=model_cfg["model_name"],
        messages=messages,
        stream=True,
        **kwargs,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
