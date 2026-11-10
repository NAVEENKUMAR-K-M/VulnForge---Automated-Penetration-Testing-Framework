"""
Application startup and shutdown lifecycle manager.

Uses FastAPI's ``lifespan`` context manager (introduced in 0.95.0) as the
modern replacement for deprecated ``@app.on_event`` handlers.

Startup:
    1. Configure structured logging
    2. Initialise the async DB connection pool
    3. Seed the first superuser if one doesn't exist

Shutdown:
    1. Close the DB connection pool gracefully

Design:
    All side effects (DB connection, external clients) are initialised here
    rather than at module import time.  This makes the application testable —
    tests can provide their own initialisation without triggering production
    connections.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.database.session import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager.

    Code before ``yield`` runs at startup; code after runs at shutdown.

    Args:
        app: The FastAPI application instance.

    Yields:
        None
    """
    settings = get_settings()

    # ── Startup ───────────────────────────────────────────────────────────────
    configure_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
    )
    logger = get_logger(__name__)
    logger.info(
        "vulnforge.starting",
        version=settings.app_version,
        environment=settings.app_env,
    )

    init_db(
        database_url=settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        echo=settings.db_echo,
    )

    # Seed first superuser if the DB is fresh
    await _seed_superuser(settings)

    # Register on-disk plugins into the plugin registry so scans can resolve them
    await _sync_plugins()

    logger.info("vulnforge.ready", port=settings.api_port)

    # ── Hand control to FastAPI ────────────────────────────────────────────────
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("vulnforge.shutting_down")
    await close_db()
    logger.info("vulnforge.shutdown_complete")


async def _seed_superuser(settings: object) -> None:
    """Create the initial superuser account if none exists.

    This is idempotent — it only creates the user if no superuser exists.
    Called during every startup; safe to run multiple times.

    Args:
        settings: Application settings with superuser credentials.
    """
    from app.core.security import hash_password
    from app.database.session import get_db
    from app.models.user import UserRole
    from app.repositories.user import UserRepository

    logger = get_logger(__name__)

    try:
        async for db in get_db():
            user_repo = UserRepository(db)

            if await user_repo.superuser_exists():
                logger.debug("seed.superuser_exists")
                return

            hashed = hash_password(settings.first_superuser_password)  # type: ignore[attr-defined]
            await user_repo.create_from_dict(
                {
                    "username": settings.first_superuser_username,  # type: ignore[attr-defined]
                    "email": settings.first_superuser_email,  # type: ignore[attr-defined]
                    "hashed_password": hashed,
                    "full_name": "VulnForge Administrator",
                    "role": UserRole.ADMIN,
                    "is_active": True,
                    "is_superuser": True,
                }
            )
            logger.info(
                "seed.superuser_created",
                email=settings.first_superuser_email,  # type: ignore[attr-defined]
            )
    except Exception as exc:  # noqa: BLE001
        get_logger(__name__).warning("seed.superuser_failed", error=str(exc))


async def _sync_plugins() -> None:
    """Discover on-disk plugins and upsert them into the plugin registry.

    Idempotent — runs on every startup.  Plugins found on disk are inserted or
    updated; registry rows no longer present on disk are disabled.  Without this
    the ``plugins`` table stays empty and scans cannot resolve any plugin set.
    """
    from app.core.plugin_registry import PluginRegistry
    from app.database.session import get_db

    logger = get_logger(__name__)
    try:
        async for db in get_db():
            await PluginRegistry(db).sync()
            logger.info("plugins.synced")
    except Exception as exc:  # noqa: BLE001
        logger.warning("plugins.sync_failed", error=str(exc))
