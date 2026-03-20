# This project was developed with assistance from AI tools.
"""Functional tests: Document completeness endpoint across personas.

Validates that completeness checks respect data scope (borrowers see own,
LO sees assigned, CEO sees all, prospect blocked) and return correct
response shape through the real FastAPI app with mocked DB.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from db.enums import DocumentStatus, DocumentType, EmploymentStatus

from .data_factory import make_app_sarah_1
from .personas import borrower_sarah, ceo, loan_officer, prospect

pytestmark = pytest.mark.functional


def _make_completeness_session(application, documents):
    """Build a mock session for the completeness endpoint.

    The completeness service runs two queries:
      1. Application lookup (with data scope) -> unique().scalar_one_or_none()
      2. Document query (with data scope) -> scalars().all()
    """
    session = AsyncMock()

    app_result = MagicMock()
    app_result.unique.return_value.scalar_one_or_none.return_value = application

    doc_result = MagicMock()
    doc_result.scalars.return_value.all.return_value = documents

    session.execute = AsyncMock(side_effect=[app_result, doc_result])
    return session


def _make_doc(doc_id, doc_type, status=DocumentStatus.UPLOADED, quality_flags=None):
    """Build a mock Document."""
    doc = MagicMock()
    doc.id = doc_id
    doc.doc_type = doc_type
    doc.status = status
    doc.quality_flags = json.dumps(quality_flags) if quality_flags else None
    doc.created_at = datetime(2026, 1, 15, tzinfo=UTC)
    doc.application = make_app_sarah_1()
    return doc


class TestBorrowerCompleteness:
    """Borrower can check completeness on own application."""

    def test_borrower_sees_completeness(self, app, make_client):
        sarah_app = make_app_sarah_1()
        # Sarah has W2 and pay stub uploaded, missing bank statement + ID
        docs = [
            _make_doc(1, DocumentType.W2),
            _make_doc(2, DocumentType.PAY_STUB),
        ]
        session = _make_completeness_session(sarah_app, docs)
        client = make_client(borrower_sarah(), session)

        resp = client.get(f"/api/applications/{sarah_app.id}/completeness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_complete"] is False
        assert data["provided_count"] == 2
        assert data["required_count"] == 4

        missing = [r for r in data["requirements"] if not r["is_provided"]]
        missing_types = {r["doc_type"] for r in missing}
        assert "bank_statement" in missing_types
        assert "drivers_license" in missing_types

    def test_borrower_cannot_see_other_app(self, app, make_client):
        """Borrower checking another user's app gets 404 (scope returns None)."""
        session = _make_completeness_session(None, [])
        client = make_client(borrower_sarah(), session)

        resp = client.get("/api/applications/99999/completeness")
        assert resp.status_code == 404


class TestLoanOfficerCompleteness:
    """LO sees completeness on assigned applications."""

    def test_lo_sees_assigned_app_completeness(self, app, make_client):
        sarah_app = make_app_sarah_1()
        docs = [
            _make_doc(1, DocumentType.W2),
            _make_doc(2, DocumentType.PAY_STUB),
            _make_doc(3, DocumentType.BANK_STATEMENT),
            _make_doc(4, DocumentType.DRIVERS_LICENSE),
        ]
        session = _make_completeness_session(sarah_app, docs)
        client = make_client(loan_officer(), session)

        resp = client.get(f"/api/applications/{sarah_app.id}/completeness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_complete"] is True
        assert data["provided_count"] == 4


class TestCeoCompleteness:
    """CEO can view completeness (aggregate visibility)."""

    def test_ceo_sees_completeness(self, app, make_client):
        sarah_app = make_app_sarah_1()
        docs = [_make_doc(1, DocumentType.W2)]
        session = _make_completeness_session(sarah_app, docs)
        client = make_client(ceo(), session)

        resp = client.get(f"/api/applications/{sarah_app.id}/completeness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_complete"] is False


class TestProspectBlocked:
    """Prospect cannot access completeness endpoint."""

    def test_prospect_blocked(self, monkeypatch, app, make_client):
        from src.core.config import settings

        monkeypatch.setattr(settings, "AUTH_DISABLED", False)

        session = AsyncMock()
        client = make_client(prospect(), session)
        resp = client.get("/api/applications/101/completeness")
        assert resp.status_code == 403


class TestQualityFlagsSurfaced:
    """Completeness response includes quality flags from documents."""

    def test_blurry_flag_in_response(self, app, make_client):
        sarah_app = make_app_sarah_1()
        # Set employment status so requirements are deterministic
        sarah_app.application_borrowers[0].borrower.employment_status = EmploymentStatus.W2_EMPLOYEE
        docs = [
            _make_doc(1, DocumentType.W2, quality_flags=["blurry"]),
            _make_doc(2, DocumentType.PAY_STUB),
            _make_doc(3, DocumentType.BANK_STATEMENT),
            _make_doc(4, DocumentType.DRIVERS_LICENSE),
        ]
        session = _make_completeness_session(sarah_app, docs)
        client = make_client(loan_officer(), session)

        resp = client.get(f"/api/applications/{sarah_app.id}/completeness")
        assert resp.status_code == 200
        data = resp.json()
        w2_req = next(r for r in data["requirements"] if r["doc_type"] == "w2")
        assert "blurry" in w2_req["quality_flags"]
