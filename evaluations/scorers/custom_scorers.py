# This project was developed with assistance from AI tools.
"""Custom domain-specific scorers for mortgage agent evaluation.

These scorers perform lightweight, deterministic checks without requiring
LLM calls. They complement MLflow's built-in LLM judges.

MLflow scorers must return one of: int, float, bool, str, Feedback, or list[Feedback].
They cannot return dict - the dict format was deprecated.
"""

from mlflow.genai.scorers import scorer

from ..predictors import get_last_tool_calls


@scorer
def contains_expected(
    inputs: dict, outputs: str, expectations: dict
) -> bool:
    """Check if output contains expected answer keyword.

    Args:
        inputs: The input dict containing user_message
        outputs: The model's response text
        expectations: Dict containing expected_answer keyword

    Returns:
        True if expected keyword found in response, False otherwise
    """
    expected = expectations.get("expected_answer", "")
    if not expected:
        return True  # No expected answer specified

    return str(expected).lower() in str(outputs).lower()


@scorer
def avoids_forbidden(outputs: str, expectations: dict) -> bool:
    """Check output avoids forbidden content.

    Args:
        outputs: The model's response text
        expectations: Dict containing forbidden_content list

    Returns:
        True if no forbidden content found, False otherwise
    """
    forbidden = expectations.get("forbidden_content", [])
    if not forbidden:
        return True  # No forbidden content specified

    found_forbidden = [f for f in forbidden if f.lower() in str(outputs).lower()]
    return len(found_forbidden) == 0


@scorer
def mentions_expected_topics(outputs: str, expectations: dict) -> float:
    """Score based on how many expected topics are mentioned.

    Args:
        outputs: The model's response text
        expectations: Dict containing expected_topics list

    Returns:
        Float between 0-1 representing proportion of topics mentioned
    """
    topics = expectations.get("expected_topics", [])
    if not topics:
        return 1.0  # No expected topics specified

    mentioned = [t for t in topics if t.lower() in str(outputs).lower()]
    return len(mentioned) / len(topics)


@scorer
def response_length_appropriate(outputs: str) -> float:
    """Score response length appropriateness.

    Optimal response length is 100-500 characters for most queries.
    Too short may indicate incomplete answers.
    Too long may indicate verbosity or hallucination.

    Args:
        outputs: The model's response text

    Returns:
        Float between 0-1 representing length appropriateness
    """
    length = len(str(outputs))

    if length < 50:
        return 0.3  # Too short, may be incomplete
    elif length < 100:
        return 0.6  # Somewhat short
    elif length <= 500:
        return 1.0  # Optimal
    elif length <= 1000:
        return 0.8  # Somewhat long
    else:
        return 0.5  # Too long, may be verbose


@scorer
def professional_tone(outputs: str) -> bool:
    """Check for professional language markers.

    Args:
        outputs: The model's response text

    Returns:
        True if professional tone, False if unprofessional language found
    """
    outputs_lower = str(outputs).lower()

    unprofessional = ["dude", "bro", "lol", "idk", "wtf", "omg"]

    found_unprofessional = [m for m in unprofessional if m in outputs_lower]
    return len(found_unprofessional) == 0


@scorer
def has_numeric_result(outputs: str) -> bool:
    """Check if response contains numeric values (useful for calculation queries).

    Args:
        outputs: The model's response text

    Returns:
        True if response contains numbers (dollar amounts, percentages, etc.)
    """
    import re

    # Look for dollar amounts, percentages, or plain numbers
    patterns = [
        r"\$[\d,]+",  # Dollar amounts like $100,000
        r"\d+%",  # Percentages like 6.5%
        r"\d{1,3}(,\d{3})+",  # Large numbers with commas
    ]

    for pattern in patterns:
        if re.search(pattern, str(outputs)):
            return True
    return False


@scorer
def response_length(outputs: str) -> float:
    """Score response length (simplified version).

    Returns 1.0 for responses with reasonable length (50+ chars).

    Args:
        outputs: The model's response text

    Returns:
        1.0 if adequate length, 0.5 otherwise
    """
    length = len(str(outputs))
    return 1.0 if length >= 50 else 0.5


@scorer
def tool_calls_match(expectations: dict, trace) -> bool:
    """Check if expected tools were called during agent execution.

    This scorer extracts tool calls from the MLflow trace and compares
    against the expected_tools list in the dataset expectations.

    Args:
        expectations: Dict containing expected_tools list
        trace: MLflow trace object containing span information

    Returns:
        True if all expected tools were called, False otherwise.
        Returns True if no expected tools specified (pass by default).
    """
    import logging
    logger = logging.getLogger(__name__)

    expected_tools = expectations.get("expected_tools", [])
    if not expected_tools:
        return True  # No expected tools specified, pass

    # Extract actual tool calls from trace
    actual_tools = set()

    if trace is None:
        logger.debug("tool_calls_match: trace is None")
        return False

    # Debug: log trace structure
    logger.debug(f"tool_calls_match: trace type={type(trace)}, attrs={dir(trace)[:10]}")

    # Method 1: Try search_spans for TOOL type
    try:
        if hasattr(trace, "search_spans"):
            spans = list(trace.search_spans(span_type="TOOL"))
            logger.debug(f"tool_calls_match: TOOL spans found: {len(spans)}")
            for span in spans:
                name = getattr(span, "name", "")
                logger.debug(f"tool_calls_match: TOOL span name={name}")
                if name:
                    actual_tools.add(name)
    except Exception as e:
        logger.debug(f"tool_calls_match: search_spans error: {e}")

    # Method 2: Try to iterate all spans and check span_type
    try:
        if hasattr(trace, "data") and hasattr(trace.data, "spans"):
            for span in trace.data.spans:
                span_type = getattr(span, "span_type", None)
                name = getattr(span, "name", "")
                logger.debug(f"tool_calls_match: span name={name}, type={span_type}")
                # Check if it's a TOOL span or matches our tool names
                if span_type == "TOOL" or name in [
                    "product_info", "affordability_calc", "kb_search",
                    "current_date", "list_my_applications"
                ]:
                    actual_tools.add(name)
    except Exception as e:
        logger.debug(f"tool_calls_match: data.spans error: {e}")

    logger.debug(f"tool_calls_match: expected={expected_tools}, actual={actual_tools}")

    # Check if all expected tools were called
    for tool in expected_tools:
        if tool not in actual_tools:
            return False

    return True
