# This project was developed with assistance from AI tools.
"""Tests for response cleaning logic applied to LLM output.

The chat handler applies a series of regex transformations to raw LLM output
before sending it to the client or storing it in conversation history.  These
tests verify the cleaning pipeline in isolation.
"""

import re


def _clean_response(raw: str) -> str:
    """Mirror the cleaning pipeline from _chat_handler.py lines 402-408."""
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    text = text.replace("**", "")
    text = re.sub(r"\[[^\]]*\w+\(.*?\)[^\]]*\]", "", text)
    text = text.strip()
    return text


class TestThinkTagStripping:
    """Think-tag removal from reasoning model output."""

    def test_strips_single_think_block(self):
        """should remove a single <think>...</think> block."""
        raw = "<think>reasoning here</think>Hello!"
        assert _clean_response(raw) == "Hello!"

    def test_strips_multiline_think_block(self):
        """should remove think blocks spanning multiple lines."""
        raw = "<think>\nstep 1\nstep 2\nstep 3\n</think>\nHere is my answer."
        assert _clean_response(raw) == "Here is my answer."

    def test_strips_multiple_think_blocks(self):
        """should remove multiple think blocks in a single response."""
        raw = "<think>first</think>Hello!<think>second</think> Goodbye!"
        assert _clean_response(raw) == "Hello! Goodbye!"

    def test_strips_leading_whitespace_after_think(self):
        """should strip leading newlines left after think-tag removal."""
        raw = "<think>reasoning</think>\n\nActual answer"
        assert _clean_response(raw) == "Actual answer"

    def test_no_think_tags_unchanged(self):
        """should pass through responses without think tags."""
        raw = "Just a normal response."
        assert _clean_response(raw) == "Just a normal response."

    def test_empty_think_block(self):
        """should handle empty think blocks."""
        raw = "<think></think>Answer"
        assert _clean_response(raw) == "Answer"


class TestBoldMarkerStripping:
    """Markdown bold marker removal."""

    def test_strips_bold_markers(self):
        """should remove ** bold markers."""
        raw = "Here are our **mortgage products**:"
        assert _clean_response(raw) == "Here are our mortgage products:"

    def test_multiple_bold_markers(self):
        """should remove all bold markers."""
        raw = "**30-Year Fixed** and **FHA Loan**"
        assert _clean_response(raw) == "30-Year Fixed and FHA Loan"


class TestInlineToolCallStripping:
    """Inline tool-call text removal (small models emit these as text)."""

    def test_strips_inline_tool_call(self):
        """should remove bracketed tool-call text."""
        raw = 'Let me check. [lo_search_applications(query="active")] You have 3 loans.'
        assert _clean_response(raw) == "Let me check.  You have 3 loans."

    def test_strips_multiple_tool_calls(self):
        """should remove multiple inline tool calls."""
        raw = "Checking [tool_a(x=1)] and [tool_b(y=2)] done."
        assert _clean_response(raw) == "Checking  and  done."

    def test_preserves_normal_brackets(self):
        """should not remove brackets without function-call syntax."""
        raw = "Interest rates are [currently competitive]."
        assert _clean_response(raw) == "Interest rates are [currently competitive]."


class TestCombinedCleaning:
    """End-to-end cleaning with multiple artifact types."""

    def test_think_plus_bold_plus_tool_call(self):
        """should clean all artifact types in a single pass."""
        raw = (
            "<think>I should look this up</think>\n\n"
            "**Great question!** Let me check.\n"
            '[lo_search_applications(query="test")]\n'
            "You have 2 active applications."
        )
        result = _clean_response(raw)
        assert "<think>" not in result
        assert "**" not in result
        assert "lo_search_applications" not in result
        assert "Great question!" in result
        assert "You have 2 active applications." in result

    def test_safety_refusal_passes_through(self):
        """should not alter safety refusal messages."""
        raw = "I'm not able to help with that request. Can I assist you with something else?"
        assert _clean_response(raw) == raw

    def test_empty_after_stripping(self):
        """should return empty string when all content is artifacts."""
        raw = "<think>just thinking</think>"
        assert _clean_response(raw) == ""
