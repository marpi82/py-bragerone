"""Edge-path tests for BragerOneApiClient auth, cache, and asset helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pytest_httpx import HTTPXMock

from pybragerone.api import BragerOneApiClient
from pybragerone.api.client import ApiError, HttpCache
from pybragerone.api.server import TISCONNECT_SERVER
from pybragerone.models import Token

API = "https://io.brager.pl"
ONE = "https://one.brager.pl"
TEST_EMAIL = "a@b"
TEST_PASSWORD = "pw"


class _TestTokenStore:
    """In-memory token store for client wiring tests."""

    def __init__(self, initial: Token | None = None) -> None:
        """Initialize with an optional cached token."""
        self.token = initial
        self.cleared = False

    def load(self) -> Token | None:
        """Return the cached token."""
        return self.token

    def save(self, token: Token) -> None:
        """Persist a token."""
        self.token = token

    def clear(self) -> None:
        """Forget the cached token."""
        self.token = None
        self.cleared = True


class _BoomLoader:
    """Token store whose load() always fails."""

    def load(self) -> Token | None:
        """Raise to exercise ensure_auth's suppressed loader path."""
        raise RuntimeError("store unavailable")

    def save(self, token: Token) -> None:
        """Ignore saves."""
        del token

    def clear(self) -> None:
        """Ignore clears."""


def test_http_cache_conditional_headers_and_miss() -> None:
    """HttpCache emits validators only after a body has been stored."""
    cache = HttpCache()
    url = "https://example.test/a.js"
    assert cache.headers_for(url) == {}
    assert cache.get_body(url) is None

    cache.update(url, {"ETag": '"abc"', "Last-Modified": "Wed, 01 Jan 2020 00:00:00 GMT"}, b"body")
    assert cache.headers_for(url) == {
        "If-None-Match": '"abc"',
        "If-Modified-Since": "Wed, 01 Jan 2020 00:00:00 GMT",
    }
    assert cache.get_body(url) == b"body"


def test_client_uses_server_config_and_clears_token_store() -> None:
    """``server=`` overrides bases; ``set_token_store(None)`` unhooks persistence."""
    store = _TestTokenStore(Token(access_token="cached"))
    client = BragerOneApiClient(server=TISCONNECT_SERVER, token_store=store, validate_on_start=False)
    assert client.api_base == TISCONNECT_SERVER.api_base
    assert client.one_base == TISCONNECT_SERVER.one_base
    assert client.io_base == TISCONNECT_SERVER.io_base.rstrip("/")

    client.set_token_store(None)
    assert client._token_loader is None
    assert client._token_saver is None
    assert client._token_clearer is None


def test_access_token_requires_auth() -> None:
    """``access_token`` raises before ``ensure_auth``."""
    client = BragerOneApiClient(validate_on_start=False)
    with pytest.raises(RuntimeError, match="no access token"):
        _ = client.access_token


async def test_ensure_auth_requires_credentials() -> None:
    """Missing email/password becomes a 401 ApiError."""
    client = BragerOneApiClient(validate_on_start=False)
    with pytest.raises(ApiError) as exc:
        await client.ensure_auth()
    assert exc.value.status == 401
    await client.close()


async def test_ensure_auth_swallows_loader_errors_and_logs_in(httpx_mock: HTTPXMock) -> None:
    """A failing token loader is ignored; login still proceeds."""
    client = BragerOneApiClient(
        token_store=_BoomLoader(),
        creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD),
        validate_on_start=False,
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        json={"accessToken": "T1", "type": "bearer"},
    )
    tok = await client.ensure_auth()
    assert tok.access_token == "T1"
    await client.close()


async def test_ensure_auth_relogins_when_validation_returns_401(httpx_mock: HTTPXMock) -> None:
    """A cached token that fails /user validation is dropped and replaced."""
    cached = Token(
        access_token="OLD",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    store = _TestTokenStore(cached)
    client = BragerOneApiClient(
        token_store=store,
        creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD),
        validate_on_start=True,
    )
    httpx_mock.add_response(method="GET", url=f"{API}/v1/user", status_code=401)
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


async def test_login_rejects_empty_access_token(httpx_mock: HTTPXMock) -> None:
    """Login payload without a usable access token is an ApiError."""
    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD), validate_on_start=False)
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "", "type": "bearer"})
    with pytest.raises(ApiError) as exc:
        await client.ensure_auth()
    assert exc.value.status == 500
    await client.close()


async def test_login_retries_duplicate_token_error(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """500 ER_DUP_ENTRY is retried, then a later login succeeds."""
    sleeps: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("pybragerone.api.client.asyncio.sleep", _fake_sleep)
    monkeypatch.setattr("random.uniform", lambda _a, _b: 0.0)

    client = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD), validate_on_start=False)
    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        status_code=500,
        json={"message": "ER_DUP_ENTRY"},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        json={"accessToken": "T2", "type": "bearer"},
    )
    tok = await client.ensure_auth()
    assert tok.access_token == "T2"
    assert sleeps
    await client.close()


async def test_revoke_clears_token_store(httpx_mock: HTTPXMock) -> None:
    """Successful revoke clears RAM and the persistence clearer."""
    store = _TestTokenStore()
    client = BragerOneApiClient(
        token_store=store,
        creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD),
        validate_on_start=False,
    )
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url=f"{API}/v1/auth/revoke", json={"ok": True})
    await client.ensure_auth()
    await client.revoke()
    assert client._token is None
    assert store.cleared is True
    await client.close()


async def test_get_system_version_rejects_non_dict(httpx_mock: HTTPXMock) -> None:
    """Version endpoint must return a JSON object."""
    client = BragerOneApiClient(validate_on_start=False)
    httpx_mock.add_response(
        method="GET",
        url=f"{API}/v1/system/version?container=BragerOne&platform=0",
        json=["nope"],
    )
    with pytest.raises(ApiError) as exc:
        await client.get_system_version()
    assert exc.value.status == 500
    await client.close()


async def test_req_without_token_is_401() -> None:
    """Authenticated _req without a token fails locally before HTTP."""
    client = BragerOneApiClient(validate_on_start=False)
    with pytest.raises(ApiError) as exc:
        await client._req("GET", f"{API}/v1/user")
    assert exc.value.status == 401
    await client.close()


async def test_fetch_json_one_returns_none_for_non_json(httpx_mock: HTTPXMock) -> None:
    """Asset text that is not JSON becomes ``(status, None)``."""
    client = BragerOneApiClient(validate_on_start=False)
    client._token = Token(access_token="T1")
    httpx_mock.add_response(
        method="GET",
        url=f"{ONE}/index.js",
        text="export default {}",
        headers={"Content-Type": "application/javascript"},
    )
    status, payload = await client.fetch_json_one("index.js")
    assert status == 200
    assert payload is None
    await client.close()


async def test_http_trace_redacts_authorization(httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture) -> None:
    """HTTP tracing logs the request and redacts the bearer token."""
    client = BragerOneApiClient(validate_on_start=False, enable_http_trace=True, redact_secrets=True)
    client._token = Token(access_token="secret-token")
    httpx_mock.add_response(method="GET", url=f"{API}/v1/user", json={"user": {"id": 1, "email": TEST_EMAIL}})
    with caplog.at_level("DEBUG", logger="pybragerone.http"):
        await client._req("GET", f"{API}/v1/user")
    assert "<redacted>" in caplog.text
    assert "secret-token" not in caplog.text
    await client.close()


class _ScriptedSession:
    """Fake httpx session with a programmed get() sequence."""

    def __init__(self, responses: list[httpx.Response | BaseException]) -> None:
        """Store scripted outcomes."""
        self._responses = list(responses)
        self.calls = 0

    async def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """Return the next scripted response or raise."""
        del headers
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _response(status: int, content: bytes = b"", headers: dict[str, str] | None = None) -> httpx.Response:
    """Build an httpx response bound to a dummy request."""
    request = httpx.Request("GET", "https://example.test/a.js")
    return httpx.Response(status, content=content, headers=headers or {}, request=request)


async def test_get_bytes_uses_cache_on_304(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 304 with a cached body returns the stored bytes."""
    client = BragerOneApiClient(validate_on_start=False)
    client._cache.update("https://example.test/a.js", {"ETag": '"e1"'}, b"cached")
    fake = _ScriptedSession([_response(304)])

    async def _session() -> _ScriptedSession:
        return fake

    monkeypatch.setattr(client, "_ensure_session", _session)
    body = await client.get_bytes("https://example.test/a.js")
    assert body == b"cached"
    assert fake.calls == 1
    await client.close()


async def test_get_bytes_refetches_when_304_has_no_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 304 without a prior body triggers an unconditional refetch."""
    client = BragerOneApiClient(validate_on_start=False)
    fake = _ScriptedSession([_response(304), _response(200, b"fresh", {"ETag": '"e2"'})])

    async def _session() -> _ScriptedSession:
        return fake

    monkeypatch.setattr(client, "_ensure_session", _session)
    body = await client.get_bytes("https://example.test/a.js")
    assert body == b"fresh"
    assert fake.calls == 2
    await client.close()


async def test_get_bytes_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 429 is retried; a later 200 wins."""
    client = BragerOneApiClient(validate_on_start=False)
    fake = _ScriptedSession([_response(429), _response(200, b"ok")])
    sleeps: list[float] = []

    async def _session() -> _ScriptedSession:
        return fake

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(client, "_ensure_session", _session)
    monkeypatch.setattr("pybragerone.api.client.asyncio.sleep", _sleep)
    body = await client.get_bytes("https://example.test/a.js")
    assert body == b"ok"
    assert sleeps == [0.2]
    await client.close()
