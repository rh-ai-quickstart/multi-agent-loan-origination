# This project was developed with assistance from AI tools.
"""Inference module -- LLM client and config loading."""

from .client import get_completion, get_streaming_completion
from .config import get_model_config

__all__ = [
    "get_completion",
    "get_model_config",
    "get_streaming_completion",
]
