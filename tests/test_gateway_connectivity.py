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
        """Invoke disconnect callbacks like a real socket drop."""
        for cb in list(self._on_disconnected):
            res = cb()
            if asyncio.iscoroutine(res):
                await res

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
async def test_gateway_connectivity_from_rest_and_ws_disconnect_preserves_online() -> None:
    """REST connectedAt drives online; client WS disconnect does not force offline."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=1_700_000_000, gateway=None)]
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
    assert gw.module_online("M2") is False
    assert [(e.devid, e.online, e.source) for e in events] == [
        ("M1", True, "rest"),
        ("M2", False, "derived"),
    ]

    events.clear()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=0, gateway=None)]
    await gw.refresh_module_connectivity()
    assert gw.module_online("M1") is False
    offline = list(events)
    assert len(offline) == 1
    assert offline[0].online is False
    assert offline[0].source == "rest"

    events.clear()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=1_700_000_001, gateway=None)]
    await gw.refresh_module_connectivity()
    assert gw.module_online("M1") is True

    events.clear()
    await ws.trigger_disconnected()
    await asyncio.sleep(0)
    assert gw.module_online("M1") is True
    assert gw.ws_session_up() is False
    assert events == []

    events.clear()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=0, gateway=None)]
    await gw.refresh_module_connectivity()
    assert gw.module_online("M1") is False
    assert events[0].source == "rest"

    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_empty_listing_does_not_wipe() -> None:
    """An empty get_modules result must not mark every module offline."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    assert gw.module_online("M1") is True

    api.module_rows = []
    await gw.refresh_module_connectivity()
    assert gw.module_online("M1") is True
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_poll_loop_and_get_modules_error() -> None:
    """Background poll refreshes state; get_modules failures are logged and ignored."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
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

    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=0, gateway=None)]
    await asyncio.sleep(0.12)
    assert gw.module_online("M1") is False

    api.get_modules_error = RuntimeError("modules down")
    await asyncio.sleep(0.12)
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_skips_blank_devid_rows() -> None:
    """Rows without a devid are ignored during REST refresh."""
    api = FakeApiClient()
    api.module_rows = [
        SimpleNamespace(devid="", connectedAt=99, gateway=None),
        SimpleNamespace(devid="M1", connectedAt=99, gateway=None),
    ]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    assert gw.module_online("M1") is True
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_metadata_notifies_without_online_flip() -> None:
    """Gateway/connectedAt updates notify even when online stays True."""
    api = FakeApiClient()
    api.module_rows = [
        SimpleNamespace(
            devid="M1",
            connectedAt=50,
            gateway={"address": "1.1.1.1", "interface": "wifi", "version": "V1"},
        )
    ]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    events: list[ModuleConnectivity] = []
    gw.on_module_connectivity(events.append)
    await gw.start()
    events.clear()

    api.module_rows = [
        SimpleNamespace(
            devid="M1",
            connectedAt=51,
            gateway={"address": "1.1.1.2", "interface": "wifi", "version": "V1"},
        )
    ]
    await gw.refresh_module_connectivity()
    assert gw.module_online("M1") is True
    assert len(events) == 1
    assert events[0].online_changed is False
    assert events[0].metadata_changed is True
    assert events[0].connected_at == 51
    assert events[0].gateway == {"address": "1.1.1.2", "interface": "wifi", "version": "V1"}
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
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_callback_error_does_not_abort() -> None:
    """A raising connectivity callback does not block later listeners."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=99, gateway=None)]
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


@pytest.mark.asyncio
async def test_gateway_stop_does_not_force_offline_callbacks() -> None:
    """stop() must not emit mass-offline connectivity events after shutdown."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=99, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    events: list[ModuleConnectivity] = []
    gw.on_module_connectivity(events.append)
    await gw.start()
    events.clear()
    await gw.stop()
    await asyncio.sleep(0)
    assert events == []
    assert gw.module_online("M1") is True
