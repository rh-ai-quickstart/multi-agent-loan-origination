# This project was developed with assistance from AI tools.
"""Functional tests: Model monitoring endpoint access control.

Model monitoring endpoints are CEO/ADMIN-only. Other personas must get 403.
Data comes from LangFuse (not DB), so the mock DB session is a no-op here --
the real boundary to test is role gating.
"""

from unittest.mock import AsyncMock, patch

import pytest

from .mock_db import make_mock_session
from .personas import borrower_sarah, ceo, loan_officer, underwriter

pytestmark = pytest.mark.functional

_MONITORING_ENDPOINTS = [
    "/api/analytics/model-monitoring",
    "/api/analytics/model-monitoring/latency",
    "/api/analytics/model-monitoring/tokens",
    "/api/analytics/model-monitoring/errors",
    "/api/analytics/model-monitoring/routing",
]


class TestModelMonitoringRoleGating:
    """Only CEO and ADMIN can access model monitoring endpoints."""

    def test_borrower_denied_on_all_endpoints(self, monkeypatch, make_client):
        """Borrower gets 403 on every model monitoring endpoint."""
        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        client = make_client(borrower_sarah(), make_mock_session())
        for path in _MONITORING_ENDPOINTS:
            resp = client.get(path)
            assert resp.status_code == 403, f"Expected 403 on {path}, got {resp.status_code}"

    def test_loan_officer_denied(self, monkeypatch, make_client):
        """Loan officer gets 403 on model monitoring."""
        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        client = make_client(loan_officer(), make_mock_session())
        resp = client.get("/api/analytics/model-monitoring")
        assert resp.status_code == 403

    def test_underwriter_denied(self, monkeypatch, make_client):
        """Underwriter gets 403 on model monitoring."""
        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        client = make_client(underwriter(), make_mock_session())
        resp = client.get("/api/analytics/model-monitoring")
        assert resp.status_code == 403


class TestCeoModelMonitoringAccess:
    """CEO can access model monitoring and gets correct response shapes."""

    @patch("src.services.model_monitoring.fetch_traces", new_callable=AsyncMock)
    def test_ceo_gets_summary(self, mock_fetch, make_client):
        """CEO gets 200 with correct response shape on summary endpoint."""
        mock_fetch.return_value = None
        client = make_client(ceo(), make_mock_session())

        resp = client.get("/api/analytics/model-monitoring")

        assert resp.status_code == 200
        body = resp.json()
        assert "mlflow_available" in body
        assert "latency" in body
        assert "token_usage" in body
        assert "errors" in body
        assert "routing" in body
        assert "time_range_hours" in body

    @patch("src.services.model_monitoring.fetch_traces", new_callable=AsyncMock)
    def test_ceo_gets_sub_endpoints(self, mock_fetch, make_client):
        """CEO gets 200 on all sub-endpoints when MLFlow has data."""
        from datetime import UTC, datetime, timedelta

        obs = [
            {
                "model": "gpt-4o-mini",
                "startTime": (datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)).isoformat(),
                "endTime": (
                    datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC) + timedelta(milliseconds=500)
                ).isoformat(),
                "usage": {"input": 100, "output": 50},
                "level": "DEFAULT",
                "statusMessage": "",
            }
        ]
        mock_fetch.return_value = obs
        client = make_client(ceo(), make_mock_session())

        for path in _MONITORING_ENDPOINTS:
            resp = client.get(path)
            assert resp.status_code == 200, f"Expected 200 on {path}, got {resp.status_code}"
