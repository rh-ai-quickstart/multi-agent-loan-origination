# This project was developed with assistance from AI tools.
"""Document completeness with real PostgreSQL -- no mocks except LLM."""

import io

import pytest

pytestmark = pytest.mark.integration


async def test_borrower_sees_own_completeness(client_factory, seed_data):
    """Sarah checks completeness on her conventional_30 app (2 of 4 docs uploaded)."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.get(f"/api/applications/{seed_data.sarah_app1.id}/completeness")

    assert resp.status_code == 200
    data = resp.json()
    # conventional_30 with no employment_status -> _default/_default -> W2, PAY_STUB, BANK_STATEMENT, ID
    assert data["required_count"] == 4
    assert data["provided_count"] == 2
    assert data["is_complete"] is False

    provided = {r["doc_type"] for r in data["requirements"] if r["is_provided"]}
    missing = {r["doc_type"] for r in data["requirements"] if not r["is_provided"]}
    assert provided == {"w2", "pay_stub"}
    assert missing == {"bank_statement", "id"}
    await client.aclose()


async def test_borrower_blocked_from_other_app(client_factory, seed_data):
    """Sarah cannot see Michael's app completeness -> 404."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.get(f"/api/applications/{seed_data.michael_app.id}/completeness")
    assert resp.status_code == 404
    await client.aclose()


async def test_lo_sees_assigned_app(client_factory, seed_data):
    """LO sees completeness on sarah_app1 (assigned to LO)."""
    from tests.functional.personas import loan_officer

    client = await client_factory(loan_officer())
    resp = await client.get(f"/api/applications/{seed_data.sarah_app1.id}/completeness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["required_count"] == 4
    assert data["provided_count"] == 2
    await client.aclose()


async def test_ceo_sees_any_app(client_factory, seed_data):
    """CEO can check completeness on any application."""
    from tests.functional.personas import ceo

    client = await client_factory(ceo())
    resp = await client.get(f"/api/applications/{seed_data.michael_app.id}/completeness")
    assert resp.status_code == 200
    data = resp.json()
    # VA app with no employment_status -> va/_default -> W2, PAY_STUB, BANK_STATEMENT, ID
    assert data["required_count"] == 4
    # Michael has 0 docs uploaded
    assert data["provided_count"] == 0
    assert data["is_complete"] is False
    await client.aclose()


async def test_fha_app_requires_tax_return(client_factory, seed_data):
    """sarah_app2 is FHA -- requires 5 docs including tax_return."""
    from tests.functional.personas import ceo

    client = await client_factory(ceo())
    resp = await client.get(f"/api/applications/{seed_data.sarah_app2.id}/completeness")
    assert resp.status_code == 200
    data = resp.json()
    # FHA _default -> W2, PAY_STUB, TAX_RETURN, BANK_STATEMENT, ID
    assert data["required_count"] == 5
    required_types = {r["doc_type"] for r in data["requirements"]}
    assert "tax_return" in required_types
    await client.aclose()


async def test_completeness_after_all_docs_uploaded(client_factory, seed_data):
    """Upload remaining docs for sarah_app1 -> is_complete becomes True."""
    from unittest.mock import patch

    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    app_id = seed_data.sarah_app1.id

    # Upload bank_statement and id (seed already has W2 + PAY_STUB)
    pdf = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
    )

    with patch("src.routes.documents.asyncio.create_task"):
        for doc_type in ("bank_statement", "drivers_license"):
            resp = await client.post(
                f"/api/applications/{app_id}/documents",
                files={"file": ("doc.pdf", io.BytesIO(pdf), "application/pdf")},
                data={"doc_type": doc_type},
            )
            assert resp.status_code == 201

    # Now check completeness
    resp = await client.get(f"/api/applications/{app_id}/completeness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_complete"] is True
    assert data["provided_count"] == 4
    assert data["required_count"] == 4
    await client.aclose()


async def test_rejected_docs_not_counted(client_factory, seed_data, db_session):
    """Rejected documents should not count toward completeness."""
    from db.enums import DocumentStatus
    from db.models import Document
    from sqlalchemy import update

    from tests.functional.personas import borrower_sarah

    # Mark the W2 doc as rejected
    await db_session.execute(
        update(Document)
        .where(Document.id == seed_data.doc1.id)
        .values(status=DocumentStatus.REJECTED)
    )
    await db_session.flush()

    client = await client_factory(borrower_sarah())
    resp = await client.get(f"/api/applications/{seed_data.sarah_app1.id}/completeness")
    assert resp.status_code == 200
    data = resp.json()
    # Only PAY_STUB should count now (W2 rejected)
    assert data["provided_count"] == 1
    assert data["is_complete"] is False
    await client.aclose()
