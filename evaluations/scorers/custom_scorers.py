# This project was developed with assistance from AI tools.
"""Custom domain-specific scorers for mortgage agent evaluation.

These scorers perform lightweight, deterministic checks without requiring
LLM calls. They complement MLflow's built-in LLM judges.

MLflow scorers must return one of: int, float, bool, str, Feedback, or list[Feedback].
They cannot return dict - the dict format was deprecated.
"""

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
