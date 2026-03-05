# This project was developed with assistance from AI tools.
"""Tests for underwriter chat endpoints.

Only tests UW-specific behavior: role gating and route wiring.
WebSocket protocol is tested in _chat_handler.py tests.
"""

from unittest.mock import AsyncMock, patch

import pytest
from db.enums import UserRole
from fastapi import Request
from fastapi.testclient import TestClient

from src.main import app
from src.middleware.auth import get_current_user
from src.schemas.auth import DataScope, UserContext


def _make_user(role: UserRole, user_id: str = "test-user") -> UserContext:
    """Build a test UserContext."""
    if role == UserRole.UNDERWRITER:
        scope = DataScope(full_pipeline=True)
    elif role == UserRole.BORROWER:
        scope = DataScope(own_data_only=True, user_id=user_id)
    elif role == UserRole.ADMIN:
        scope = DataScope(full_pipeline=True)
    else:
        scope = DataScope()
    return UserContext(
        user_id=user_id,
        role=role,
        email=f"{user_id}@test.com",
        name="Test User",
        data_scope=scope,
    )


@pytest.fixture(autouse=True)
def _clean_overrides():
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


class TestUwConversationHistory:
    """Tests for GET /api/underwriter/conversations/history."""

    def test_history_requires_uw_role(self):
        """Borrower hitting UW history endpoint gets 403."""
        borrower = _make_user(UserRole.BORROWER, "borrower-1")

        async def fake_user(request: Request):
            request.state.pii_mask = False
            return borrower

        app.dependency_overrides[get_current_user] = fake_user
        client = TestClient(app)

        resp = client.get("/api/underwriter/conversations/history")
        assert resp.status_code == 403

    @patch(
        "src.services.conversation.get_conversation_service",
    )
    def test_history_returns_data_shape(self, mock_get_svc):
        """Underwriter gets back {"data": [...]} response."""
        uw = _make_user(UserRole.UNDERWRITER, "uw-maria")

        async def fake_user(request: Request):
            request.state.pii_mask = False
            return uw

        app.dependency_overrides[get_current_user] = fake_user

        mock_svc = mock_get_svc.return_value
        mock_svc.get_conversation_history = AsyncMock(return_value=[])

        client = TestClient(app)
        resp = client.get("/api/underwriter/conversations/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    @patch(
        "src.services.conversation.get_conversation_service",
    )
    def test_admin_can_access_history(self, mock_get_svc):
        """Admin can access UW history endpoint."""
        admin = _make_user(UserRole.ADMIN, "admin-1")

        async def fake_user(request: Request):
            request.state.pii_mask = False
            return admin

        app.dependency_overrides[get_current_user] = fake_user

        mock_svc = mock_get_svc.return_value
        mock_svc.get_conversation_history = AsyncMock(return_value=[])

        client = TestClient(app)
        resp = client.get("/api/underwriter/conversations/history")
        assert resp.status_code == 200


class TestUwClearConversation:
    """Tests for DELETE /api/underwriter/conversations/history."""

    def test_delete_requires_uw_role(self):
        """Borrower hitting DELETE on UW history gets 403."""
        borrower = _make_user(UserRole.BORROWER, "borrower-1")

        async def fake_user(request: Request):
            request.state.pii_mask = False
            return borrower

        app.dependency_overrides[get_current_user] = fake_user
        client = TestClient(app)

        resp = client.delete("/api/underwriter/conversations/history")
        assert resp.status_code == 403

    @patch("src.services.conversation.get_conversation_service")
    def test_delete_returns_204(self, mock_get_svc):
        """Underwriter can clear their conversation history."""
        uw = _make_user(UserRole.UNDERWRITER, "uw-maria")

        async def fake_user(request: Request):
            request.state.pii_mask = False
            return uw

        app.dependency_overrides[get_current_user] = fake_user

        mock_svc = mock_get_svc.return_value
        mock_svc.clear_conversation = AsyncMock(return_value=True)

        client = TestClient(app)
        resp = client.delete("/api/underwriter/conversations/history")
        assert resp.status_code == 204

    def test_lo_cannot_delete_uw_history(self):
        """Loan officer hitting DELETE on UW history gets 403."""
        lo = _make_user(UserRole.LOAN_OFFICER, "lo-james")

        async def fake_user(request: Request):
            request.state.pii_mask = False
            return lo

        app.dependency_overrides[get_current_user] = fake_user
        client = TestClient(app)

        resp = client.delete("/api/underwriter/conversations/history")
        assert resp.status_code == 403
