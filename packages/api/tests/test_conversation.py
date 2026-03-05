# This project was developed with assistance from AI tools.
"""Unit tests for ConversationService -- thread ID generation, ownership, URL derivation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.conversation import ConversationService, derive_psycopg_url


class TestGetThreadId:
    """Tests for ConversationService.get_thread_id()."""

    def test_deterministic(self):
        """should return the same thread_id for the same user_id."""
        tid1 = ConversationService.get_thread_id("sarah-001")
        tid2 = ConversationService.get_thread_id("sarah-001")
        assert tid1 == tid2

    def test_different_users(self):
        """should return different thread_ids for different user_ids."""
        tid1 = ConversationService.get_thread_id("sarah-001")
        tid2 = ConversationService.get_thread_id("james-002")
        assert tid1 != tid2

    def test_format(self):
        """should produce user:{id}:agent:{name} format."""
        tid = ConversationService.get_thread_id("sarah-001", "public-assistant")
        assert tid == "user:sarah-001:agent:public-assistant"

    def test_different_agents(self):
        """should produce different thread_ids for different agent_names."""
        tid1 = ConversationService.get_thread_id("sarah-001", "public-assistant")
        tid2 = ConversationService.get_thread_id("sarah-001", "borrower-assistant")
        assert tid1 != tid2

    def test_default_agent(self):
        """should default to public-assistant agent."""
        tid = ConversationService.get_thread_id("sarah-001")
        assert tid == "user:sarah-001:agent:public-assistant"

    def test_with_application_id(self):
        """should append app:{id} when application_id is provided."""
        tid = ConversationService.get_thread_id(
            "sarah-001", "borrower-assistant", application_id=42
        )
        assert tid == "user:sarah-001:agent:borrower-assistant:app:42"

    def test_without_application_id(self):
        """should omit app segment when application_id is None."""
        tid = ConversationService.get_thread_id(
            "sarah-001", "borrower-assistant", application_id=None
        )
        assert tid == "user:sarah-001:agent:borrower-assistant"

    def test_different_applications(self):
        """should produce different thread_ids for different application_ids."""
        tid1 = ConversationService.get_thread_id("lo-001", "lo-assistant", application_id=1)
        tid2 = ConversationService.get_thread_id("lo-001", "lo-assistant", application_id=2)
        assert tid1 != tid2


class TestVerifyThreadOwnership:
    """Tests for ConversationService.verify_thread_ownership()."""

    def test_match(self):
        """should not raise for correct user."""
        tid = "user:sarah-001:agent:public-assistant"
        ConversationService.verify_thread_ownership(tid, "sarah-001")

    def test_mismatch(self):
        """should raise PermissionError for wrong user."""
        tid = "user:sarah-001:agent:public-assistant"
        with pytest.raises(PermissionError, match="does not belong"):
            ConversationService.verify_thread_ownership(tid, "james-002")

    def test_admin_no_override(self):
        """should reject admin user_id accessing borrower thread (S-2-F19-04)."""
        tid = "user:sarah-001:agent:borrower-assistant"
        with pytest.raises(PermissionError):
            ConversationService.verify_thread_ownership(tid, "admin-001")


class TestDerivePsycopgUrl:
    """Tests for derive_psycopg_url()."""

    def test_strips_asyncpg(self):
        """should strip +asyncpg from DATABASE_URL."""
        url = "postgresql+asyncpg://user:pass@localhost:5433/summit-cap"
        assert derive_psycopg_url(url) == "postgresql://user:pass@localhost:5433/summit-cap"

    def test_already_plain(self):
        """should handle URL without driver prefix."""
        url = "postgresql://user:pass@localhost:5433/summit-cap"
        assert derive_psycopg_url(url) == "postgresql://user:pass@localhost:5433/summit-cap"


class TestInitialize:
    """Tests for ConversationService.initialize()."""

    @pytest.mark.asyncio
    async def test_initialize_creates_working_checkpointer(self):
        """should create a connection pool and call setup() on AsyncPostgresSaver."""
        service = ConversationService()
        mock_pool = AsyncMock()
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()

        with (
            patch(
                "src.services.conversation.AsyncConnectionPool",
                return_value=mock_pool,
            ) as mock_pool_cls,
            patch(
                "langgraph.checkpoint.postgres.aio.AsyncPostgresSaver",
                return_value=mock_saver,
            ),
        ):
            await service.initialize("postgresql+asyncpg://user:pass@localhost:5433/summit-cap")

        mock_pool_cls.assert_called_once()
        # Verify the pool was opened
        mock_pool.open.assert_awaited_once()
        mock_saver.setup.assert_awaited_once()
        assert service.is_initialized is True
        assert service._pool is mock_pool


class TestShutdown:
    """Tests for ConversationService.shutdown()."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_connection(self):
        """should close the underlying connection pool."""
        service = ConversationService()
        mock_pool = AsyncMock()
        service._pool = mock_pool
        service._checkpointer = MagicMock()
        service._initialized = True

        await service.shutdown()

        mock_pool.close.assert_awaited_once()
        assert service._pool is None
        assert service._checkpointer is None
        assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_when_not_initialized(self):
        """should be safe to call when service was never initialized."""
        service = ConversationService()
        await service.shutdown()
        assert service.is_initialized is False


class TestClearConversation:
    """Tests for ConversationService.clear_conversation()."""

    @pytest.mark.asyncio
    async def test_returns_false_when_not_initialized(self):
        """should return False when service is not initialized."""
        service = ConversationService()
        result = await service.clear_conversation("any-thread")
        assert result is False

    @pytest.mark.asyncio
    async def test_deletes_from_all_three_tables(self):
        """should delete from checkpoint_writes, checkpoint_blobs, and checkpoints."""
        from contextlib import asynccontextmanager

        service = ConversationService()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def fake_connection():
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.connection = fake_connection
        service._pool = mock_pool
        service._initialized = True

        result = await service.clear_conversation("user:test:agent:uw")

        assert result is True
        assert mock_conn.execute.await_count == 3
        calls = [c.args for c in mock_conn.execute.await_args_list]
        tables = [c[0] for c in calls]
        assert "DELETE FROM checkpoint_writes WHERE thread_id = %s" in tables
        assert "DELETE FROM checkpoint_blobs WHERE thread_id = %s" in tables
        assert "DELETE FROM checkpoints WHERE thread_id = %s" in tables
        # All three calls pass the same thread_id
        for call_args in calls:
            assert call_args[1] == ("user:test:agent:uw",)

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        """should return False and not raise when database errors occur."""
        service = ConversationService()
        mock_pool = AsyncMock()
        mock_pool.connection.side_effect = RuntimeError("db down")
        service._pool = mock_pool
        service._initialized = True

        result = await service.clear_conversation("user:test:agent:uw")
        assert result is False
