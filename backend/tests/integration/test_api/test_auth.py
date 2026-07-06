"""
Integration tests for auth API endpoints.

These tests exercise the complete HTTP stack:
    Client → Router → Service → Repository → (Test) Database

Each test uses the rolled-back async session fixture to ensure isolation.

Markers: ``@pytest.mark.integration``
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.user import User


REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
LOGOUT_ALL_URL = "/api/v1/auth/logout-all"
ME_URL = "/api/v1/auth/me"
CHANGE_PASSWORD_URL = "/api/v1/auth/change-password"
RESET_REQUEST_URL = "/api/v1/auth/password-reset/request"
RESET_CONFIRM_URL = "/api/v1/auth/password-reset/confirm"


@pytest.mark.integration
class TestRegisterEndpoint:
    """Integration tests for POST /auth/register."""

    @pytest.mark.asyncio
    async def test_register_returns_201_with_tokens(self, client: AsyncClient) -> None:
        """Successful registration returns 201 with access and refresh tokens."""
        response = await client.post(
            REGISTER_URL,
            json={
                "username": "newanalyst01",
                "email": "newanalyst01@vulnforge.local",
                "password": "Str0ng!P4ssw0rd#",
                "full_name": "New Analyst",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert "tokens" in body
        assert "user" in body
        assert body["tokens"]["access_token"]
        assert body["tokens"]["refresh_token"]
        assert body["tokens"]["token_type"] == "bearer"
        assert body["user"]["email"] == "newanalyst01@vulnforge.local"
        assert body["user"]["role"] == "viewer"  # Default role

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(
        self, client: AsyncClient, test_user: User
    ) -> None:
        """Duplicate email returns 409 Conflict."""
        response = await client.post(
            REGISTER_URL,
            json={
                "username": "differentuser",
                "email": test_user.email,  # Already exists
                "password": "Str0ng!P4ssw0rd#",
            },
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_weak_password_returns_422(
        self, client: AsyncClient
    ) -> None:
        """Password without special characters fails Pydantic validation."""
        response = await client.post(
            REGISTER_URL,
            json={
                "username": "weakpassuser",
                "email": "weakpass@vulnforge.local",
                "password": "weakpassword",  # No uppercase, digit, special char
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password_returns_422(
        self, client: AsyncClient
    ) -> None:
        """Password under 12 characters fails Pydantic min_length validation."""
        response = await client.post(
            REGISTER_URL,
            json={
                "username": "shortpassuser",
                "email": "short@vulnforge.local",
                "password": "Sh0rt!",
            },
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestLoginEndpoint:
    """Integration tests for POST /auth/login."""

    @pytest.mark.asyncio
    async def test_login_success_returns_200_with_tokens(
        self, client: AsyncClient, test_user: User
    ) -> None:
        """Valid credentials return 200 with token pair."""
        response = await client.post(
            LOGIN_URL,
            json={"email": test_user.email, "password": "Test!Pass1234"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["tokens"]["access_token"]
        assert body["tokens"]["refresh_token"]

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(
        self, client: AsyncClient, test_user: User
    ) -> None:
        """Wrong password returns 401 Unauthorized."""
        response = await client.post(
            LOGIN_URL,
            json={"email": test_user.email, "password": "WrongPass!1234"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_unknown_email_returns_401(
        self, client: AsyncClient
    ) -> None:
        """Unknown email returns 401 (same as wrong password — prevents enumeration)."""
        response = await client.post(
            LOGIN_URL,
            json={"email": "nobody@vulnforge.local", "password": "Any!Pass1234"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields_returns_422(
        self, client: AsyncClient
    ) -> None:
        """Missing required fields fail Pydantic validation."""
        response = await client.post(LOGIN_URL, json={"email": "only@email.com"})
        assert response.status_code == 422


@pytest.mark.integration
class TestGetMeEndpoint:
    """Integration tests for GET /auth/me."""

    @pytest.mark.asyncio
    async def test_get_me_returns_user_profile(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ) -> None:
        """Authenticated user can retrieve their profile."""
        response = await client.get(ME_URL, headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == test_user.email
        assert "hashed_password" not in body
        assert "password_reset_token_hash" not in body

    @pytest.mark.asyncio
    async def test_get_me_without_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        """Missing token returns 401."""
        response = await client.get(ME_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_with_invalid_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        """Invalid JWT returns 401."""
        response = await client.get(
            ME_URL,
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestPasswordResetEndpoints:
    """Integration tests for the two-phase password reset flow."""

    @pytest.mark.asyncio
    async def test_reset_request_always_returns_200(
        self, client: AsyncClient
    ) -> None:
        """Password reset request always returns 200 regardless of email existence."""
        # Unknown email — still 200 (prevents enumeration)
        response = await client.post(
            RESET_REQUEST_URL,
            json={"email": "nobody@nowhere.com"},
        )
        assert response.status_code == 200
        assert "reset link" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_reset_request_known_email_returns_200(
        self, client: AsyncClient, test_user: User
    ) -> None:
        """Password reset request for existing user also returns 200."""
        response = await client.post(
            RESET_REQUEST_URL,
            json={"email": test_user.email},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_reset_confirm_invalid_token_returns_400(
        self, client: AsyncClient
    ) -> None:
        """Invalid reset token returns 400 Bad Request."""
        response = await client.post(
            RESET_CONFIRM_URL,
            json={
                "token": "completely_invalid_token_here",
                "new_password": "NewStr0ng!Pass#1",
            },
        )
        assert response.status_code == 400


@pytest.mark.integration
class TestLogoutEndpoints:
    """Integration tests for logout flows."""

    @pytest.mark.asyncio
    async def test_logout_all_returns_200(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ) -> None:
        """Logout all returns 200 with count of revoked sessions."""
        response = await client.post(
            LOGOUT_ALL_URL,
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "revoked" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_logout_all_without_auth_returns_401(
        self, client: AsyncClient
    ) -> None:
        """Logout all without auth token returns 401."""
        response = await client.post(LOGOUT_ALL_URL)
        assert response.status_code == 401
