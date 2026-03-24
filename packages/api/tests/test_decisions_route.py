# This project was developed with assistance from AI tools.
"""Tests for decision REST endpoints."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _disable_auth(monkeypatch):
    """These tests verify routing/validation, not auth -- disable JWT checks."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "AUTH_DISABLED", True)


@pytest.fixture()
def _mock_decisions():
    """Patch get_decisions to return synthetic data."""
    decisions = [
        {
            "id": 1,
            "application_id": 100,
            "decision_type": "approved",
            "rationale": "Strong financials",
            "ai_recommendation": "Approve",
            "ai_agreement": True,
            "override_rationale": None,
            "denial_reasons": None,
            "credit_score_used": 750,
            "credit_score_source": "Experian",
            "contributing_factors": None,
            "decided_by": "uw-maria",
            "created_at": "2026-01-15T10:00:00",
        },
        {
            "id": 2,
            "application_id": 100,
            "decision_type": "conditional_approval",
            "rationale": "Pending docs",
            "ai_recommendation": None,
            "ai_agreement": None,
            "override_rationale": None,
            "denial_reasons": None,
            "credit_score_used": None,
            "credit_score_source": None,
            "contributing_factors": None,
            "decided_by": "uw-maria",
            "created_at": "2026-01-16T10:00:00",
        },
    ]
    with patch("src.routes.decisions.get_decisions", new_callable=AsyncMock) as mock:
        mock.return_value = decisions
        yield mock


@pytest.fixture()
def _mock_decisions_not_found():
    """Patch get_decisions to return None (app not found)."""
    with patch("src.routes.decisions.get_decisions", new_callable=AsyncMock) as mock:
        mock.return_value = None
        yield mock


@pytest.mark.usefixtures("_mock_decisions")
class TestListDecisions:
    """GET /api/applications/{id}/decisions"""

    def test_list_decisions_returns_data(self, client):
        resp = client.get("/api/applications/100/decisions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["id"] == 1
        assert body["data"][1]["decision_type"] == "conditional_approval"
        assert body["pagination"]["total"] == 2

    def test_list_decisions_has_pagination(self, client):
        resp = client.get("/api/applications/100/decisions")
        body = resp.json()
        assert "pagination" in body
        assert body["pagination"]["has_more"] is False


@pytest.mark.usefixtures("_mock_decisions_not_found")
class TestListDecisionsNotFound:
    def test_returns_404_when_app_not_found(self, client):
        resp = client.get("/api/applications/999/decisions")
        assert resp.status_code == 404


@pytest.mark.usefixtures("_mock_decisions")
class TestGetDecision:
    """GET /api/applications/{id}/decisions/{did}"""

    def test_get_single_decision(self, client):
        resp = client.get("/api/applications/100/decisions/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == 1
        assert body["data"]["decision_type"] == "approved"
        assert body["data"]["rationale"] == "Strong financials"

    def test_get_decision_not_found(self, client):
        resp = client.get("/api/applications/100/decisions/999")
        assert resp.status_code == 404


@pytest.mark.usefixtures("_mock_decisions_not_found")
class TestGetDecisionAppNotFound:
    def test_returns_404_when_app_not_found(self, client):
        resp = client.get("/api/applications/999/decisions/1")
        assert resp.status_code == 404
