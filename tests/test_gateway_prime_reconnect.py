"""Gateway prime/resubscribe behavior tests."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from pytest_httpx import HTTPXMock

from pybragerone.api import BragerOneApiClient
from pybragerone.gateway import BragerOneGateway
from pybragerone.models import Token
from pybragerone.models.events import ParamUpdate

API = "https://io.brager.pl"
TEST_EMAIL = "a@b"
TEST_PASSWORD = "pw"


class FakeApiClient:
    """Fake API client implementing the gateway's HTTP surface."""

    def __init__(self) -> None:
        """Initialize the fake API client."""
        self._modules_connect_calls: list[tuple[str, list[str], int | None, str | None]] = []
        self._prime_params_calls: list[list[str]] = []
        self._prime_activity_calls: list[list[str]] = []
        self.closed = False

    @property
    def access_token(self) -> str:
        """Return a fake bearer token."""
        return "fake-token"

    async def modules_connect(
        self,
        wsid_ns: str,
        modules: list[str],
        group_id: int | None = None,
        engine_sid: str | None = None,
    ) -> bool:
        """Record a connect call and return success."""
        self._modules_connect_calls.append((wsid_ns, list(modules), group_id, engine_sid))
        return True

    async def modules_parameters_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Return a minimal parameters prime payload."""
        self._prime_params_calls.append(list(modules))
        if not return_data:
            return True

        payload: dict[str, Any] = {
            "DEV1": {
                "P4": {
                    "v1": {"value": 123},
                }
            }
        }
        return 200, payload

    async def modules_activity_quantity_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Return a minimal activity prime payload."""
        self._prime_activity_calls.append(list(modules))
        if not return_data:
            return True
        return 200, {"activityQuantity": {}}

    async def get_modules(self, object_id: int) -> list[Any]:
        """Return no modules by default (connectivity stays unknown/offline)."""
        return []

    async def close(self) -> None:
        """Mark the client as closed."""
        self.closed = True


class FakeRealtimeManager:
    """Fake WS manager implementing the gateway's realtime surface."""

    def __init__(self, *, sid: str = "NS-SID", engine_sid: str = "ENG-SID") -> None:
        """Initialize the fake realtime manager."""
        self._sid = sid
        self._engine_sid = engine_sid
        self._on_connected: list[Callable[[], Awaitable[None] | None]] = []
        self._on_disconnected: list[Callable[[], Awaitable[None] | None]] = []
        self._on_event: Callable[[str, Any], Awaitable[None] | None] | None = None

        self.group_id: int | None = None
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.subscribe_calls: list[list[str]] = []

    def on_event(self, cb: Callable[[str, Any], Awaitable[None] | None]) -> None:
        """Store the event callback."""
        self._on_event = cb

    async def connect(self) -> None:
        """Record a connect call."""
        self.connect_calls += 1

    async def disconnect(self) -> None:
        """Record a disconnect call."""
        self.disconnect_calls += 1

    def add_on_connected(self, cb: Callable[[], Awaitable[None] | None]) -> None:
        """Register a callback invoked after a (re)connect."""
        self._on_connected.append(cb)

    def add_on_disconnected(self, cb: Callable[[], Awaitable[None] | None]) -> None:
        """Register a callback invoked after a disconnect."""
        self._on_disconnected.append(cb)

    def sid(self) -> str | None:
        """Return a namespace SID."""
        return self._sid

    def engine_sid(self) -> str | None:
        """Return an engine SID."""
        return self._engine_sid

    async def subscribe(self, modules: Iterable[str]) -> None:
        """Record a subscribe call."""
        self.subscribe_calls.append(list(modules))

    async def force_reconnect(self) -> None:
        """Simulate hard reconnect used by zombie-session recovery."""
        await self.trigger_disconnected()
        await self.trigger_connected()

    async def hard_reset(self) -> None:
        """Simulate transport replacement used by zombie recycle."""
        await self.disconnect()
        await self.connect()

    async def trigger_connected(self) -> None:
        """Trigger all registered on_connected callbacks."""
        tasks: list[asyncio.Task[None]] = []
        for cb in list(self._on_connected):
            res = cb()
            if asyncio.iscoroutine(res):
                tasks.append(asyncio.create_task(cast(Coroutine[Any, Any, None], res)))
        if tasks:
            await asyncio.gather(*tasks)

    async def trigger_disconnected(self) -> None:
        """Trigger all registered on_disconnected callbacks."""
        tasks: list[asyncio.Task[None]] = []
        for cb in list(self._on_disconnected):
            res = cb()
            if asyncio.iscoroutine(res):
                tasks.append(asyncio.create_task(cast(Coroutine[Any, Any, None], res)))
        if tasks:
            await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_gateway_start_primes_and_subscribes() -> None:
    """Gateway start connects, subscribes, and injects prime updates."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()

    gw = BragerOneGateway(api=api, object_id=123, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    it = gw.bus.subscribe()
    first_update_task = asyncio.create_task(it.__anext__())
    try:
        await gw.start()
        upd = await asyncio.wait_for(first_update_task, timeout=1.0)
    finally:
        first_update_task.cancel()
        await it.aclose()

    assert ws.connect_calls == 1
    assert ws.subscribe_calls == [["M1"]]
    assert api._modules_connect_calls == [("NS-SID", ["M1"], 123, "ENG-SID")]
    assert api._prime_params_calls == [["M1"]]
    assert api._prime_activity_calls == [["M1"]]

    assert isinstance(upd, ParamUpdate)
    assert upd.devid == "DEV1"
    assert upd.pool == "P4"
    assert upd.chan == "v"
    assert upd.idx == 1
    assert upd.value == 123

    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_resubscribe_on_connected_reprimes() -> None:
    """WS reconnect triggers resubscribe and a fresh prime."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()

    gw = BragerOneGateway(api=api, object_id=123, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()

    await ws.trigger_connected()

    assert api._modules_connect_calls == [
        ("NS-SID", ["M1"], 123, "ENG-SID"),
        ("NS-SID", ["M1"], 123, "ENG-SID"),
    ]
    assert ws.subscribe_calls == [["M1"], ["M1"]]
    assert api._prime_params_calls == [["M1"], ["M1"]]
    assert api._prime_activity_calls == [["M1"], ["M1"]]

    await gw.stop()


async def test_start_wires_self_healing_token_provider(monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock) -> None:
    """A gateway-created RealtimeManager gets a token provider that re-logins after token expiry."""
    api = BragerOneApiClient(creds_provider=lambda: (TEST_EMAIL, TEST_PASSWORD))
    # Simulate a long-running session whose token expired during an outage.
    api._token = Token(access_token="EXPIRED", expires_at=datetime.now(UTC) - timedelta(hours=1))

    captured: dict[str, Any] = {}

    def _fake_rm(**kwargs: Any) -> FakeRealtimeManager:
        captured.update(kwargs)
        return FakeRealtimeManager()

    monkeypatch.setattr("pybragerone.gateway.RealtimeManager", _fake_rm)
    # The wiring under test is WS construction; stub the REST prime calls on the real client.
    monkeypatch.setattr(api, "modules_connect", lambda *a, **k: _async_true())
    monkeypatch.setattr(api, "modules_parameters_prime", lambda *a, **k: _async_true())
    monkeypatch.setattr(api, "modules_activity_quantity_prime", lambda *a, **k: _async_true())
    monkeypatch.setattr(api, "get_modules", lambda *a, **k: _async_empty_modules())

    httpx_mock.add_response(
        method="POST",
        url=f"{API}/v1/auth/user",
        json={
            "accessToken": "FRESH",
            "refreshToken": "R2",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        },
    )

    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], connectivity_poll_interval=0)
    await gw.start()

    provider = captured.get("token_provider")
    assert provider is not None, "gateway must wire a token provider into RealtimeManager"
    assert await provider() == "FRESH"
    assert api.access_token == "FRESH"

    await gw.stop()


async def _async_true() -> bool:
    return True


async def _async_empty_modules() -> list[Any]:
    return []
