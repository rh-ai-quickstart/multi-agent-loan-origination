# This project was developed with assistance from AI tools.
"""Tests for _record_token_usage in agents/base.py."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.base import _record_token_usage


def _make_response(content="Hello", response_metadata=None, usage_metadata=None):
    """Build an AIMessage with configurable metadata."""
    msg = AIMessage(content=content)
    msg.response_metadata = response_metadata or {}
    if usage_metadata is not None:
        msg.usage_metadata = usage_metadata
    return msg


@patch("src.agents.base.llm_tokens_total")
def test_should_record_provider_tokens_when_present(mock_counter):
    mock_label = MagicMock()
    mock_counter.labels.return_value = mock_label
    response = _make_response(
        response_metadata={"token_usage": {"prompt_tokens": 150, "completion_tokens": 50}}
    )

    _record_token_usage(response, [HumanMessage(content="Hi")], "test-model", "borrower")

    calls = mock_label.inc.call_args_list
    assert len(calls) == 2
    assert calls[0].args[0] == 150
    assert calls[1].args[0] == 50


@patch("src.agents.base.llm_tokens_total")
def test_should_estimate_when_provider_returns_zeros(mock_counter):
    mock_label = MagicMock()
    mock_counter.labels.return_value = mock_label
    response = _make_response(
        content="Hello world response",
        response_metadata={"token_usage": {"prompt_tokens": 0, "completion_tokens": 0}},
    )

    _record_token_usage(
        response, [HumanMessage(content="Tell me about loans")], "test-model", "ceo"
    )

    calls = mock_label.inc.call_args_list
    assert len(calls) == 2
    assert calls[0].args[0] > 0
    assert calls[1].args[0] > 0


@patch("src.agents.base.llm_tokens_total")
def test_should_estimate_when_no_usage_metadata(mock_counter):
    mock_label = MagicMock()
    mock_counter.labels.return_value = mock_label
    response = _make_response(content="Response text", response_metadata={})

    _record_token_usage(response, [HumanMessage(content="Input text")], "test-model", "prospect")

    calls = mock_label.inc.call_args_list
    assert len(calls) == 2
    assert calls[0].args[0] >= 1
    assert calls[1].args[0] >= 1


@patch("src.agents.base.llm_tokens_total")
def test_should_use_input_tokens_key_when_prompt_tokens_absent(mock_counter):
    mock_label = MagicMock()
    mock_counter.labels.return_value = mock_label
    response = _make_response(
        response_metadata={"usage": {"input_tokens": 200, "output_tokens": 80}}
    )

    _record_token_usage(response, [HumanMessage(content="Hi")], "test-model", "borrower")

    calls = mock_label.inc.call_args_list
    assert len(calls) == 2
    assert calls[0].args[0] == 200
    assert calls[1].args[0] == 80


@patch("src.agents.base.llm_tokens_total")
def test_should_use_usage_metadata_attribute(mock_counter):
    mock_label = MagicMock()
    mock_counter.labels.return_value = mock_label
    um = MagicMock()
    um.input_tokens = 300
    um.output_tokens = 120
    response = _make_response(content="Reply", response_metadata={}, usage_metadata=um)

    _record_token_usage(response, [HumanMessage(content="Hi")], "test-model", "underwriter")

    calls = mock_label.inc.call_args_list
    assert len(calls) == 2
    assert calls[0].args[0] == 300
    assert calls[1].args[0] == 120
