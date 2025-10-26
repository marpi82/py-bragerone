"""Tests for BragerOneApiClient authentication functionality."""

from datetime import UTC, datetime, timedelta

import pytest
from pytest_httpx import HTTPXMock

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
        """Save a token.

        Args:
            token: The token to store.
        """
        self._token = token

    def clear(self) -> None:
        """Clear the stored token."""
        self._token = None


@pytest.mark.asyncio
async def test_initial_login_and_validate(httpx_mock: HTTPXMock) -> None:
    """Test initial login flow and token validation on startup.

    Verifies that the client can successfully authenticate and validate
    the token when validate_on_start is enabled.
    """
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD), validate_on_start=True)

    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        json={
            "accessToken": "T1",
            "refreshToken": "R1",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        },
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{API}/v1/user",
        json={
            "user": {
                "id": 1,
                "name": "Test User",
                "email": TEST_EMAIL,
                "language": "en",
                "allow_email_type_informations": True,
                "allow_email_type_alarms": True,
                "allow_email_type_marketing": False,
                "allow_email_type_warnings": True,
                "activated_at": "2023-01-01T00:00:00Z",
                "show_rate_us_modal": False,
            }
        },
    )

    tok = await client.ensure_auth()
    assert tok.access_token == "T1"

    # Call get_user to trigger validation
    user = await client.get_user()
    assert user.email == TEST_EMAIL
    await client.close()


@pytest.mark.asyncio
async def test_proactive_relogin_when_expiring(httpx_mock: HTTPXMock) -> None:
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

    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        json={
            "accessToken": "NEW",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        },
    )

    tok = await client.ensure_auth()
    assert tok.access_token == "NEW"

    await client.close()


@pytest.mark.asyncio
async def test_reactive_refresh_on_401_retry_once(httpx_mock: HTTPXMock) -> None:
    """Test reactive token refresh on 401 response with single retry.

    Verifies that when a request fails with 401, the client automatically
    refreshes the token and retries the request exactly once.
    """
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD))

    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        json={
            "accessToken": "T1",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
        },
    )
    tok = await client.ensure_auth()
    assert tok.access_token == "T1"

    # Mock 401 response then successful retry
    httpx_mock.add_response(method="GET", url=f"{API}/v1/user", status_code=401)
    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        json={
            "accessToken": "T2",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        },
    )
    httpx_mock.add_response(method="GET", url=f"{API}/v1/user", json={"ok": True})

    status, payload, _ = await client._req("GET", f"{API}/v1/user")
    assert status == 200
    assert payload == {"ok": True}

    await client.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_revoke_swallows_errors(httpx_mock: HTTPXMock) -> None:
    """Test that token revoke gracefully handles server errors.

    Verifies that the revoke method clears the local token state even
    when the server returns an error response.
    """
    # Use validate_on_start=False to avoid validation calls
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD), validate_on_start=False)

    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    # Pre-mock the revoke call
    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/revoke",
        status_code=401,
        json={"message": "unauthorized"},
    )

    await client.ensure_auth()

    # Test that 401/403/404 errors are swallowed but token is cleared
    await client.revoke()
    assert client._token is None

    await client.close()
