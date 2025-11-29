"""
FastAPI Authentication Middleware for CloudOptim

Dependency injection functions for protecting API endpoints.
"""

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from .api_key import verify_api_key as _verify_api_key
from .jwt_auth import verify_access_token as _verify_access_token


# Security schemes
security = HTTPBearer()


async def require_api_key(
    x_api_key: Optional[str] = Header(None, description="API Key for service authentication")
) -> dict:
    """
    FastAPI dependency to require API key authentication

    Usage:
        @app.get("/api/v1/protected", dependencies=[Depends(require_api_key)])
        async def protected_endpoint():
            return {"message": "This endpoint requires API key"}

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        API key metadata (service_name, etc.)

    Raises:
        HTTPException: 401 if API key invalid or missing
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # NOTE: In production, fetch stored_keys from database
    # For now, this is a placeholder showing the verification pattern
    # Each component should implement its own key storage/retrieval

    # Example verification (replace with actual database lookup)
    # stored_keys = await db.get_api_keys()  # Fetch from database
    # key_info = _verify_api_key(x_api_key, stored_keys)

    # Placeholder: Accept any key starting with "sk_"
    if not x_api_key.startswith("sk_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Return API key metadata (in production, from database)
    return {
        "service_name": "placeholder",  # Replace with actual service name from DB
        "authenticated": True,
    }


async def require_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPI dependency to require JWT authentication

    Usage:
        @app.get("/api/v1/protected")
        async def protected_endpoint(user: dict = Depends(require_jwt)):
            return {"message": f"Hello {user['email']}"}

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User information from JWT payload

    Raises:
        HTTPException: 401 if JWT invalid or missing
    """
    token = credentials.credentials

    try:
        payload = _verify_access_token(token)
    except Exception:
        payload = None

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role", "user"),
        "authenticated": True,
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPI dependency to get current user from JWT

    Alias for require_jwt with more descriptive name.

    Usage:
        @app.get("/api/v1/me")
        async def get_me(user: dict = Depends(get_current_user)):
            return user

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User information from JWT payload

    Raises:
        HTTPException: 401 if JWT invalid or missing
    """
    return await require_jwt(credentials)


async def optional_auth(
    x_api_key: Optional[str] = Header(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    FastAPI dependency for optional authentication

    Tries JWT first, then API key, returns None if neither present.

    Usage:
        @app.get("/api/v1/resource")
        async def get_resource(auth: dict = Depends(optional_auth)):
            if auth:
                # Authenticated user
                return {"data": "private", "user": auth}
            else:
                # Public access
                return {"data": "public"}

    Args:
        x_api_key: Optional API key from header
        credentials: Optional Bearer token from header

    Returns:
        Auth info if authenticated, None otherwise
    """
    # Try JWT first
    if credentials:
        try:
            payload = _verify_access_token(credentials.credentials)
            if payload:
                return {
                    "user_id": payload.get("sub"),
                    "email": payload.get("email"),
                    "role": payload.get("role", "user"),
                    "auth_type": "jwt",
                }
        except Exception:
            pass

    # Try API key
    if x_api_key and x_api_key.startswith("sk_"):
        return {
            "service_name": "placeholder",  # Replace with actual DB lookup
            "auth_type": "api_key",
        }

    # No authentication
    return None


def require_role(required_role: str):
    """
    Factory function to create role-based access control dependency

    Usage:
        @app.delete("/api/v1/admin/users/{user_id}", dependencies=[Depends(require_role("admin"))])
        async def delete_user(user_id: str):
            return {"message": f"User {user_id} deleted"}

    Args:
        required_role: Required role (e.g., "admin", "user")

    Returns:
        FastAPI dependency function
    """
    async def role_checker(user: dict = Depends(require_jwt)) -> dict:
        user_role = user.get("role", "user")
        if user_role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}",
            )
        return user

    return role_checker
