# This project was developed with assistance from AI tools.
"""Functional tests: PrequalificationSummary in application responses.

Verifies that _build_app_response correctly serializes PrequalificationDecision
data into the ApplicationResponse JSON, and that applications without a decision
return prequalification: null.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.models import PrequalificationDecision

from .data_factory import (
    lo_assigned_applications,
    make_app_sarah_1,
    sarah_applications,
)
from .mock_db import make_mock_session
from .personas import borrower_sarah, loan_officer

pytestmark = pytest.mark.functional


def _make_prequal_mock(**overrides):
    """Build a MagicMock that passes isinstance(obj, PrequalificationDecision).

    SQLAlchemy mapped classes can't be instantiated with __new__ outside a
    session, so we use a MagicMock with spec and manually set attributes.
    """
    defaults = {
        "product_id": "conventional_30",
        "max_loan_amount": Decimal("350000.00"),
        "estimated_rate": Decimal("6.500"),
        "issued_at": datetime(2026, 3, 1, tzinfo=UTC),
        "expires_at": datetime(2026, 5, 30, tzinfo=UTC),
    }
    defaults.update(overrides)
    pq = MagicMock(spec=PrequalificationDecision)
    for k, v in defaults.items():
        setattr(pq, k, v)
    return pq


def _attach_prequal(app, **overrides):
    """Attach a PrequalificationDecision mock to a mock application."""
    app.prequalification_decision = _make_prequal_mock(**overrides)
    return app


class TestPrequalInGetResponse:
    """GET /api/applications/{id} includes prequalification when present."""

    def test_should_include_prequal_summary_when_decision_exists(self, make_client):
        app = _attach_prequal(make_app_sarah_1())
        client = make_client(loan_officer(), make_mock_session(single=app))

        resp = client.get(f"/api/applications/{app.id}")
        assert resp.status_code == 200
        data = resp.json()

        pq = data["prequalification"]
        assert pq is not None
        assert pq["product_id"] == "conventional_30"
        assert pq["product_name"] == "30-Year Fixed Conventional"
        assert float(pq["max_loan_amount"]) == 350000.0
        assert pq["estimated_rate"] == 6.5
        assert pq["issued_at"] is not None
        assert pq["expires_at"] is not None

    def test_should_return_null_prequal_when_no_decision(self, make_client):
        app = make_app_sarah_1()
        app.prequalification_decision = None
        client = make_client(loan_officer(), make_mock_session(single=app))

        resp = client.get(f"/api/applications/{app.id}")
        assert resp.status_code == 200
        assert resp.json()["prequalification"] is None

    def test_should_map_product_name_from_product_catalog(self, make_client):
        """Product name is resolved from PRODUCTS list, not stored on decision."""
        app = _attach_prequal(make_app_sarah_1(), product_id="fha")
        client = make_client(loan_officer(), make_mock_session(single=app))

        resp = client.get(f"/api/applications/{app.id}")
        pq = resp.json()["prequalification"]
        assert pq["product_name"] == "FHA Loan"

    def test_should_fall_back_to_product_id_for_unknown_product(self, make_client):
        """If product_id isn't in PRODUCTS, use the raw ID as name."""
        app = _attach_prequal(make_app_sarah_1(), product_id="unknown_product")
        client = make_client(loan_officer(), make_mock_session(single=app))

        resp = client.get(f"/api/applications/{app.id}")
        pq = resp.json()["prequalification"]
        assert pq["product_name"] == "unknown_product"


class TestPrequalInListResponse:
    """GET /api/applications/ includes prequalification on each item."""

    def test_should_show_prequal_on_mixed_list(self, make_client):
        """One app has prequal, the other doesn't."""
        apps = sarah_applications()
        _attach_prequal(apps[0])  # sarah_app_1 gets prequal
        apps[1].prequalification_decision = None  # sarah_app_2 does not

        client = make_client(borrower_sarah(), make_mock_session(items=apps))

        resp = client.get("/api/applications/")
        assert resp.status_code == 200
        items = resp.json()["data"]

        has_prequal = [item for item in items if item["prequalification"] is not None]
        no_prequal = [item for item in items if item["prequalification"] is None]
        assert len(has_prequal) == 1
        assert len(no_prequal) == 1
        assert has_prequal[0]["prequalification"]["product_id"] == "conventional_30"

    @patch("src.routes.applications.compute_urgency", new_callable=AsyncMock)
    def test_lo_list_includes_prequal_with_urgency(self, mock_urgency, make_client):
        """LO list response has both urgency AND prequalification."""
        from src.schemas.urgency import UrgencyIndicator, UrgencyLevel

        apps = lo_assigned_applications()
        _attach_prequal(apps[0])
        apps[1].prequalification_decision = None
        mock_urgency.return_value = {
            apps[0].id: UrgencyIndicator(
                level=UrgencyLevel.NORMAL,
                factors=[],
                days_in_stage=1,
                expected_stage_days=5,
            ),
            apps[1].id: UrgencyIndicator(
                level=UrgencyLevel.NORMAL,
                factors=[],
                days_in_stage=1,
                expected_stage_days=5,
            ),
        }

        client = make_client(loan_officer(), make_mock_session(items=apps))
        resp = client.get("/api/applications/")
        assert resp.status_code == 200
        items = resp.json()["data"]

        app_with_pq = next(i for i in items if i["id"] == apps[0].id)
        assert app_with_pq["prequalification"] is not None
        assert app_with_pq["urgency"] is not None
