"""Tests for BragerOneApiClient authentication functionality."""

from datetime import UTC, datetime, timedelta

import pytest
from aioresponses import aioresponses

from pybragerone.api import BragerOneApiClient
from pybragerone.models import Token

API = "https://io.brager.pl"
TEST_EMAIL = "a@b"
TEST_PASSWORD = "pw"


class _TestTokenStore:
    """Simple token store implementation for testing."""

    def __init__(self, initial_token: Token | None = None) -> None:
        """Initialize the test token store.

        Args:
            initial_token: Optional initial token to store.
        """
        self._token = initial_token

    def load(self) -> Token | None:
        """Load the stored token."""
        return self._token

    def save(self, token: Token) -> None:
        """Save a token to storage.

        Args:
            token: The token to save.
        """
        self._token = token

    def clear(self) -> None:
        """Clear the stored token."""
        self._token = None


@pytest.mark.asyncio
async def test_initial_login_and_validate() -> None:
    """Test initial login flow and token validation on startup.

    Verifies that the client can successfully authenticate and validate
    the token when validate_on_start is enabled.
    """
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD), validate_on_start=True)

    with aioresponses() as m:
        m.post(
            f"{API}/v1/auth/user",
            payload={
                "accessToken": "T1",
                "refreshToken": "R1",
                "type": "bearer",
                "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            },
        )
        m.get(f"{API}/v1/user", payload={"ok": True})

        tok = await client.ensure_auth()
        assert tok.access_token == "T1"

    await client.close()


@pytest.mark.asyncio
async def test_proactive_relogin_when_expiring() -> None:
    """Test proactive re-login when token is about to expire.

    Verifies that the client automatically re-authenticates when the current
    token is close to expiry, before making any requests.
    """
    expiring = Token(
        access_token="OLD",
        expires_at=datetime.now(UTC) + timedelta(seconds=10),
    )

    store = _TestTokenStore(expiring)
    client = BragerOneApiClient(token_store=store, creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD))

    with aioresponses() as m:
        m.post(
            f"{API}/v1/auth/user",
            payload={
                "accessToken": "NEW",
                "type": "bearer",
                "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            },
        )

        tok = await client.ensure_auth()
        assert tok.access_token == "NEW"

    await client.close()


@pytest.mark.asyncio
async def test_reactive_refresh_on_401_retry_once() -> None:
    """Test reactive token refresh on 401 response with single retry.

    Verifies that when a request fails with 401, the client automatically
    refreshes the token and retries the request exactly once.
    """
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD))

    with aioresponses() as m:
        m.post(
            f"{API}/v1/auth/user",
            payload={
                "accessToken": "T1",
                "type": "bearer",
                "expiresAt": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
            },
        )
        tok = await client.ensure_auth()
        assert tok.access_token == "T1"

        m.get(f"{API}/v1/user", status=401)
        m.post(
            f"{API}/v1/auth/user",
            payload={
                "accessToken": "T2",
                "type": "bearer",
                "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            },
        )
        m.get(f"{API}/v1/user", payload={"ok": True})

        status, payload, _ = await client._req("GET", f"{API}/v1/user")
        assert status == 200
        assert payload == {"ok": True}

    await client.close()


@pytest.mark.asyncio
async def test_revoke_swallows_errors() -> None:
    """Test that token revoke gracefully handles server errors.

    Verifies that the revoke method clears the local token state even
    when the server returns an error response.
    """
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD))
    with aioresponses() as m:
        m.post(f"{API}/v1/auth/user", payload={"accessToken": "T1"})
        await client.ensure_auth()

        # Test that 401/403/404 errors are swallowed but token is cleared
        m.post(f"{API}/v1/auth/revoke", status=401, payload={"message": "unauthorized"})
        await client.revoke()
        assert client._token is None

    await client.close()
