# This project was developed with assistance from AI tools.
"""Conversation persistence service -- manages LangGraph checkpoint storage.

Uses langgraph-checkpoint-postgres (AsyncPostgresSaver) to persist conversation
state per thread_id. Thread IDs are deterministic:
``user:{user_id}:agent:{agent_name}`` (user-scoped) or
``user:{user_id}:agent:{agent_name}:app:{app_id}`` (application-scoped),
ensuring authenticated users resume where they left off across sessions.

Prospects get ephemeral (random UUID) thread IDs that are never resumed.
"""

import logging
import re
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


def derive_psycopg_url(asyncpg_url: str) -> str:
    """Convert an asyncpg DATABASE_URL to a plain psycopg3-compatible URL.

    ``langgraph-checkpoint-postgres`` uses psycopg3 (not asyncpg), so we strip
    the ``+asyncpg`` driver prefix from the SQLAlchemy-style URL.

    Examples:
        >>> derive_psycopg_url("postgresql+asyncpg://user:pass@host/db")
        'postgresql://user:pass@host/db'
        >>> derive_psycopg_url("postgresql://user:pass@host/db")
        'postgresql://user:pass@host/db'
    """
    return asyncpg_url.replace("+asyncpg", "")


class ConversationService:
    """Manages LangGraph checkpoint persistence via AsyncPostgresSaver."""

    def __init__(self) -> None:
        self._checkpointer: Any | None = None
        self._pool: AsyncConnectionPool | None = None
        self._initialized: bool = False

    @property
    def is_initialized(self) -> bool:
        """Whether the checkpointer has been successfully initialized."""
        return self._initialized

    @property
    def checkpointer(self) -> Any:
        """Return the initialized AsyncPostgresSaver.

        Raises:
            RuntimeError: If called before successful initialization.
        """
        if not self._initialized or self._checkpointer is None:
            raise RuntimeError("ConversationService is not initialized")
        return self._checkpointer

    async def initialize(self, db_url: str) -> None:
        """Initialize the AsyncPostgresSaver checkpointer.

        Derives a psycopg3-compatible URL from the asyncpg DATABASE_URL,
        creates the checkpointer, and runs setup() to ensure checkpoint
        tables exist.

        Args:
            db_url: The asyncpg-style DATABASE_URL from settings.
        """
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            psycopg_url = derive_psycopg_url(db_url)
            pool = AsyncConnectionPool(
                psycopg_url,
                min_size=1,
                max_size=5,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            )
            await pool.open()
            self._pool = pool
            self._checkpointer = AsyncPostgresSaver(conn=pool)
            await self._checkpointer.setup()
            self._initialized = True
            logger.info("ConversationService initialized (checkpoint persistence active)")
        except Exception:
            logger.warning(
                "Failed to initialize ConversationService; "
                "chat will use ephemeral in-memory history",
                exc_info=True,
            )
            self._initialized = False

    async def shutdown(self) -> None:
        """Close the checkpointer's underlying connection pool."""
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:
                logger.debug("Error closing checkpointer pool", exc_info=True)
        self._pool = None
        self._checkpointer = None
        self._initialized = False

    @staticmethod
    def get_thread_id(
        user_id: str,
        agent_name: str = "public-assistant",
        application_id: int | None = None,
    ) -> str:
        """Build a deterministic thread ID for checkpoint persistence.

        Format without application:
            ``user:{user_id}:agent:{agent_name}``

        Format with application (for role-agents managing multiple apps):
            ``user:{user_id}:agent:{agent_name}:app:{application_id}``

        Args:
            user_id: The authenticated user's ID.
            agent_name: The agent name (supports multiple agents per user).
            application_id: Optional application ID for app-scoped conversations.

        Returns:
            A deterministic thread_id string.
        """
        base = f"user:{user_id}:agent:{agent_name}"
        if application_id is not None:
            return f"{base}:app:{application_id}"
        return base

    @staticmethod
    def verify_thread_ownership(thread_id: str, user_id: str) -> None:
        """Assert that *thread_id* belongs to *user_id*.

        Checks that the thread_id starts with ``user:{user_id}:``, regardless
        of the agent_name segment.  Raises :class:`PermissionError` on mismatch.

        Args:
            thread_id: The thread ID to verify.
            user_id: The authenticated user's ID.

        Raises:
            PermissionError: If thread_id does not belong to user_id.
        """
        expected_prefix = f"user:{user_id}:"
        if not thread_id.startswith(expected_prefix):
            raise PermissionError(f"Thread {thread_id!r} does not belong to user {user_id!r}")

    async def clear_conversation(self, thread_id: str) -> bool:
        """Delete all checkpoint data for *thread_id*.

        Removes rows from checkpoints, checkpoint_blobs, and checkpoint_writes
        so the next session starts fresh.

        Args:
            thread_id: The thread ID to clear.

        Returns:
            True if rows were deleted, False if nothing existed or service is
            not initialized.
        """
        if not self._initialized or self._pool is None:
            return False

        try:
            async with self._pool.connection() as conn:
                for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                    await conn.execute(
                        f"DELETE FROM {table} WHERE thread_id = %s",  # noqa: S608
                        (thread_id,),
                    )
            return True
        except Exception:
            logger.warning("Failed to clear conversation for %s", thread_id, exc_info=True)
            return False

    async def get_conversation_history(self, thread_id: str) -> list[dict]:
        """Load conversation messages from the checkpoint for *thread_id*.

        Returns a list of serializable message dicts (for resumption UX).
        Returns an empty list if no checkpoint exists.

        Args:
            thread_id: The thread ID to load history for.

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """
        if not self._initialized or self._checkpointer is None:
            return []

        try:
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint_tuple = await self._checkpointer.aget_tuple(config)
            if checkpoint_tuple is None:
                return []

            checkpoint = checkpoint_tuple.checkpoint
            messages = checkpoint.get("channel_values", {}).get("messages", [])
            result = []
            for msg in messages:
                msg_type = getattr(msg, "type", "")
                if msg_type == "ai":
                    role = "assistant"
                elif msg_type == "human":
                    role = "user"
                else:
                    continue  # skip tool, system, and function messages
                content = getattr(msg, "content", str(msg))
                if content and role == "assistant":
                    # Clean LLM artifacts that were stored raw in checkpoints
                    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
                    content = content.replace("**", "")
                    content = re.sub(r"\[[^\]]*\w+\(.*?\)[^\]]*\]", "", content)
                    content = content.strip()
                if content:
                    result.append({"role": role, "content": content})
            return result
        except Exception:
            logger.warning("Failed to load conversation history for %s", thread_id, exc_info=True)
            return []


# Module-level singleton
_service = ConversationService()


def get_conversation_service() -> ConversationService:
    """Return the module-level ConversationService singleton."""
    return _service
