"""
JWT Authentication for Admin Frontend ↔ Core Platform Communication

Provides JWT token generation and verification for user sessions.
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class JWTManager:
    """
    Manages JWT token creation and verification

    Used for:
    - Admin Frontend → Core Platform authentication
    - User session management
    """

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """
        Initialize JWT Manager

        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT signing algorithm (default: HS256)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_access_token(
        self,
        subject: str,
        expires_delta: timedelta = timedelta(hours=1),
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create an access token

        Args:
            subject: Subject (usually user ID or email)
            expires_delta: Token expiration time
            additional_claims: Additional JWT claims

        Returns:
            Encoded JWT token string
        """
        expires_at = datetime.utcnow() + expires_delta
        payload = {
            "sub": subject,
            "exp": expires_at,
            "iat": datetime.utcnow(),
            "type": "access",
        }

        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self,
        subject: str,
        expires_delta: timedelta = timedelta(days=7)
    ) -> str:
        """
        Create a refresh token

        Args:
            subject: Subject (usually user ID or email)
            expires_delta: Token expiration time

        Returns:
            Encoded JWT refresh token string
        """
        expires_at = datetime.utcnow() + expires_delta
        payload = {
            "sub": subject,
            "exp": expires_at,
            "iat": datetime.utcnow(),
            "type": "refresh",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            # Token expired
            return None
        except jwt.InvalidTokenError:
            # Invalid token
            return None

    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify an access token

        Args:
            token: JWT access token string

        Returns:
            Decoded payload if valid access token, None otherwise
        """
        payload = self.verify_token(token)
        if payload and payload.get("type") == "access":
            return payload
        return None

    def verify_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a refresh token

        Args:
            token: JWT refresh token string

        Returns:
            Decoded payload if valid refresh token, None otherwise
        """
        payload = self.verify_token(token)
        if payload and payload.get("type") == "refresh":
            return payload
        return None


# Convenience functions for global JWT manager instance
_jwt_manager: Optional[JWTManager] = None


def init_jwt_manager(secret_key: str, algorithm: str = "HS256"):
    """
    Initialize global JWT manager

    Args:
        secret_key: Secret key for signing tokens
        algorithm: JWT signing algorithm
    """
    global _jwt_manager
    _jwt_manager = JWTManager(secret_key, algorithm)


def get_jwt_manager() -> JWTManager:
    """
    Get global JWT manager instance

    Returns:
        JWTManager instance

    Raises:
        RuntimeError: If JWT manager not initialized
    """
    if _jwt_manager is None:
        raise RuntimeError("JWT manager not initialized. Call init_jwt_manager() first.")
    return _jwt_manager


def create_access_token(
    subject: str,
    expires_delta: timedelta = timedelta(hours=1),
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create an access token using global JWT manager

    Args:
        subject: Subject (usually user ID or email)
        expires_delta: Token expiration time
        additional_claims: Additional JWT claims

    Returns:
        Encoded JWT token string
    """
    return get_jwt_manager().create_access_token(subject, expires_delta, additional_claims)


def create_refresh_token(
    subject: str,
    expires_delta: timedelta = timedelta(days=7)
) -> str:
    """
    Create a refresh token using global JWT manager

    Args:
        subject: Subject (usually user ID or email)
        expires_delta: Token expiration time

    Returns:
        Encoded JWT refresh token string
    """
    return get_jwt_manager().create_refresh_token(subject, expires_delta)


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify an access token using global JWT manager

    Args:
        token: JWT access token string

    Returns:
        Decoded payload if valid, None otherwise
    """
    return get_jwt_manager().verify_access_token(token)


def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a refresh token using global JWT manager

    Args:
        token: JWT refresh token string

    Returns:
        Decoded payload if valid, None otherwise
    """
    return get_jwt_manager().verify_refresh_token(token)
