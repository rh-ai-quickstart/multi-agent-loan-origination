# This project was developed with assistance from AI tools.
"""Custom domain-specific scorers for mortgage agent evaluation.

These scorers perform lightweight, deterministic checks without requiring
LLM calls. They complement MLflow's built-in LLM judges.

MLflow scorers must return one of: int, float, bool, str, Feedback, or list[Feedback].
"""

import re

from mlflow.genai.scorers import scorer


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
def has_numeric_result(outputs: str) -> bool:
    """Check if response contains numeric values (useful for calculation queries).

    Args:
        outputs: The model's response text

    Returns:
        True if response contains numbers (dollar amounts, percentages, etc.)
    """
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
