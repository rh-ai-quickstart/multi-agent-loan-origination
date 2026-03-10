# This project was developed with assistance from AI tools.
"""Tests for the embedding provider abstraction."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.inference.embeddings import (
    LocalEmbeddingProvider,
    RemoteEmbeddingProvider,
    _build_provider,
    get_embedding_provider,
    reset_embedding_provider,
)


class TestLocalEmbeddingProvider:
    """Tests for in-process sentence-transformers provider."""

    @pytest.mark.asyncio
    async def test_converts_numpy_to_python_lists(self):
        """sentence-transformers returns numpy arrays; downstream (pgvector,
        JSON serialization) needs plain Python lists of floats."""
        provider = LocalEmbeddingProvider("test-model", dimensions=4)

        fake_model = MagicMock()
        fake_model.encode.return_value = np.array(
            [
                [0.1, 0.2, 0.3, 0.4],
                [0.5, 0.6, 0.7, 0.8],
            ]
        )
        provider._model = fake_model

        result = await provider.embed(["hello", "world"])

        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[0][0], float)
        assert result[0] == pytest.approx([0.1, 0.2, 0.3, 0.4])
        assert result[1] == pytest.approx([0.5, 0.6, 0.7, 0.8])
        fake_model.encode.assert_called_once_with(
            ["hello", "world"],
            normalize_embeddings=True,
        )

    @pytest.mark.asyncio
    async def test_lazy_loads_model(self):
        """Model must not load at construction time -- only on first embed
        call. Eager loading would add ~2s to every app startup even when
        embeddings are never used (health checks, non-KB endpoints)."""
        provider = LocalEmbeddingProvider("test-model")
        assert provider._model is None

        fake_model = MagicMock()
        fake_model.encode.return_value = np.array([[0.1] * 768])

        with patch(
            "src.inference.embeddings.SentenceTransformer", return_value=fake_model
        ) as mock_cls:
            await provider.embed(["test"])
            mock_cls.assert_called_once_with("test-model", trust_remote_code=True)


class TestProviderFactory:
    """Tests for config-driven provider construction."""

    def test_builds_local_provider_from_config(self, monkeypatch):
        """provider=local must produce LocalEmbeddingProvider with correct
        model name and dimensions. Wrong dispatch = total breakage."""
        monkeypatch.setattr(
            "src.inference.embeddings.get_model_config",
            lambda tier: {
                "provider": "local",
                "model_name": "nomic-ai/nomic-embed-text-v1.5",
                "dimensions": 768,
            },
        )
        provider = _build_provider()
        assert isinstance(provider, LocalEmbeddingProvider)
        assert provider._model_name == "nomic-ai/nomic-embed-text-v1.5"
        assert provider._dimensions == 768

    def test_builds_remote_provider_from_config(self, monkeypatch):
        """provider=openai_compatible must produce RemoteEmbeddingProvider."""
        monkeypatch.setattr(
            "src.inference.embeddings.get_model_config",
            lambda tier: {
                "provider": "openai_compatible",
                "model_name": "text-embedding-3-small",
                "endpoint": "https://api.openai.com/v1",
                "api_key": "sk-test",
            },
        )
        provider = _build_provider()
        assert isinstance(provider, RemoteEmbeddingProvider)

    def test_defaults_to_remote_for_backward_compat(self, monkeypatch):
        """Existing configs without a provider key must not break --
        they should default to openai_compatible."""
        monkeypatch.setattr(
            "src.inference.embeddings.get_model_config",
            lambda tier: {
                "model_name": "text-embedding-3-small",
                "endpoint": "https://api.openai.com/v1",
            },
        )
        provider = _build_provider()
        assert isinstance(provider, RemoteEmbeddingProvider)

    def test_remote_falls_back_to_llm_base_url(self, monkeypatch):
        """When EMBEDDING_BASE_URL is not set, the remote provider must
        fall back to LLM_BASE_URL. This is the common single-endpoint
        dev setup where one LMStudio/vLLM serves everything."""
        monkeypatch.setenv("LLM_BASE_URL", "http://lmstudio:1234/v1")
        monkeypatch.setattr(
            "src.inference.embeddings.get_model_config",
            lambda tier: {
                "provider": "openai_compatible",
                "model_name": "test-embed",
                "endpoint": "",
                "api_key": "",
            },
        )
        provider = _build_provider()
        assert isinstance(provider, RemoteEmbeddingProvider)
        assert provider._client.base_url.host == "lmstudio"


class TestConfigReloadResetsProvider:
    """Config hot-reload must rebuild the embedding provider."""

    def test_new_model_name_takes_effect_after_reload(self, tmp_path):
        """When models.yaml changes on disk and config reloads, the
        embedding provider must be rebuilt with the new settings.
        Without this, the app serves stale embeddings after a model swap."""
        from src.inference import config as config_mod

        reset_embedding_provider()

        cfg = tmp_path / "models.yaml"
        cfg.write_text(
            "routing:\n  default_tier: fast_small\n"
            "models:\n  fast_small:\n    provider: openai_compatible\n"
            "    model_name: m1\n    endpoint: http://a/v1\n"
            "  embedding:\n    provider: local\n"
            "    model_name: model-a\n    dimensions: 768\n"
        )

        orig_path = config_mod._CONFIG_PATH
        config_mod._CONFIG_PATH = cfg
        config_mod._cached_config = None
        config_mod._cached_mtime = 0.0

        try:
            p1 = get_embedding_provider()
            assert p1._model_name == "model-a"

            # Rewrite config with a different model name
            time.sleep(0.05)
            cfg.write_text(
                "routing:\n  default_tier: fast_small\n"
                "models:\n  fast_small:\n    provider: openai_compatible\n"
                "    model_name: m1\n    endpoint: http://a/v1\n"
                "  embedding:\n    provider: local\n"
                "    model_name: model-b\n    dimensions: 768\n"
            )

            # Trigger config reload (reads new mtime)
            config_mod.get_config()

            p2 = get_embedding_provider()
            assert p2._model_name == "model-b"
            assert p1 is not p2
        finally:
            config_mod._CONFIG_PATH = orig_path
            config_mod._cached_config = None
            config_mod._cached_mtime = 0.0
            reset_embedding_provider()
