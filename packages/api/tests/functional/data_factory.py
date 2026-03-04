# This project was developed with assistance from AI tools.
"""Centralized mock data portfolio for functional tests.

Produces consistent mock ORM objects shared across all persona tests:
- 2 borrowers (Sarah, Michael) with PII
- 3 applications at different stages and assignments
- Documents for application 101

All IDs are fixed so persona tests can reference them by number.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from db.enums import (
    ApplicationStage,
    DocumentStatus,
    DocumentType,
    LoanType,
)

from .personas import LO_BOB_USER_ID, LO_USER_ID, MICHAEL_USER_ID, SARAH_USER_ID

# ---------------------------------------------------------------------------
# Borrowers
# ---------------------------------------------------------------------------


def make_borrower_sarah() -> MagicMock:
    b = MagicMock()
    b.id = 1
    b.keycloak_user_id = SARAH_USER_ID
    b.first_name = "Sarah"
    b.last_name = "Mitchell"
    b.email = "sarah@example.com"
    b.ssn = "123-45-6789"
    b.dob = datetime(1990, 3, 15, tzinfo=UTC)
    b.employment_status = None
    b.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    b.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return b


def make_borrower_michael() -> MagicMock:
    b = MagicMock()
    b.id = 2
    b.keycloak_user_id = MICHAEL_USER_ID
    b.first_name = "Michael"
    b.last_name = "Chen"
    b.email = "michael@example.com"
    b.ssn = "987-65-4321"
    b.dob = datetime(1985, 7, 22, tzinfo=UTC)
    b.employment_status = None
    b.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    b.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return b


def _make_app_borrower(borrower, *, is_primary=True) -> MagicMock:
    """Build a mock ApplicationBorrower junction object."""
    ab = MagicMock()
    ab.borrower = borrower
    ab.borrower_id = borrower.id
    ab.is_primary = is_primary
    return ab


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


def _make_application(**fields) -> MagicMock:
    """Build a mock Application with defaults for schema-required attributes.

    Ensures Pydantic ``from_attributes`` validation succeeds by setting
    attributes that don't exist on the real ORM model to ``None``.
    """
    app = MagicMock()
    for key, value in fields.items():
        setattr(app, key, value)
    # Schema-only fields that the ORM model doesn't carry
    app.urgency = None
    # Explicit None prevents MagicMock from auto-creating a truthy mock attribute
    if "prequalification_decision" not in fields:
        app.prequalification_decision = None
    return app


def make_app_sarah_1() -> MagicMock:
    """App 101: Sarah, APPLICATION stage, assigned to LO."""
    return _make_application(
        id=101,
        stage=ApplicationStage.APPLICATION,
        loan_type=LoanType.CONVENTIONAL_30,
        property_address="123 Oak Street",
        loan_amount=Decimal("350000.00"),
        property_value=Decimal("450000.00"),
        assigned_to=LO_USER_ID,
        created_at=datetime(2026, 1, 10, tzinfo=UTC),
        updated_at=datetime(2026, 1, 15, tzinfo=UTC),
        application_borrowers=[_make_app_borrower(make_borrower_sarah())],
    )


def make_app_sarah_2() -> MagicMock:
    """App 102: Sarah, INQUIRY stage, unassigned."""
    return _make_application(
        id=102,
        stage=ApplicationStage.INQUIRY,
        loan_type=None,
        property_address=None,
        loan_amount=None,
        property_value=None,
        assigned_to=None,
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
        updated_at=datetime(2026, 2, 1, tzinfo=UTC),
        application_borrowers=[_make_app_borrower(make_borrower_sarah())],
    )


def make_app_michael() -> MagicMock:
    """App 103: Michael, UNDERWRITING stage, assigned to LO."""
    return _make_application(
        id=103,
        stage=ApplicationStage.UNDERWRITING,
        loan_type=LoanType.FHA,
        property_address="456 Maple Avenue",
        loan_amount=Decimal("275000.00"),
        property_value=Decimal("320000.00"),
        assigned_to=LO_USER_ID,
        created_at=datetime(2026, 1, 20, tzinfo=UTC),
        updated_at=datetime(2026, 2, 10, tzinfo=UTC),
        application_borrowers=[_make_app_borrower(make_borrower_michael())],
    )


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------


def all_applications() -> list[MagicMock]:
    """All 3 applications (CEO/underwriter/admin view)."""
    return [make_app_sarah_1(), make_app_sarah_2(), make_app_michael()]


def sarah_applications() -> list[MagicMock]:
    """Sarah's 2 applications (borrower_sarah view)."""
    return [make_app_sarah_1(), make_app_sarah_2()]


def michael_applications() -> list[MagicMock]:
    """Michael's 1 application (borrower_michael view)."""
    return [make_app_michael()]


def lo_assigned_applications() -> list[MagicMock]:
    """Apps assigned to LO James: 101 + 103 (102 is unassigned)."""
    return [make_app_sarah_1(), make_app_michael()]


def make_app_bob_assigned() -> MagicMock:
    """App 104: Assigned to LO Bob, PROCESSING stage."""
    return _make_application(
        id=104,
        stage=ApplicationStage.PROCESSING,
        loan_type=LoanType.VA,
        property_address="789 Elm Drive",
        loan_amount=Decimal("400000.00"),
        property_value=Decimal("500000.00"),
        assigned_to=LO_BOB_USER_ID,
        created_at=datetime(2026, 2, 5, tzinfo=UTC),
        updated_at=datetime(2026, 2, 15, tzinfo=UTC),
        application_borrowers=[_make_app_borrower(make_borrower_michael())],
    )


def lo_bob_applications() -> list[MagicMock]:
    """Apps assigned to LO Bob: 104 only."""
    return [make_app_bob_assigned()]


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def make_document(**overrides) -> MagicMock:
    """Build a mock Document ORM object with sensible defaults."""
    doc = MagicMock()
    doc.id = overrides.get("id", 1)
    doc.application_id = overrides.get("application_id", 101)
    doc.borrower_id = overrides.get("borrower_id", 1)
    doc.doc_type = overrides.get("doc_type", DocumentType.W2)
    doc.status = overrides.get("status", DocumentStatus.UPLOADED)
    doc.quality_flags = overrides.get("quality_flags", None)
    doc.uploaded_by = overrides.get("uploaded_by", "james.torres")
    doc.file_path = overrides.get("file_path", "/uploads/w2-2024.pdf")
    doc.created_at = overrides.get(
        "created_at",
        datetime(2026, 1, 15, tzinfo=UTC),
    )
    doc.updated_at = overrides.get(
        "updated_at",
        datetime(2026, 1, 15, tzinfo=UTC),
    )
    # Relationship for join-based scope filtering
    doc.application = make_app_sarah_1()
    return doc


def app_101_documents() -> list[MagicMock]:
    """Documents for application 101."""
    return [
        make_document(id=1, doc_type=DocumentType.W2),
        make_document(id=2, doc_type=DocumentType.PAY_STUB, file_path="/uploads/paystub.pdf"),
    ]
