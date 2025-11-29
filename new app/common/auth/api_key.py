"""
API Key Authentication for ML Server ↔ Core Platform Communication

Provides secure API key generation, hashing, and verification for
inter-service communication.
"""

import hashlib
import secrets
import hmac
from typing import Optional, Tuple
from datetime import datetime, timedelta


class APIKeyManager:
    """
    Manages API key creation, verification, and revocation

    Used for:
    - Core Platform → ML Server authentication
    - Customer → Core Platform API authentication
    """

    @staticmethod
    def generate_api_key(prefix: str = "sk") -> str:
        """
        Generate a secure random API key

        Args:
            prefix: Key prefix for identification (sk = secret key, pk = public key)

        Returns:
            API key string (format: {prefix}_{random_64_chars})
        """
        random_bytes = secrets.token_bytes(32)
        random_hex = random_bytes.hex()
        return f"{prefix}_{random_hex}"

    @staticmethod
    def hash_api_key(api_key: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash an API key for secure storage

        Args:
            api_key: Plain text API key
            salt: Optional salt (generated if not provided)

        Returns:
            Tuple of (hashed_key, salt)
        """
        if salt is None:
            salt = secrets.token_hex(16)

        # Use PBKDF2 with SHA-256
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            api_key.encode('utf-8'),
            salt.encode('utf-8'),
            iterations=100000
        )

        return hashed.hex(), salt

    @staticmethod
    def verify_api_key(api_key: str, hashed_key: str, salt: str) -> bool:
        """
        Verify an API key against its hash

        Args:
            api_key: Plain text API key to verify
            hashed_key: Stored hash
            salt: Stored salt

        Returns:
            True if API key matches, False otherwise
        """
        computed_hash, _ = APIKeyManager.hash_api_key(api_key, salt)
        return hmac.compare_digest(computed_hash, hashed_key)

    @staticmethod
    def extract_prefix(api_key: str) -> str:
        """
        Extract prefix from API key

        Args:
            api_key: API key string

        Returns:
            Prefix (e.g., "sk", "pk")
        """
        if "_" in api_key:
            return api_key.split("_")[0]
        return ""


def create_api_key(service_name: str, expires_days: int = 365) -> dict:
    """
    Create a new API key for a service

    Args:
        service_name: Name of the service (e.g., "ml-server", "customer-123")
        expires_days: Number of days until expiration

    Returns:
        Dictionary with api_key, hashed_key, salt, expires_at
    """
    api_key = APIKeyManager.generate_api_key(prefix="sk")
    hashed_key, salt = APIKeyManager.hash_api_key(api_key)
    expires_at = datetime.utcnow() + timedelta(days=expires_days)

    return {
        "api_key": api_key,  # Return to user once, never stored
        "hashed_key": hashed_key,  # Store in database
        "salt": salt,  # Store in database
        "service_name": service_name,
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
    }


def verify_api_key(api_key: str, stored_keys: list) -> Optional[dict]:
    """
    Verify an API key against stored keys

    Args:
        api_key: Plain text API key from request
        stored_keys: List of stored key dictionaries (hashed_key, salt, expires_at, etc.)

    Returns:
        Matching key dictionary if valid, None otherwise
    """
    for stored in stored_keys:
        # Check expiration
        if stored.get("expires_at") and stored["expires_at"] < datetime.utcnow():
            continue

        # Check if key is active
        if not stored.get("active", True):
            continue

        # Verify hash
        if APIKeyManager.verify_api_key(
            api_key,
            stored["hashed_key"],
            stored["salt"]
        ):
            return stored

    return None


def hash_api_key(api_key: str) -> Tuple[str, str]:
    """
    Convenience function to hash an API key

    Args:
        api_key: Plain text API key

    Returns:
        Tuple of (hashed_key, salt)
    """
    return APIKeyManager.hash_api_key(api_key)
