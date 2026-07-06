"""
Alembic environment configuration for VulnForge async migrations.

Architecture Decisions:
    1. Async engine: Uses ``asyncpg`` driver via ``run_sync`` so Alembic
       (which is synchronous) can operate against an async connection pool.
    2. Model import: Imports ``app.models`` to ensure all SQLAlchemy models
       are registered with ``Base.metadata`` before autogenerate runs.
    3. Config sourced from environment: The database URL is assembled from
       environment variables, never hardcoded.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── VulnForge imports ─────────────────────────────────────────────────────────
# This import is essential — it side-loads all models into Base.metadata
import app.models  # noqa: F401
from app.models.base import Base
from app.core.config import get_settings

# ── Alembic Config Object ─────────────────────────────────────────────────────
config = context.config

# Configure Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata for autogenerate support
target_metadata = Base.metadata

# Override the sqlalchemy.url from environment variables
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    In offline mode, Alembic emits SQL scripts without connecting to the DB.
    This is useful for generating migration SQL to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within a synchronous connection context.

    Args:
        connection: A synchronous SQLAlchemy connection.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations via ``run_sync``.

    Alembic's migration execution is inherently synchronous.  We bridge
    the async engine to the sync context using ``run_sync``.
    """
    configuration: dict[str, Any] = config.get_section(
        config.config_ini_section, {}
    )
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an active DB connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
