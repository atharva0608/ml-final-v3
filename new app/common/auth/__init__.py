"""
Common Authentication Utilities for CloudOptim Agentless Architecture

Shared authentication logic for:
- ML Server ↔ Core Platform API key authentication
- Admin Frontend ↔ Core Platform JWT authentication
- Customer API authentication
"""

from .api_key import (
    APIKeyManager,
    verify_api_key,
    create_api_key,
    hash_api_key,
)

from .jwt_auth import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)

from .middleware import (
    require_api_key,
    require_jwt,
    get_current_user,
)

__all__ = [
    # API Key
    "APIKeyManager",
    "verify_api_key",
    "create_api_key",
    "hash_api_key",

    # JWT
    "JWTManager",
    "create_access_token",
    "create_refresh_token",
    "verify_access_token",
    "verify_refresh_token",

    # Middleware
    "require_api_key",
    "require_jwt",
    "get_current_user",
]
