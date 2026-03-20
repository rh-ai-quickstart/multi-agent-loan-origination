# This project was developed with assistance from AI tools.
"""Application status endpoint with real PostgreSQL."""

import io

import pytest

pytestmark = pytest.mark.integration


async def test_borrower_sees_status_with_missing_docs(client_factory, seed_data):
    """Sarah's app1 has W2 + PAY_STUB -> status shows 2/4, pending uploads."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.get(f"/api/applications/{seed_data.sarah_app1.id}/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["stage"] == "application"
    assert data["is_document_complete"] is False
    assert data["provided_doc_count"] == 2
    assert data["required_doc_count"] == 4
    assert data["open_condition_count"] == 0

    upload_actions = [a for a in data["pending_actions"] if a["action_type"] == "upload_document"]
    assert len(upload_actions) == 2
    descriptions = {a["description"] for a in upload_actions}
    assert "Upload Bank Statement" in descriptions
    assert "Upload Government-Issued ID" in descriptions
    await client.aclose()


async def test_borrower_blocked_from_other_app_status(client_factory, seed_data):
    """Sarah can't see Michael's app status -> 404."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.get(f"/api/applications/{seed_data.michael_app.id}/status")
    assert resp.status_code == 404
    await client.aclose()


async def test_status_after_all_docs_uploaded(client_factory, seed_data):
    """Upload remaining docs -> status shows is_complete=True, no upload actions."""
    from unittest.mock import patch

    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    app_id = seed_data.sarah_app1.id

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

    resp = await client.get(f"/api/applications/{app_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_document_complete"] is True
    assert data["provided_doc_count"] == 4

    upload_actions = [a for a in data["pending_actions"] if a["action_type"] == "upload_document"]
    assert len(upload_actions) == 0
    await client.aclose()


async def test_ceo_sees_any_app_status(client_factory, seed_data):
    """CEO can view status on any application."""
    from tests.functional.personas import ceo

    client = await client_factory(ceo())
    resp = await client.get(f"/api/applications/{seed_data.michael_app.id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage"] == "processing"
    assert data["stage_info"]["label"] == "Processing"
    await client.aclose()


async def test_status_stage_info_matches_app_stage(client_factory, seed_data):
    """Stage info label matches the actual application stage."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())

    # sarah_app2 is FHA at INQUIRY stage
    resp = await client.get(f"/api/applications/{seed_data.sarah_app2.id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage"] == "inquiry"
    assert data["stage_info"]["label"] == "Inquiry"
    await client.aclose()
