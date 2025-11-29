"""
Database Configuration Utilities for CloudOptim Components

Provides SQLAlchemy engine and session creation with best practices.
"""

from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
from typing import Optional


def get_db_url(
    user: str,
    password: str,
    host: str,
    port: int,
    database: str,
    driver: str = "postgresql+asyncpg"
) -> str:
    """
    Construct database URL

    Args:
        user: Database user
        password: Database password
        host: Database host
        port: Database port
        database: Database name
        driver: SQLAlchemy driver

    Returns:
        Database URL string
    """
    return f"{driver}://{user}:{password}@{host}:{port}/{database}"


def create_engine(
    database_url: str,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_pre_ping: bool = True,
    echo: bool = False,
    **kwargs
):
    """
    Create SQLAlchemy engine with best practices

    Args:
        database_url: Database connection URL
        pool_size: Connection pool size
        max_overflow: Max overflow connections
        pool_pre_ping: Enable pool pre-ping for connection health checks
        echo: Echo SQL queries to logs
        **kwargs: Additional engine kwargs

    Returns:
        SQLAlchemy engine
    """
    # Use QueuePool for production, NullPool for testing
    poolclass = kwargs.pop("poolclass", QueuePool)

    engine = sa_create_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        echo=echo,
        poolclass=poolclass,
        **kwargs
    )

    return engine


def create_session(engine, autocommit: bool = False, autoflush: bool = False) -> sessionmaker:
    """
    Create SQLAlchemy session maker

    Args:
        engine: SQLAlchemy engine
        autocommit: Enable auto-commit
        autoflush: Enable auto-flush

    Returns:
        Session maker
    """
    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=autocommit,
        autoflush=autoflush,
        class_=Session
    )

    return SessionLocal


def get_db_session(SessionLocal: sessionmaker):
    """
    FastAPI dependency for database sessions

    Usage:
        from common.config import create_session, create_engine

        engine = create_engine(settings.database_url)
        SessionLocal = create_session(engine)

        @app.get("/users")
        def get_users(db: Session = Depends(lambda: get_db_session(SessionLocal))):
            return db.query(User).all()

    Args:
        SessionLocal: Session maker

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
