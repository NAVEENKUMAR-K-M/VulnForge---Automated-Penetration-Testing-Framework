"""
Pytest configuration and shared fixtures for VulnForge test suite.

Fixture scopes:
    - ``event_loop``:      Session-scoped — one event loop for all async tests.
    - ``settings``:        Session-scoped — parsed once, immutable.
    - ``test_db_engine``:  Session-scoped — one engine per test session.
    - ``db_session``:      Function-scoped — rolled back after every test.
    - ``client``:          Function-scoped — fresh HTTP client per test.
    - ``test_user``:       Function-scoped — seeded user, rolled back after test.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.security import hash_password
from app.database.session import get_db
from app.main import create_app
from app.models.base import Base
from app.models.user import User, UserRole


# ── Test Settings ──────────────────────────────────────────────────────────────

TEST_SETTINGS_OVERRIDES: dict[str, Any] = {
    "app_env": "development",
    "debug": True,
    "log_level": "WARNING",
    "log_format": "CONSOLE",
    "secret_key": "a" * 64,
    "postgres_host": "localhost",
    "postgres_port": 5432,
    "postgres_db": "vulnforge_test",
    "postgres_user": "vulnforge_user",
    "postgres_password": "test_password",
    "redis_host": "localhost",
    "redis_port": 6379,
    "first_superuser_email": "admin@test.local",
    "first_superuser_password": "Admin!Test1234",
    "first_superuser_username": "admin",
    "access_token_expire_minutes": 5,
    "refresh_token_expire_days": 1,
    "max_login_attempts": 3,
    "lockout_duration_minutes": 1,
    "db_echo": False,
}

TEST_DATABASE_URL = (
    "postgresql+asyncpg://vulnforge_user:test_password"
    "@localhost:5432/vulnforge_test"
)


# ── Event Loop ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Provide a single event loop for the entire test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ── Settings Fixture ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Return test-specific application settings.

    Returns:
        Settings: Settings configured for the test environment.
    """
    return Settings(**TEST_SETTINGS_OVERRIDES)  # type: ignore[arg-type]


# ── Database Fixtures ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_db_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
    """Create an async engine connected to the test database.

    Creates all tables at session start, drops them at the end.

    Args:
        test_settings: Test settings fixture.

    Yields:
        AsyncEngine: Connected test database engine.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    test_db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional async session that is ROLLED BACK after each test.

    This ensures test isolation — each test starts with a clean state without
    needing to truncate tables.

    Args:
        test_db_engine: The session-scoped test engine.

    Yields:
        AsyncSession: A rolled-back-after-use session.
    """
    factory = async_sessionmaker(
        bind=test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ── HTTP Client Fixture ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    test_settings: Settings,
) -> AsyncGenerator[AsyncClient, None]:
    """Yield an async HTTP test client with the test DB injected.

    Overrides the ``get_db`` dependency to use the test session so API
    tests share the same rolled-back transaction.

    Args:
        db_session:    Test database session fixture.
        test_settings: Test settings fixture.

    Yields:
        AsyncClient: Configured HTTPX async test client.
    """
    from app.core.config import get_settings

    app: FastAPI = create_app()

    # Override DB dependency to use our test session
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    # Override settings to use test settings
    def override_get_settings() -> Settings:
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── User Fixtures ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and persist a standard analyst user for tests.

    Args:
        db_session: Test database session.

    Returns:
        User: The created test user.
    """
    from app.repositories.user import UserRepository

    repo = UserRepository(db_session)
    user = await repo.create_from_dict(
        {
            "username": f"testuser_{uuid.uuid4().hex[:8]}",
            "email": f"test_{uuid.uuid4().hex[:8]}@vulnforge.local",
            "hashed_password": hash_password("Test!Pass1234"),
            "full_name": "Test Analyst",
            "role": UserRole.ANALYST,
            "is_active": True,
            "is_superuser": False,
        }
    )
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """Create and persist an admin user for tests.

    Args:
        db_session: Test database session.

    Returns:
        User: The created admin user.
    """
    from app.repositories.user import UserRepository

    repo = UserRepository(db_session)
    user = await repo.create_from_dict(
        {
            "username": f"admin_{uuid.uuid4().hex[:8]}",
            "email": f"admin_{uuid.uuid4().hex[:8]}@vulnforge.local",
            "hashed_password": hash_password("Admin!Pass1234"),
            "full_name": "Test Admin",
            "role": UserRole.ADMIN,
            "is_active": True,
            "is_superuser": False,
        }
    )
    return user


@pytest_asyncio.fixture
async def test_superuser(db_session: AsyncSession) -> User:
    """Create and persist a superuser for tests.

    Args:
        db_session: Test database session.

    Returns:
        User: The created superuser.
    """
    from app.repositories.user import UserRepository

    repo = UserRepository(db_session)
    user = await repo.create_from_dict(
        {
            "username": f"superuser_{uuid.uuid4().hex[:8]}",
            "email": f"super_{uuid.uuid4().hex[:8]}@vulnforge.local",
            "hashed_password": hash_password("Super!Pass1234"),
            "full_name": "Test Superuser",
            "role": UserRole.ADMIN,
            "is_active": True,
            "is_superuser": True,
        }
    )
    return user


# ── Token Fixture ──────────────────────────────────────────────────────────────

@pytest.fixture
def auth_headers(test_user: User, test_settings: Settings) -> dict[str, str]:
    """Return Authorization headers for the test user.

    Args:
        test_user:     The test analyst user.
        test_settings: Test settings with secret key.

    Returns:
        dict[str, str]: Authorization header dictionary.
    """
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=test_user.id,
        email=test_user.email,
        role=test_user.role.value,
        is_superuser=test_user.is_superuser,
        secret_key=test_settings.secret_key,
        algorithm=test_settings.algorithm,
        expire_minutes=test_settings.access_token_expire_minutes,
    )
    return {"Authorization": f"Bearer {token}"}
