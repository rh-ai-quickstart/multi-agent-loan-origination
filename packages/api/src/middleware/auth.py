# This project was developed with assistance from AI tools.
"""
JWT authentication middleware for Keycloak OIDC.

Validates Bearer tokens against Keycloak's JWKS endpoint, extracts user
identity and role, and provides FastAPI dependencies for route-level auth.

Set AUTH_DISABLED=true to bypass validation (tests / local dev without Keycloak).
"""

import logging
import time
from typing import Annotated

import httpx
import jwt
from db.enums import UserRole
from fastapi import Depends, HTTPException, Request, status

from ..core.auth import build_data_scope
from ..core.config import settings
from ..schemas.auth import TokenPayload, UserContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------

_jwks_data: dict | None = None
_jwks_fetched_at: float = 0


async def _fetch_jwks() -> dict:
    """Fetch JSON Web Key Set from Keycloak. Raises on failure."""
    url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


async def _get_jwks(force_refresh: bool = False) -> dict:
    """Return cached JWKS, refreshing if stale or forced."""
    global _jwks_data, _jwks_fetched_at  # noqa: PLW0603

    now = time.time()
    if _jwks_data is None or force_refresh or (now - _jwks_fetched_at) > settings.JWKS_CACHE_TTL:
        _jwks_data = await _fetch_jwks()
        _jwks_fetched_at = now

    return _jwks_data


async def _get_signing_key(token: str) -> jwt.PyJWK:
    """Find the signing key for the given token from the JWKS."""
    try:
        jwks = await _get_jwks()
        jwk_set = jwt.PyJWKSet.from_dict(jwks)
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        for key in jwk_set.keys:
            if key.key_id == kid:
                return key

        # kid not found -- cache-bust and retry once (key rotation)
        jwks = await _get_jwks(force_refresh=True)
        jwk_set = jwt.PyJWKSet.from_dict(jwks)
        for key in jwk_set.keys:
            if key.key_id == kid:
                return key

        raise ValueError(f"No matching key found for kid={kid}")

    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.error("Failed to fetch JWKS from Keycloak: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from exc


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


def _extract_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:]
    return None


async def _decode_token(token: str) -> TokenPayload:
    """Validate and decode a JWT against Keycloak's JWKS."""
    signing_key = await _get_signing_key(token)
    issuer = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"

    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=issuer,
        audience=settings.KEYCLOAK_CLIENT_ID,
        options={"verify_aud": True},
    )
    return TokenPayload(**payload)


def _resolve_role(token_payload: TokenPayload) -> UserRole:
    """Extract the primary role from realm_access.roles.

    Raises:
        ValueError: If no recognized role is assigned.
    """
    roles = token_payload.realm_access.get("roles", [])

    # Filter to roles we actually define (ignore Keycloak built-ins)
    known = set(UserRole.__members__.values())
    user_roles = [r for r in roles if r in {role.value for role in known}]

    if not user_roles:
        raise ValueError("No recognized role assigned")

    if len(user_roles) > 1:
        logger.warning(
            "User %s has multiple roles %s, using first: %s",
            token_payload.sub,
            user_roles,
            user_roles[0],
        )

    return UserRole(user_roles[0])


# build_data_scope is re-exported from core.auth for backward compatibility
__all__ = ["build_data_scope"]

# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_DEV_ROLE_MAP = {r.value: r for r in UserRole}


def _build_dev_user(
    role: UserRole,
    *,
    user_id: str = "dev-user",
    email: str = "dev@summit-cap.local",
    name: str | None = None,
) -> UserContext:
    """Build a dev user context for the given role."""
    display_name = name or f"Dev {role.value.replace('_', ' ').title()}"
    return UserContext(
        user_id=user_id,
        role=role,
        email=email,
        name=display_name,
        data_scope=build_data_scope(role, user_id),
    )


async def get_current_user(request: Request) -> UserContext:
    """FastAPI dependency: validate JWT and return UserContext.

    When AUTH_DISABLED=true, returns a dev user without token validation.
    The role defaults to ADMIN but can be overridden with the ``X-Dev-Role``
    header (e.g., ``X-Dev-Role: borrower``) for testing per-role UI views.
    """
    if settings.AUTH_DISABLED:
        role_header = request.headers.get("x-dev-role")
        role = _DEV_ROLE_MAP.get(role_header.lower()) if role_header else None
        dev_user = _build_dev_user(
            role or UserRole.ADMIN,
            user_id=request.headers.get("x-dev-user-id", "dev-user"),
            email=request.headers.get("x-dev-user-email", "dev@summit-cap.local"),
            name=request.headers.get("x-dev-user-name"),
        )
        request.state.pii_mask = dev_user.data_scope.pii_mask
        return dev_user

    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = await _decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        role = _resolve_role(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    data_scope = build_data_scope(role, payload.sub)

    user = UserContext(
        user_id=payload.sub,
        role=role,
        email=payload.email,
        name=payload.name or payload.preferred_username,
        data_scope=data_scope,
    )
    request.state.pii_mask = user.data_scope.pii_mask
    return user


# Type alias for use in route signatures
CurrentUser = Annotated[UserContext, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole):
    """Dependency factory: restrict a route to specific roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_roles(UserRole.ADMIN))])
    """

    async def _check(user: CurrentUser) -> UserContext:
        if user.role not in allowed_roles:
            logger.warning(
                "RBAC denied: user=%s role=%s attempted route requiring %s",
                user.user_id,
                user.role.value,
                [r.value for r in allowed_roles],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check
