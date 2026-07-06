"""
Async SQLAlchemy session factory and engine for VulnForge.

Architecture Decision:
    Uses ``asyncpg`` as the PostgreSQL driver for true async I/O.
    The async engine is created once at startup (in ``lifespan.py``) and
    shared across all requests via FastAPI's dependency injection.

    Each HTTP request gets its own ``AsyncSession`` scoped to the request
    lifecycle — committed on success, rolled back on any exception.
    This is the Unit of Work pattern: one transaction per request.

    The ``get_db`` dependency is the single entry point for all database
    access in route handlers and services.  Nothing outside this module
    directly touches ``AsyncEngine`` or ``async_sessionmaker``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Module-level singletons — initialised by ``init_db()`` during app startup
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(
    database_url: str,
    *,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
    echo: bool = False,
) -> None:
    """Initialise the async SQLAlchemy engine and session factory.

    Call this exactly once during application startup inside ``lifespan.py``.
    After this call, ``get_db()`` becomes usable.

    Args:
        database_url:  Full asyncpg connection URL.
        pool_size:     Number of persistent connections in the pool.
        max_overflow:  Extra connections allowed above ``pool_size``.
        pool_timeout:  Seconds to wait for a connection before raising.
        pool_recycle:  Seconds after which connections are recycled.
        echo:          If True, log all SQL statements (dev only).
    """
    global _engine, _session_factory  # noqa: PLW0603

    _engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        echo=echo,
        # asyncpg-specific: disable JIT for consistent query planning
        connect_args={"server_settings": {"jit": "off"}},
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Don't lazy-load after commit — safer in async
        autocommit=False,
        autoflush=False,
    )

    logger.info(
        "database.initialised",
        pool_size=pool_size,
        max_overflow=max_overflow,
    )


async def close_db() -> None:
    """Dispose the engine connection pool.

    Call this during application shutdown in ``lifespan.py``.
    Waits for all active connections to return to the pool before closing.
    """
    global _engine  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        logger.info("database.closed")
        _engine = None


def get_engine() -> AsyncEngine:
    """Return the global async engine.

    Returns:
        AsyncEngine: The initialised engine.

    Raises:
        RuntimeError: If ``init_db()`` has not been called yet.
    """
    if _engine is None:
        raise RuntimeError(
            "Database engine is not initialised. "
            "Call init_db() during application startup."
        )
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a per-request async database session.

    The session is automatically committed on clean exit and rolled back on
    any exception — implementing the Unit of Work pattern.

    Yields:
        AsyncSession: A transactional database session scoped to this request.

    Example:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    if _session_factory is None:
        raise RuntimeError(
            "Session factory is not initialised. "
            "Call init_db() during application startup."
        )

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
