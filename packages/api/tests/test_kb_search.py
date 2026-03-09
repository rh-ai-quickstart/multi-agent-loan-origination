# This project was developed with assistance from AI tools.
"""Tests for compliance KB vector search with tier boosting."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.compliance.knowledge_base.search import search_kb


def _make_row(chunk_text, title, section_ref, tier, effective_date, similarity):
    """Create a mock DB row for search results."""
    row = MagicMock()
    row.id = 1
    row.chunk_text = chunk_text
    row.title = title
    row.section_ref = section_ref
    row.tier = tier
    row.effective_date = effective_date
    row.similarity = similarity
    return row


class TestSearchKb:
    """Tests for vector search with tier boosting."""

    @pytest.mark.asyncio
    async def test_tier_boost_reranks_results(self, monkeypatch):
        """Tier-1 result at 0.7 similarity should outrank tier-3 at 0.85 after boost."""
        mock_session = AsyncMock()

        # tier-3 internal at 0.85, tier-1 federal at 0.7
        rows = [
            _make_row(
                "Internal policy: DTI max 40%",
                "Internal Policies",
                "DTI Limits",
                3,
                None,
                0.85,
            ),
            _make_row(
                "Federal regulation: DTI safe harbor 43%",
                "ATR/QM Rule",
                "QM Safe Harbor",
                1,
                "2014-01-10",
                0.70,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_embedding = [0.1] * 768
        import src.services.compliance.knowledge_base.search as mod

        monkeypatch.setattr(mod, "get_embeddings", AsyncMock(return_value=[fake_embedding]))

        results = await search_kb(mock_session, "DTI requirements")

        assert len(results) == 2
        # Federal (0.7 * 1.5 = 1.05) should outrank internal (0.85 * 1.0 = 0.85)
        assert results[0].tier == 1
        assert results[0].boosted_similarity == pytest.approx(0.7 * 1.5)
        assert results[1].tier == 3
        assert results[1].boosted_similarity == pytest.approx(0.85 * 1.0)

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_results(self, monkeypatch):
        """Results below threshold return empty list."""
        mock_session = AsyncMock()
        rows = [
            _make_row("Unrelated content", "Doc", None, 1, None, 0.1),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_embedding = [0.1] * 768
        import src.services.compliance.knowledge_base.search as mod

        monkeypatch.setattr(mod, "get_embeddings", AsyncMock(return_value=[fake_embedding]))

        results = await search_kb(mock_session, "something unrelated")

        assert results == []

    @pytest.mark.asyncio
    async def test_respects_top_k_limit(self, monkeypatch):
        """Only top_k results returned after boosting."""
        mock_session = AsyncMock()
        rows = [_make_row(f"Chunk {i}", "Doc", None, 1, None, 0.9 - i * 0.05) for i in range(10)]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_embedding = [0.1] * 768
        import src.services.compliance.knowledge_base.search as mod

        monkeypatch.setattr(mod, "get_embeddings", AsyncMock(return_value=[fake_embedding]))

        results = await search_kb(mock_session, "query", top_k=3)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_includes_citation_metadata(self, monkeypatch):
        """Results include source_document, section_ref, and tier_label."""
        mock_session = AsyncMock()
        rows = [
            _make_row(
                "Content about TRID timing",
                "TRID Rule",
                "Loan Estimate Timing",
                1,
                "2015-10-03",
                0.85,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_embedding = [0.1] * 768
        import src.services.compliance.knowledge_base.search as mod

        monkeypatch.setattr(mod, "get_embeddings", AsyncMock(return_value=[fake_embedding]))

        results = await search_kb(mock_session, "loan estimate timing")

        assert len(results) == 1
        r = results[0]
        assert r.source_document == "TRID Rule"
        assert r.section_ref == "Loan Estimate Timing"
        assert r.tier_label == "Federal Regulation"
        assert r.effective_date == "2015-10-03"
        assert r.similarity == pytest.approx(0.85)

    @pytest.mark.asyncio
    async def test_returns_empty_when_embedding_fails(self, monkeypatch):
        """When embedding generation fails, returns empty results."""
        mock_session = AsyncMock()

        import src.services.compliance.knowledge_base.search as mod

        monkeypatch.setattr(mod, "get_embeddings", AsyncMock(side_effect=RuntimeError("No model")))

        results = await search_kb(mock_session, "any query")

        assert results == []
