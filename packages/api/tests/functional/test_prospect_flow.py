# This project was developed with assistance from AI tools.
"""Functional tests: Prospect persona journey.

Prospects can access public endpoints (products, affordability calculator,
health) but must be denied on all protected endpoints.
"""

import pytest

from .mock_db import make_mock_session
from .personas import prospect

pytestmark = pytest.mark.functional


class TestProspectPublicAccess:
    """Prospects can access unauthenticated public endpoints."""

    def test_health_endpoint(self, make_client):
        client = make_client(prospect(), make_mock_session())
        resp = client.get("/health/")
        assert resp.status_code == 200

    def test_list_products(self, make_client):
        client = make_client(prospect(), make_mock_session())
        resp = client.get("/api/public/products")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_affordability_calculator(self, make_client):
        client = make_client(prospect(), make_mock_session())
        resp = client.post(
            "/api/public/calculate-affordability",
            json={
                "gross_annual_income": 120000,
                "monthly_debts": 500,
                "down_payment": 50000,
                "interest_rate": 6.5,
                "loan_term_years": 30,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "max_loan_amount" in data

    def test_root_endpoint(self, make_client):
        client = make_client(prospect(), make_mock_session())
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["message"]  # non-empty welcome message


class TestProspectDenied:
    """Prospects are denied on all protected endpoints (403)."""

    def test_list_applications_denied(self, monkeypatch, make_client):
        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        client = make_client(prospect(), make_mock_session())
        resp = client.get("/api/applications/")
        assert resp.status_code == 403

    def test_get_application_denied(self, monkeypatch, make_client):
        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        client = make_client(prospect(), make_mock_session())
        resp = client.get("/api/applications/101")
        assert resp.status_code == 403

    def test_create_application_denied(self, monkeypatch, make_client):
        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        client = make_client(prospect(), make_mock_session())
        resp = client.post("/api/applications/", json={})
        assert resp.status_code == 403

    def test_admin_seed_status_denied(self, monkeypatch, make_client):
        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        client = make_client(prospect(), make_mock_session())
        resp = client.get("/api/admin/seed/status")
        assert resp.status_code == 403

    def test_documents_denied(self, monkeypatch, make_client):
        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        client = make_client(prospect(), make_mock_session())
        resp = client.get("/api/applications/101/documents")
        assert resp.status_code == 403

    def test_upload_document_denied(self, monkeypatch, make_client):
        from io import BytesIO

        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        client = make_client(prospect(), make_mock_session())
        resp = client.post(
            "/api/applications/101/documents",
            files={"file": ("test.pdf", BytesIO(b"%PDF"), "application/pdf")},
            data={"doc_type": "w2"},
        )
        assert resp.status_code == 403
