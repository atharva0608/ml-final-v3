"""
Base Settings for CloudOptim Components

Provides Pydantic settings with environment variable support.
"""

from pydantic_settings import BaseSettings as PydanticBaseSettings
from pydantic import Field
from typing import Optional, List
from functools import lru_cache


class BaseSettings(PydanticBaseSettings):
    """
    Base settings class with common configuration

    Each component (ML Server, Core Platform) should extend this class
    with component-specific settings.
    """

    # Application
    app_name: str = Field("CloudOptim", description="Application name")
    app_version: str = Field("1.0.0", description="Application version")
    environment: str = Field("development", description="Environment (development, staging, production)")
    debug: bool = Field(False, description="Debug mode")

    # API
    api_host: str = Field("0.0.0.0", description="API host")
    api_port: int = Field(8000, description="API port")
    api_workers: int = Field(4, description="Number of API workers")

    # Database
    database_url: str = Field(..., description="PostgreSQL connection URL")
    database_pool_size: int = Field(10, description="Database connection pool size")
    database_max_overflow: int = Field(20, description="Database max overflow connections")
    database_echo: bool = Field(False, description="Echo SQL queries")

    # Redis
    redis_url: str = Field("redis://localhost:6379/0", description="Redis connection URL")
    redis_ttl_seconds: int = Field(3600, description="Default Redis TTL (seconds)")

    # Security
    jwt_secret_key: str = Field(..., description="JWT secret key")
    jwt_algorithm: str = Field("HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(60, description="Access token expiration (minutes)")
    jwt_refresh_token_expire_days: int = Field(7, description="Refresh token expiration (days)")

    api_key_salt: str = Field(..., description="API key hashing salt")

    # Logging
    log_level: str = Field("INFO", description="Logging level")
    log_format: str = Field("json", description="Log format (json, text)")
    log_file: Optional[str] = Field(None, description="Log file path (None for stdout only)")

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"],
        description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(True, description="Allow credentials in CORS")

    # AWS (for Core Platform)
    aws_region: Optional[str] = Field(None, description="Default AWS region")
    aws_access_key_id: Optional[str] = Field(None, description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(None, description="AWS secret access key")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Singleton settings instance
_settings: Optional[BaseSettings] = None


@lru_cache()
def get_settings() -> BaseSettings:
    """
    Get global settings instance (cached)

    Returns:
        BaseSettings instance
    """
    global _settings
    if _settings is None:
        _settings = BaseSettings()
    return _settings
