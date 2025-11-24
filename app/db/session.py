"""
Async Database Session Management

Handles SQLAlchemy async session lifecycle and dependency injection.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

logger = logging.getLogger(__name__)


# Global engine instance
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create the async database engine.

    Configures connection pooling with settings from config.

    Returns:
        AsyncEngine: SQLAlchemy async engine instance
    """
    global _engine

    if _engine is None:
        _engine = create_async_engine(
            settings.database_url_str,
            echo=settings.db_echo,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=True,  # Enable connection health checks
            future=True,
        )
        logger.info("Database engine created successfully")

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the async session factory.

    Returns:
        async_sessionmaker: Session factory for creating new sessions
    """
    global _async_session_factory

    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,  # Prevent lazy loading after commit
        )
        logger.info("Session factory created successfully")

    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Provides a database session for request handling with proper
    cleanup and error handling.

    Yields:
        AsyncSession: Database session for the request

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(text("SELECT * FROM items"))
            return result.fetchall()
    """
    session_factory = get_session_factory()
    session = session_factory()

    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error occurred: {e}")
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error during database operation: {e}")
        raise
    finally:
        await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions outside of FastAPI.

    Use this for background tasks, CLI commands, or testing.

    Yields:
        AsyncSession: Database session

    Example:
        async with get_db_context() as db:
            result = await db.execute(text("SELECT * FROM items"))
            await db.commit()
    """
    session_factory = get_session_factory()
    session = session_factory()

    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Error in database context: {e}")
        raise
    finally:
        await session.close()


async def check_database_connection() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        from sqlalchemy import text

        async with get_db_context() as db:
            result = await db.execute(text("SELECT 1"))
            result.scalar()
            logger.info("Database connection check successful")
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def close_database_connection() -> None:
    """
    Close database engine and cleanup resources.

    Should be called during application shutdown.
    """
    global _engine, _async_session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database connections closed successfully")
