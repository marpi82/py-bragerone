"""Tests for BragerOneApiClient authentication functionality."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pytest_httpx import HTTPXMock

from pybragerone.api import BragerOneApiClient
from pybragerone.api.client import ApiError
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
async def test_invalidate_and_reauth_forces_login(httpx_mock: HTTPXMock) -> None:
    """invalidate_and_reauth must drop a still-valid token and login again."""
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD), validate_on_start=False)
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T2"})
    first = await client.ensure_auth()
    assert first.access_token == "T1"
    second = await client.invalidate_and_reauth()
    assert second.access_token == "T2"
    assert client.access_token == "T2"
    await client.close()


@pytest.mark.asyncio
async def test_invalidate_and_reauth_without_creds_preserves_token() -> None:
    """Without credentials, invalidate must not wipe a usable in-memory token."""
    client = BragerOneApiClient(validate_on_start=False)
    client._token = Token(access_token="keep-me")
    tok = await client.invalidate_and_reauth()
    assert tok.access_token == "keep-me"
    assert client._token is not None
    assert client._token.access_token == "keep-me"
    await client.close()


@pytest.mark.asyncio
async def test_invalidate_and_reauth_without_creds_or_token_raises() -> None:
    """Without credentials and without a usable token, invalidate raises ApiError."""
    client = BragerOneApiClient(validate_on_start=False)
    with pytest.raises(ApiError) as exc:
        await client.invalidate_and_reauth()
    assert exc.value.status == 401
    assert exc.value.data == {"message": "No credentials for (re)login"}
    assert client._token is None
    await client.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_ensure_auth_empty_persisted_token_does_not_deadlock(httpx_mock: HTTPXMock) -> None:
    """Persisted empty access_token must not deadlock under validate_on_start.

    ``ensure_auth`` holds ``_auth_lock`` while validating; an empty token used to
    reach ``_req`` → recursive ``ensure_auth`` on the same lock.
    """
    store = _TestTokenStore(Token(access_token=""))
    client = BragerOneApiClient(
        token_store=store,
        creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD),
        validate_on_start=True,
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        json={
            "accessToken": "T1",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        },
    )
    tok = await asyncio.wait_for(client.ensure_auth(), timeout=2.0)
    assert tok.access_token == "T1"
    assert client.access_token == "T1"
    await client.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_invalidate_and_reauth_clears_token_store(httpx_mock: HTTPXMock) -> None:
    """invalidate_and_reauth clears the persisted store before re-login.

    If the forced login fails after clearing, ``load()`` stays empty so a later
    recovery cycle cannot reload the wedged token.
    """
    store = _TestTokenStore()
    client = BragerOneApiClient(
        token_store=store,
        creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD),
        validate_on_start=False,
    )
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    await client.ensure_auth()
    saved = store.load()
    assert saved is not None
    assert saved.access_token == "T1"

    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        status_code=401,
        json={"message": "bad credentials"},
    )
    with pytest.raises(ApiError):
        await client.invalidate_and_reauth()

    assert client._token is None
    assert store.load() is None

    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T2"})
    tok = await client.ensure_auth()
    assert tok.access_token == "T2"
    saved_again = store.load()
    assert saved_again is not None
    assert saved_again.access_token == "T2"
    await client.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_invalidate_and_reauth_propagates_clearer_errors(httpx_mock: HTTPXMock) -> None:
    """Persisted-store clear failures must not be swallowed during invalidation."""

    class _BoomStore(_TestTokenStore):
        def clear(self) -> None:
            raise RuntimeError("disk full")

    store = _BoomStore()
    client = BragerOneApiClient(
        token_store=store,
        creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD),
        validate_on_start=False,
    )
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    await client.ensure_auth()

    with pytest.raises(RuntimeError, match="disk full"):
        await client.invalidate_and_reauth()

    assert client._token is None
    assert client._skip_load_once is True
    await client.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_invalidate_and_reauth_accepts_explicit_credentials(httpx_mock: HTTPXMock) -> None:
    """Explicit email/password overrides are forwarded to the forced login."""
    client = BragerOneApiClient(validate_on_start=False)
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T2"})
    await client.ensure_auth("old@example.com", "old-pass")
    second = await client.invalidate_and_reauth("new@example.com", "new-pass")
    assert second.access_token == "T2"
    await client.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_invalidate_and_reauth_honors_explicit_creds_under_race(httpx_mock: HTTPXMock) -> None:
    """Atomic invalidate+login must not let a provider race steal explicit overrides.

    A concurrent ``ensure_auth()`` waits on ``_auth_lock``; when invalidate holds
    the lock through ``_post_login``, the forced login still uses the explicit
    email/password rather than the credential provider.
    """
    provider_calls: list[tuple[str, str]] = []

    def _provider() -> tuple[str, str]:
        pair = ("provider@example.com", "provider-pass")
        provider_calls.append(pair)
        return pair

    client = BragerOneApiClient(creds_provider=_provider, validate_on_start=False)
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T2"})
    await client.ensure_auth()
    assert provider_calls == [("provider@example.com", "provider-pass")]
    provider_calls.clear()

    real_post_login = client._post_login
    login_started = asyncio.Event()
    login_release = asyncio.Event()
    login_emails: list[str] = []

    async def _gated_post_login(email: str, password: str) -> Token:
        login_emails.append(email)
        login_started.set()
        await login_release.wait()
        return await real_post_login(email, password)

    client._post_login = _gated_post_login  # type: ignore[method-assign]

    reauth_task = asyncio.create_task(client.invalidate_and_reauth("explicit@example.com", "explicit-pass"))
    await login_started.wait()
    ensure_task = asyncio.create_task(client.ensure_auth())
    await asyncio.sleep(0)
    login_release.set()

    tok = await reauth_task
    ensure_tok = await ensure_task
    assert tok.access_token == "T2"
    assert ensure_tok.access_token == "T2"
    assert login_emails == ["explicit@example.com"]
    assert provider_calls == []
    await client.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_invalidate_and_reauth_clearer_runs_off_event_loop(httpx_mock: HTTPXMock) -> None:
    """Token clearer must run via ``asyncio.to_thread`` (not on the event loop)."""
    import threading

    loop_thread_id = threading.get_ident()
    clearer_thread_ids: list[int] = []

    class _ThreadProbeStore(_TestTokenStore):
        def clear(self) -> None:
            clearer_thread_ids.append(threading.get_ident())
            super().clear()

    store = _ThreadProbeStore()
    client = BragerOneApiClient(
        token_store=store,
        creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD),
        validate_on_start=False,
    )
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T2"})
    await client.ensure_auth()
    second = await client.invalidate_and_reauth()
    assert second.access_token == "T2"
    assert clearer_thread_ids
    assert clearer_thread_ids[0] != loop_thread_id
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


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_req_reauths_when_token_cleared(httpx_mock: HTTPXMock) -> None:
    """Authenticated ``_req`` must ``ensure_auth`` when ``_token`` is cleared.

    Without this, concurrent invalidate/zombie recovery races raise
    ``ApiError(... No token)`` instead of waiting for a fresh login.
    """
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD), validate_on_start=False)
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T2"})
    httpx_mock.add_response(method="GET", url=f"{API}/v1/user", json={"ok": True})

    await client.ensure_auth()
    assert client.access_token == "T1"
    client._token = None

    status, payload, _ = await client._req("GET", f"{API}/v1/user")
    assert status == 200
    assert payload == {"ok": True}
    assert client.access_token == "T2"
    await client.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_req_waits_during_invalidate_and_reauth(httpx_mock: HTTPXMock) -> None:
    """Concurrent authenticated ``_req`` must wait out ``invalidate_and_reauth``.

    Clears the token then holds login briefly so a racing ``_req`` cannot raise
    ``No token``; both complete after the fresh login.
    """
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD), validate_on_start=False)
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T2"})
    httpx_mock.add_response(method="GET", url=f"{API}/v1/user", json={"ok": True})

    await client.ensure_auth()
    assert client.access_token == "T1"

    real_post_login = client._post_login
    login_started = asyncio.Event()
    login_release = asyncio.Event()

    async def _gated_post_login(email: str, password: str) -> Token:
        login_started.set()
        await login_release.wait()
        return await real_post_login(email, password)

    client._post_login = _gated_post_login  # type: ignore[method-assign]

    reauth_task = asyncio.create_task(client.invalidate_and_reauth())
    await login_started.wait()
    assert client._token is None

    req_task = asyncio.create_task(client._req("GET", f"{API}/v1/user"))
    await asyncio.sleep(0)
    login_release.set()

    tok = await reauth_task
    status, payload, _ = await req_task
    assert tok.access_token == "T2"
    assert status == 200
    assert payload == {"ok": True}
    assert client.access_token == "T2"
    await client.close()


@pytest.mark.asyncio
async def test_req_raises_no_token_when_ensure_auth_leaves_unusable() -> None:
    """Authenticated ``_req`` raises ``No token`` if ``ensure_auth`` yields nothing usable.

    Covers the empty-``access_token`` arm of the pre-``ensure_auth`` guard and the
    post-``ensure_auth`` raise when the token is still missing or blank.
    """
    client = BragerOneApiClient(validate_on_start=False)
    # First guard: ``_token`` present but ``access_token`` empty → call ``ensure_auth``.
    client._token = Token(access_token="")

    async def _leave_none(*_args: object, **_kwargs: object) -> Token:
        client._token = None
        return Token(access_token="")

    client.ensure_auth = _leave_none  # type: ignore[method-assign]
    with pytest.raises(ApiError) as exc_none:
        await client._req("GET", f"{API}/v1/user")
    assert exc_none.value.status == 401
    assert exc_none.value.data == {"message": "No token"}

    # Same path when ``ensure_auth`` leaves an empty ``access_token``.
    client._token = Token(access_token="")

    async def _leave_empty(*_args: object, **_kwargs: object) -> Token:
        client._token = Token(access_token="")
        return client._token

    client.ensure_auth = _leave_empty  # type: ignore[method-assign]
    with pytest.raises(ApiError) as exc_empty:
        await client._req("GET", f"{API}/v1/user")
    assert exc_empty.value.status == 401
    assert exc_empty.value.data == {"message": "No token"}
    await client.close()
