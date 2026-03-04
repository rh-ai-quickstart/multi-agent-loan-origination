# This project was developed with assistance from AI tools.
"""Full application lifecycle through API routes."""

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.integration


async def test_create_application(client_factory, db_session):
    """POST as borrower creates application + borrower + junction."""

    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.post(
        "/api/applications/",
        json={
            "loan_type": "conventional_30",
            "property_address": "100 Test St",
            "loan_amount": 300000,
            "property_value": 400000,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["loan_type"] == "conventional_30"
    assert data["property_address"] == "100 Test St"
    assert len(data["borrowers"]) >= 1
    await client.aclose()


async def test_create_auto_creates_borrower(client_factory, db_session):
    """New keycloak_user_id creates Borrower row automatically."""
    from db.models import Borrower

    from tests.functional.personas import SARAH_USER_ID, borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.post("/api/applications/", json={"loan_type": "fha"})
    assert resp.status_code == 201

    result = await db_session.execute(
        select(Borrower).where(Borrower.keycloak_user_id == SARAH_USER_ID)
    )
    borrower = result.scalar_one_or_none()
    assert borrower is not None
    assert borrower.first_name == "Sarah"
    await client.aclose()


async def test_create_reuses_existing_borrower(client_factory, db_session, seed_data):
    """Second POST by same user reuses existing Borrower."""
    from db.models import Borrower
    from sqlalchemy import func

    from tests.functional.personas import SARAH_USER_ID, borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.post("/api/applications/", json={"loan_type": "va"})
    assert resp.status_code == 201

    count = (
        await db_session.execute(
            select(func.count(Borrower.id)).where(Borrower.keycloak_user_id == SARAH_USER_ID)
        )
    ).scalar()
    assert count == 1
    await client.aclose()


async def test_get_application_by_id(client_factory, seed_data):
    """GET returns app with borrowers list populated."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.get(f"/api/applications/{seed_data.sarah_app1.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seed_data.sarah_app1.id
    assert len(data["borrowers"]) >= 1
    await client.aclose()


async def test_get_nonexistent_returns_404(client_factory, seed_data):
    """GET for nonexistent ID returns 404."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.get("/api/applications/99999")
    assert resp.status_code == 404
    await client.aclose()


async def test_list_applications(client_factory, seed_data):
    """GET list returns seeded apps with correct count."""
    from tests.functional.personas import admin

    client = await client_factory(admin())
    resp = await client.get("/api/applications/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pagination"]["total"] == 3
    assert len(data["data"]) == 3
    await client.aclose()


async def test_update_stage(client_factory, seed_data):
    """PATCH as LO with stage change succeeds."""
    from tests.functional.personas import loan_officer

    client = await client_factory(loan_officer())
    resp = await client.patch(
        f"/api/applications/{seed_data.sarah_app1.id}",
        json={"stage": "processing"},
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "processing"
    await client.aclose()


async def test_update_empty_body_returns_400(client_factory, seed_data):
    """PATCH with empty body returns 400."""
    from tests.functional.personas import loan_officer

    client = await client_factory(loan_officer())
    resp = await client.patch(
        f"/api/applications/{seed_data.sarah_app1.id}",
        json={},
    )
    assert resp.status_code == 400
    await client.aclose()


# ---------------------------------------------------------------------------
# PrequalificationDecision in response
# ---------------------------------------------------------------------------


async def test_get_application_without_prequal_returns_null(client_factory, seed_data):
    """GET returns prequalification: null when no decision exists."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.get(f"/api/applications/{seed_data.sarah_app1.id}")
    assert resp.status_code == 200
    assert resp.json()["prequalification"] is None
    await client.aclose()


async def test_get_application_with_prequal_returns_summary(client_factory, db_session, seed_data):
    """GET returns prequalification summary when a decision exists in DB."""
    from datetime import UTC, datetime

    from db.models import PrequalificationDecision

    from tests.functional.personas import borrower_sarah

    pq = PrequalificationDecision(
        application_id=seed_data.sarah_app1.id,
        product_id="conventional_30",
        max_loan_amount=350000,
        estimated_rate=6.5,
        credit_score_at_decision=742,
        dti_at_decision=0.2800,
        ltv_at_decision=0.7778,
        issued_by="james-torres-lo",
        issued_at=datetime(2026, 3, 1, tzinfo=UTC),
        expires_at=datetime(2026, 5, 30, tzinfo=UTC),
    )
    db_session.add(pq)
    await db_session.flush()

    client = await client_factory(borrower_sarah())
    resp = await client.get(f"/api/applications/{seed_data.sarah_app1.id}")
    assert resp.status_code == 200
    data = resp.json()

    pq_data = data["prequalification"]
    assert pq_data is not None
    assert pq_data["product_id"] == "conventional_30"
    assert pq_data["product_name"] == "30-Year Fixed Conventional"
    assert pq_data["max_loan_amount"] == 350000.0
    assert pq_data["estimated_rate"] == 6.5
    assert pq_data["issued_at"] is not None
    assert pq_data["expires_at"] is not None
    await client.aclose()


async def test_list_applications_includes_prequal(client_factory, db_session, seed_data):
    """GET list includes prequalification on applications that have one."""
    from datetime import UTC, datetime

    from db.models import PrequalificationDecision

    from tests.functional.personas import admin

    pq = PrequalificationDecision(
        application_id=seed_data.sarah_app1.id,
        product_id="fha",
        max_loan_amount=275000,
        estimated_rate=6.0,
        credit_score_at_decision=680,
        dti_at_decision=0.3200,
        ltv_at_decision=0.8462,
        issued_by="james-torres-lo",
        issued_at=datetime(2026, 3, 1, tzinfo=UTC),
        expires_at=datetime(2026, 5, 30, tzinfo=UTC),
    )
    db_session.add(pq)
    await db_session.flush()

    client = await client_factory(admin())
    resp = await client.get("/api/applications/")
    assert resp.status_code == 200
    items = resp.json()["data"]

    app_with_pq = next(i for i in items if i["id"] == seed_data.sarah_app1.id)
    app_without_pq = next(i for i in items if i["id"] == seed_data.sarah_app2.id)

    assert app_with_pq["prequalification"] is not None
    assert app_with_pq["prequalification"]["product_id"] == "fha"
    assert app_with_pq["prequalification"]["product_name"] == "FHA Loan"
    assert app_without_pq["prequalification"] is None
    await client.aclose()
