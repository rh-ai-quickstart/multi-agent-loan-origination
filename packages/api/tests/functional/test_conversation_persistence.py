# This project was developed with assistance from AI tools.
"""Functional tests for conversation persistence using MemorySaver.

Uses MemorySaver (in-memory checkpointer from langgraph.checkpoint.memory) instead
of AsyncPostgresSaver to avoid requiring PostgreSQL. MemorySaver provides the same
checkpointing interface so these tests validate the persistence contract.
"""

import uuid

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph

from src.services.conversation import ConversationService


def _build_echo_graph(checkpointer=None):
    """Build a minimal graph that echoes user input -- for testing checkpointing."""

    class EchoState(MessagesState):
        user_role: str
        user_id: str

    def echo(state: EchoState) -> dict:
        last = state["messages"][-1]
        return {"messages": [AIMessage(content=f"Echo: {last.content}")]}

    graph = StateGraph(EchoState)
    graph.add_node("echo", echo)
    graph.set_entry_point("echo")
    graph.add_edge("echo", END)
    return graph.compile(checkpointer=checkpointer)


@pytest.mark.functional
class TestGraphCheckpointing:
    """Tests for LangGraph checkpointer integration."""

    def test_graph_compiles_with_checkpointer(self):
        """should compile a graph with MemorySaver checkpointer."""
        saver = MemorySaver()
        graph = _build_echo_graph(checkpointer=saver)
        assert graph is not None

    def test_checkpointer_persists_messages(self):
        """should see first message in state on second invocation with same thread_id."""
        saver = MemorySaver()
        graph = _build_echo_graph(checkpointer=saver)
        thread_id = "test-thread-1"
        config = {"configurable": {"thread_id": thread_id}}

        # First invocation
        result1 = graph.invoke(
            {"messages": [HumanMessage(content="Hello")], "user_role": "prospect", "user_id": "u1"},
            config=config,
        )
        assert any("Echo: Hello" in m.content for m in result1["messages"] if hasattr(m, "content"))

        # Second invocation -- only send new message; checkpoint has prior state
        result2 = graph.invoke(
            {
                "messages": [HumanMessage(content="Follow up")],
                "user_role": "prospect",
                "user_id": "u1",
            },
            config=config,
        )
        contents = [m.content for m in result2["messages"] if hasattr(m, "content")]
        # Should contain both the original "Hello" exchange and the follow-up
        assert any("Hello" in c for c in contents), f"Expected prior 'Hello' in {contents}"
        assert any("Follow up" in c for c in contents), f"Expected 'Follow up' in {contents}"

    def test_different_threads_isolated(self):
        """should keep conversations independent across different thread_ids."""
        saver = MemorySaver()
        graph = _build_echo_graph(checkpointer=saver)

        config_a = {"configurable": {"thread_id": "thread-a"}}
        config_b = {"configurable": {"thread_id": "thread-b"}}

        graph.invoke(
            {
                "messages": [HumanMessage(content="Thread A message")],
                "user_role": "prospect",
                "user_id": "u1",
            },
            config=config_a,
        )

        result_b = graph.invoke(
            {
                "messages": [HumanMessage(content="Thread B message")],
                "user_role": "prospect",
                "user_id": "u2",
            },
            config=config_b,
        )
        contents = [m.content for m in result_b["messages"] if hasattr(m, "content")]
        # Thread B should NOT contain Thread A's message
        assert not any("Thread A" in c for c in contents), "Cross-thread leak detected"

    def test_new_thread_starts_empty(self):
        """should start with no prior messages on a new thread_id."""
        saver = MemorySaver()
        graph = _build_echo_graph(checkpointer=saver)
        config = {"configurable": {"thread_id": "fresh-thread"}}

        result = graph.invoke(
            {
                "messages": [HumanMessage(content="First message")],
                "user_role": "prospect",
                "user_id": "u1",
            },
            config=config,
        )
        # Should have exactly 2 messages: the human input + the echo response
        assert len(result["messages"]) == 2

    def test_prospect_ephemeral_thread_not_reused(self):
        """should produce isolated sessions with random UUID thread_ids."""
        saver = MemorySaver()
        graph = _build_echo_graph(checkpointer=saver)

        # Simulate two prospect sessions (each gets a random UUID)
        tid1 = str(uuid.uuid4())
        tid2 = str(uuid.uuid4())

        graph.invoke(
            {
                "messages": [HumanMessage(content="Session 1 secret")],
                "user_role": "prospect",
                "user_id": tid1,
            },
            config={"configurable": {"thread_id": tid1}},
        )

        result2 = graph.invoke(
            {
                "messages": [HumanMessage(content="Session 2 message")],
                "user_role": "prospect",
                "user_id": tid2,
            },
            config={"configurable": {"thread_id": tid2}},
        )
        contents = [m.content for m in result2["messages"] if hasattr(m, "content")]
        assert not any("Session 1" in c for c in contents), "Ephemeral sessions leaked"

    def test_verify_rejects_cross_user_access(self):
        """should block mismatched user from accessing another user's thread."""
        thread_id = ConversationService.get_thread_id("sarah-001", "borrower-assistant")
        with pytest.raises(PermissionError):
            ConversationService.verify_thread_ownership(thread_id, "james-002")


@pytest.mark.functional
class TestGetConversationHistory:
    """Tests for ConversationService.get_conversation_history()."""

    @pytest.mark.asyncio
    async def test_returns_messages_after_invocation(self):
        """should return prior messages from checkpoint after graph invocation."""
        saver = MemorySaver()
        graph = _build_echo_graph(checkpointer=saver)
        thread_id = "history-test-thread"
        config = {"configurable": {"thread_id": thread_id}}

        graph.invoke(
            {
                "messages": [HumanMessage(content="Hello there")],
                "user_role": "borrower",
                "user_id": "u1",
            },
            config=config,
        )

        service = ConversationService()
        service._checkpointer = saver
        service._initialized = True

        history = await service.get_conversation_history(thread_id)
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello there"}
        assert history[1]["role"] == "assistant"
        assert "Echo: Hello there" in history[1]["content"]

    @pytest.mark.asyncio
    async def test_empty_thread_returns_empty_list(self):
        """should return empty list for a thread with no prior messages."""
        saver = MemorySaver()
        service = ConversationService()
        service._checkpointer = saver
        service._initialized = True

        history = await service.get_conversation_history("nonexistent-thread")
        assert history == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_initialized(self):
        """should return empty list when service is not initialized."""
        service = ConversationService()
        history = await service.get_conversation_history("any-thread")
        assert history == []

    @pytest.mark.asyncio
    async def test_excludes_tool_messages(self):
        """should exclude tool/function messages from history, keeping only human and ai."""
        from langchain_core.messages import ToolMessage

        saver = MemorySaver()
        # Build a graph that produces a tool message followed by an AI response
        graph = _build_echo_graph(checkpointer=saver)
        thread_id = "tool-filter-test"
        config = {"configurable": {"thread_id": thread_id}}

        # Invoke to create checkpoint state
        graph.invoke(
            {
                "messages": [HumanMessage(content="Hello")],
                "user_role": "underwriter",
                "user_id": "uw-1",
            },
            config=config,
        )

        # Manually inject a tool message into the checkpoint to simulate agent tool calls
        state = graph.get_state(config)
        messages = list(state.values["messages"])
        messages.insert(
            1,
            ToolMessage(content="tool result data", tool_call_id="tc-1"),
        )
        graph.update_state(config, {"messages": messages})

        service = ConversationService()
        service._checkpointer = saver
        service._initialized = True

        history = await service.get_conversation_history(thread_id)

        # Should only have human + ai, no tool messages
        roles = [m["role"] for m in history]
        assert "user" in roles
        assert "assistant" in roles
        assert all(r in ("user", "assistant") for r in roles)
        # Tool content should not appear
        assert not any("tool result data" in m["content"] for m in history)
