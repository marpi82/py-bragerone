"""Tests for gateway per-module cloud connectivity signals."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from types import SimpleNamespace
from typing import Any

import pytest

from pybragerone.gateway import BragerOneGateway, module_connected_at_means_online
from pybragerone.models.events import ModuleConnectivity


class FakeApiClient:
    """Fake API client with controllable ``get_modules`` rows."""

    def __init__(self) -> None:
        """Initialize the fake API client."""
        self.module_rows: list[Any] = []
        self.get_modules_calls = 0
        self.get_modules_error: Exception | None = None
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
        """Return success without side effects."""
        return True

    async def modules_parameters_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Return an empty successful prime."""
        if not return_data:
            return True
        return 200, {}

    async def modules_activity_quantity_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Return an empty successful activity prime."""
        if not return_data:
            return True
        return 200, {}

    async def get_modules(self, object_id: int) -> list[Any]:
        """Return the configured module rows (or raise when configured)."""
        self.get_modules_calls += 1
        if self.get_modules_error is not None:
            raise self.get_modules_error
        return list(self.module_rows)

    async def close(self) -> None:
        """Mark the client as closed."""
        self.closed = True


class FakeRealtimeManager:
    """Fake WS manager with connect/disconnect hooks."""

    def __init__(self) -> None:
        """Initialize the fake realtime manager."""
        self._on_connected: list[Callable[[], Awaitable[None] | None]] = []
        self._on_disconnected: list[Callable[[], Awaitable[None] | None]] = []
        self._on_event: Callable[[str, Any], Awaitable[None] | None] | None = None
        self.group_id: int | None = None

    def on_event(self, cb: Callable[[str, Any], Awaitable[None] | None]) -> None:
        """Store the event callback."""
        self._on_event = cb

    async def connect(self) -> None:
        """No-op connect."""

    async def disconnect(self) -> None:
        """No-op disconnect."""

    def add_on_connected(self, cb: Callable[[], Awaitable[None] | None]) -> None:
        """Register reconnect callback."""
        self._on_connected.append(cb)

    def add_on_disconnected(self, cb: Callable[[], Awaitable[None] | None]) -> None:
        """Register disconnect callback."""
        self._on_disconnected.append(cb)

    def sid(self) -> str | None:
        """Return a namespace SID."""
        return "NS-SID"

    def engine_sid(self) -> str | None:
        """Return an engine SID."""
        return "ENG-SID"

    async def subscribe(self, modules: Iterable[str]) -> None:
        """No-op subscribe."""

    async def trigger_disconnected(self) -> None:
        """Invoke disconnect callbacks."""
        for cb in list(self._on_disconnected):
            res = cb()
            if asyncio.iscoroutine(res):
                await res


def test_module_connected_at_means_online() -> None:
    """``connectedAt == 0`` is the upstream offline sentinel."""
    assert module_connected_at_means_online(0) is False
    assert module_connected_at_means_online(1_700_000_000) is True


@pytest.mark.asyncio
async def test_gateway_connectivity_from_rest_and_ws_disconnect() -> None:
    """REST connectedAt drives online; WS disconnect forces offline and notifies."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=1_700_000_000)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1", "M2"],
        ws=ws,
        connectivity_poll_interval=0,
    )

    events: list[ModuleConnectivity] = []
    gw.on_module_connectivity(events.append)

    assert gw.module_online("M1") is None
    await gw.start()

    assert api.get_modules_calls == 1
    assert gw.module_online("M1") is True
    assert gw.module_connected_at("M1") == 1_700_000_000
    assert gw.module_online("M2") is False  # missing from listing
    assert [(e.devid, e.online, e.source) for e in events] == [
        ("M1", True, "rest"),
        ("M2", False, "derived"),
    ]

    events.clear()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=0)]
    await gw.refresh_module_connectivity()
    assert gw.module_online("M1") is False
    offline = list(events)
    assert len(offline) == 1
    assert offline[0].online is False
    assert offline[0].source == "rest"

    events.clear()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=1_700_000_001)]
    await gw.refresh_module_connectivity()
    assert gw.module_online("M1") is True

    events.clear()
    await ws.trigger_disconnected()
    # Allow spawned disconnect task to finish.
    await asyncio.sleep(0)
    assert gw.module_online("M1") is False
    assert gw.module_online("M2") is False
    disc = list(events)
    assert {e.source for e in disc} == {"ws"}
    assert all(not e.online for e in disc)

    # While WS is down, REST refresh is a no-op (stay offline).
    events.clear()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=1_700_000_002)]
    await gw.refresh_module_connectivity()
    assert events == []
    assert gw.module_online("M1") is False

    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_poll_loop_and_get_modules_error() -> None:
    """Background poll refreshes state; get_modules failures are logged and ignored."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
    )
    await gw.start()
    assert gw.module_online("M1") is True

    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=0)]
    await asyncio.sleep(0.12)
    assert gw.module_online("M1") is False

    api.get_modules_error = RuntimeError("modules down")
    # Another poll tick should not raise out of the gateway.
    await asyncio.sleep(0.12)
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_skips_blank_devid_rows() -> None:
    """Rows without a devid are ignored during REST refresh."""
    api = FakeApiClient()
    api.module_rows = [
        SimpleNamespace(devid="", connectedAt=99),
        SimpleNamespace(devid="M1", connectedAt=99),
    ]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    assert gw.module_online("M1") is True
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_from_ws_connection_status_event() -> None:
    """SPA ``app:module:connection:status:changed`` updates online + gateway."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=0, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    events: list[ModuleConnectivity] = []
    gw.on_module_connectivity(events.append)
    await gw.start()
    assert gw.module_online("M1") is False
    events.clear()

    result = ws._on_event(
        "app:module:connection:status:changed",
        {
            "M1": {
                "connectedAt": 1_700_000_100,
                "gateway": {"address": "10.0.0.2", "interface": "wifi", "version": "V2.08"},
            }
        },
    )
    if asyncio.iscoroutine(result):
        await result
    await asyncio.sleep(0)

    assert gw.module_online("M1") is True
    assert gw.module_connected_at("M1") == 1_700_000_100
    assert gw.module_gateway("M1") == {"address": "10.0.0.2", "interface": "wifi", "version": "V2.08"}
    assert len(events) == 1
    assert events[0].source == "ws"
    assert events[0].online is True
    assert events[0].gateway == {"address": "10.0.0.2", "interface": "wifi", "version": "V2.08"}

    events.clear()
    result = ws._on_event(
        "app:module:connection:status:changed",
        {"M1": {"connectedAt": 0, "gateway": {"address": None, "interface": None, "version": None}}},
    )
    if asyncio.iscoroutine(result):
        await result
    await asyncio.sleep(0)
    assert gw.module_online("M1") is False
    assert events[0].online is False
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_apply_without_connected_at() -> None:
    """WS-driven offline updates may omit a fresh connectedAt value."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    await gw._apply_connectivity(devid="M1", online=False, source="ws", connected_at=None)
    assert gw.module_online("M1") is False
    assert gw.module_connected_at("M1") == 50
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_callback_error_does_not_abort() -> None:
    """A raising connectivity callback does not block later listeners."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=99)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)

    seen: list[bool] = []

    def _boom(_event: ModuleConnectivity) -> None:
        raise RuntimeError("cb")

    def _ok(event: ModuleConnectivity) -> None:
        seen.append(event.online)

    gw.on_module_connectivity(_boom)
    gw.on_module_connectivity(_ok)
    await gw.start()
    assert seen == [True]
    await gw.stop()
