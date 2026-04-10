"""Tests for transient retry behavior in BragerOneApiClient.get_bytes."""

from __future__ import annotations

import httpx
import pytest

from pybragerone.api.client import BragerOneApiClient


class _FakeSession:
    """Simple fake session with programmable get() sequence."""

    def __init__(self) -> None:
        """Initialize call counter and scripted outcomes."""
        self.calls = 0

    async def get(self, _url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """Fail first call with timeout, then return success response."""
        self.calls += 1
        if self.calls == 1:
            raise httpx.ReadTimeout("timeout")
        request = httpx.Request("GET", "https://example.test/assets/index.js", headers=headers)
        return httpx.Response(200, content=b"ok", headers={"ETag": "abc"}, request=request)


@pytest.mark.asyncio
async def test_get_bytes_retries_transient_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_bytes should retry on transient timeout and eventually succeed."""
    client = BragerOneApiClient()
    fake = _FakeSession()

    async def _fake_ensure_session() -> _FakeSession:
        return fake

    monkeypatch.setattr(client, "_ensure_session", _fake_ensure_session)

    body = await client.get_bytes("https://example.test/assets/index.js")

    assert body == b"ok"
    assert fake.calls == 2
