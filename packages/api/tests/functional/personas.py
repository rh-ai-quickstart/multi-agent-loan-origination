# This project was developed with assistance from AI tools.
"""Persona factories for functional tests.

Each function returns a UserContext matching the DataScope built by
``middleware/auth.py:build_data_scope()`` for that role. Fixed user IDs
ensure cross-test consistency.
"""

from db.enums import UserRole

from src.schemas.auth import DataScope, UserContext

# Fixed IDs for cross-test referencing
SARAH_USER_ID = "sarah-mitchell-001"
MICHAEL_USER_ID = "michael-chen-002"
LO_USER_ID = "james-torres-lo"
LO_BOB_USER_ID = "bob-williams-lo"
UW_USER_ID = "emily-park-uw"
CEO_USER_ID = "ceo-dashboard"
ADMIN_USER_ID = "admin-user"
PROSPECT_USER_ID = "prospect-visitor"


def prospect() -> UserContext:
    return UserContext(
        user_id=PROSPECT_USER_ID,
        role=UserRole.PROSPECT,
        email="visitor@example.com",
        name="Visitor",
        data_scope=DataScope(),
    )


def borrower_sarah() -> UserContext:
    return UserContext(
        user_id=SARAH_USER_ID,
        role=UserRole.BORROWER,
        email="sarah@example.com",
        name="Sarah Mitchell",
        data_scope=DataScope(own_data_only=True, user_id=SARAH_USER_ID),
    )


def borrower_michael() -> UserContext:
    return UserContext(
        user_id=MICHAEL_USER_ID,
        role=UserRole.BORROWER,
        email="michael@example.com",
        name="Michael Chen",
        data_scope=DataScope(own_data_only=True, user_id=MICHAEL_USER_ID),
    )


def loan_officer() -> UserContext:
    return UserContext(
        user_id=LO_USER_ID,
        role=UserRole.LOAN_OFFICER,
        email="james@example.com",
        name="James Torres",
        data_scope=DataScope(assigned_to=LO_USER_ID),
    )


def loan_officer_bob() -> UserContext:
    return UserContext(
        user_id=LO_BOB_USER_ID,
        role=UserRole.LOAN_OFFICER,
        email="bob@example.com",
        name="Bob Williams",
        data_scope=DataScope(assigned_to=LO_BOB_USER_ID),
    )


def underwriter() -> UserContext:
    return UserContext(
        user_id=UW_USER_ID,
        role=UserRole.UNDERWRITER,
        email="emily@example.com",
        name="Emily Park",
        data_scope=DataScope(full_pipeline=True),
    )


def ceo() -> UserContext:
    return UserContext(
        user_id=CEO_USER_ID,
        role=UserRole.CEO,
        email="ceo@example.com",
        name="CEO Dashboard",
        data_scope=DataScope(
            pii_mask=True,
            document_metadata_only=True,
            full_pipeline=True,
        ),
    )


def admin() -> UserContext:
    return UserContext(
        user_id=ADMIN_USER_ID,
        role=UserRole.ADMIN,
        email="admin@example.com",
        name="Admin User",
        data_scope=DataScope(full_pipeline=True),
    )
