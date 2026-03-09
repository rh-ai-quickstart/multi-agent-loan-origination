# This project was developed with assistance from AI tools.
"""Shared utilities for agent tool modules.

Tools use ``SessionLocal()`` for DB access because LangGraph tool nodes run
outside a FastAPI request lifecycle -- there is no ``Request`` object and no
``Depends(get_db)`` injection available.  Route handlers, by contrast, receive
a session via ``Depends(get_db)``.  Both paths ultimately use the same engine
and connection pool; the difference is only how the session is obtained.
"""

from db.enums import UserRole

from ..core.auth import build_data_scope
from ..schemas.auth import UserContext


def user_context_from_state(state: dict, *, default_role: str) -> UserContext:
    """Build a UserContext from the agent's graph state.

    Args:
        state: The LangGraph graph state dict containing user_id, user_role, etc.
        default_role: Fallback role string if user_role is missing from state.

    Raises:
        ValueError: If user_id is missing from state.
    """
    user_id = state.get("user_id")
    if not user_id:
        raise ValueError("user_id is required in agent state")
    role_str = state.get("user_role", default_role)
    role = UserRole(role_str)
    return UserContext(
        user_id=user_id,
        role=role,
        email=state.get("user_email") or f"{user_id}@example.com",
        name=state.get("user_name") or user_id,
        data_scope=build_data_scope(role, user_id),
    )


def format_enum_label(value: str) -> str:
    """Convert a snake_case enum value to a Title Case label.

    Example: ``"prior_to_approval"`` -> ``"Prior To Approval"``
    """
    return value.replace("_", " ").title()
