"""Tests for gateway per-module cloud connectivity signals."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterable
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ReadTimeout, TimeoutException
from pytest_httpx import HTTPXMock

from pybragerone.api.client import ApiError, BragerOneApiClient
from pybragerone.gateway import (
    ApiClient,
    BragerOneGateway,
    ConnectivitySource,
    RealtimeManagerClient,
    _gateway_as_dict,
    _is_api_dispatch_timeout,
    _is_http_timeout_error,
    _parse_connected_at,
    module_connected_at_means_online,
)
from pybragerone.models.events import ModuleConnectivity


class FakeApiClient:
    """Fake API client with controllable ``get_modules`` rows."""

    def __init__(self) -> None:
        """Initialize the fake API client."""
        self.module_rows: list[Any] = []
        self.get_modules_calls = 0
        self.get_modules_error: Exception | None = None
        self.prime_params_calls = 0
        self.modules_connect_calls = 0
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
        self.modules_connect_calls += 1
        return True

    async def modules_parameters_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Return an empty successful prime."""
        self.prime_params_calls += 1
        if not return_data:
            return True
        return 200, {}

    async def modules_activity_quantity_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Return an empty successful activity prime."""
        if not return_data:
            return True
        return 200, {}

    async def modules_alarms_quantity(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Return an empty successful alarm quantity prime."""
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
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.subscribe_calls: list[list[str]] = []
        self.force_reconnect_calls = 0
        self.hard_reset_calls = 0

    def on_event(self, cb: Callable[[str, Any], Awaitable[None] | None]) -> None:
        """Store the event callback."""
        self._on_event = cb

    async def connect(self) -> None:
        """Record a connect call."""
        self.connect_calls += 1

    async def disconnect(self) -> None:
        """Invoke disconnect callbacks like a real socket drop."""
        self.disconnect_calls += 1
        for cb in list(self._on_disconnected):
            res = cb()
            if asyncio.iscoroutine(res):
                # Bind the discarded None so CodeQL does not treat bare ``await`` as ineffectual.
                _ = await res

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
        """Record a subscribe call."""
        self.subscribe_calls.append(list(modules))

    async def force_reconnect(self) -> None:
        """Simulate SPA-style hard reconnect: disconnect hooks then connect hooks."""
        self.force_reconnect_calls += 1
        await self.trigger_disconnected()
        for cb in list(self._on_connected):
            res = cb()
            if asyncio.iscoroutine(res):
                _ = await res

    async def hard_reset(self) -> None:
        """Simulate transport replacement: disconnect then connect."""
        self.hard_reset_calls += 1
        await self.disconnect()
        await self.connect()

    async def trigger_disconnected(self) -> None:
        """Invoke disconnect callbacks."""
        for cb in list(self._on_disconnected):
            res = cb()
            if asyncio.iscoroutine(res):
                # Bind the discarded None so CodeQL does not treat bare ``await`` as ineffectual.
                _ = await res

    async def emit(self, name: str, payload: Any) -> None:
        """Dispatch a fake Socket.IO event through the registered handler."""
        handler = self._on_event
        assert handler is not None
        result = handler(name, payload)
        if asyncio.iscoroutine(result):
            # Bind the discarded None so CodeQL does not treat bare ``await`` as ineffectual.
            _ = await result
        elif result is not None:
            raise TypeError(f"event handler returned unexpected value: {type(result)!r}")


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


async def _wait_until(predicate: Callable[[], bool], *, timeout: float = 2.0) -> None:
    """Spin until ``predicate`` is true without relying on a fixed wall-clock sleep."""

    async def _spin() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(_spin(), timeout=timeout)


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
    await _wait_until(lambda: gw.module_online("M1") is False)
    assert gw.module_online("M1") is False

    calls_before_error = api.get_modules_calls
    api.get_modules_error = RuntimeError("modules down")
    await _wait_until(lambda: api.get_modules_calls > calls_before_error)
    assert gw.module_online("M1") is False
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_timeout_errors_are_warn_only(caplog: pytest.LogCaptureFixture) -> None:
    """Expected timeout-like failures should not emit full traceback spam."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()

    with caplog.at_level("WARNING"):
        api.get_modules_error = ReadTimeout("read timeout")
        await gw.refresh_module_connectivity()
    assert "get_modules unavailable/timeout during connectivity refresh" in caplog.text
    assert not any(record.exc_info for record in caplog.records)

    caplog.clear()
    with caplog.at_level("WARNING"):
        api.get_modules_error = ApiError(
            408,
            {"status": "E_DISPATCH_EVENT_TIMEOUT", "message": "upstream timeout"},
            {},
        )
        await gw.refresh_module_connectivity()
    assert "get_modules unavailable/timeout during connectivity refresh" in caplog.text
    assert not any(record.exc_info for record in caplog.records)

    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_connectivity_503_errors_are_warn_only(caplog: pytest.LogCaptureFixture) -> None:
    """Expected 503 upstream outages should not emit full traceback spam."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()

    with caplog.at_level("WARNING"):
        api.get_modules_error = ApiError(503, "<html>Service Unavailable</html>", {})
        await gw.refresh_module_connectivity()
    assert "get_modules unavailable/timeout during connectivity refresh" in caplog.text
    assert not any(record.exc_info for record in caplog.records)
    assert gw.module_online("M1") is True

    await gw.stop()


def test_gateway_timeout_error_helpers() -> None:
    """Timeout helpers classify only expected timeout-like exceptions."""
    assert _is_http_timeout_error(ReadTimeout("t")) is True
    assert _is_http_timeout_error(TimeoutException("t")) is True

    class ForeignReadTimeout(Exception):
        __module__ = "other"

    assert _is_http_timeout_error(ForeignReadTimeout()) is False
    assert _is_http_timeout_error(RuntimeError("no")) is False

    assert _is_api_dispatch_timeout(ApiError(408, {"status": "E_DISPATCH_EVENT_TIMEOUT"}, {})) is True
    assert _is_api_dispatch_timeout(ApiError(408, {"status": "OTHER"}, {})) is False
    assert _is_api_dispatch_timeout(ApiError(408, "not-a-dict", {})) is False
    assert _is_api_dispatch_timeout(ApiError(500, {"status": "E_DISPATCH_EVENT_TIMEOUT"}, {})) is False


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

    await ws.emit(
        "app:module:connection:status:changed",
        {
            "M1": {
                "connectedAt": 1_700_000_100,
                "gateway": {"address": "10.0.0.2", "interface": "wifi", "version": "V2.08"},
            }
        },
    )
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


def test_parse_connected_at_and_gateway_helpers() -> None:
    """Helpers accept SPA shapes and reject unusable values."""
    assert _parse_connected_at(None) is None
    assert _parse_connected_at("nope") is None
    assert _parse_connected_at(12) == 12
    assert _gateway_as_dict(None) is None
    assert _gateway_as_dict({"address": "1.1.1.1"}) == {"address": "1.1.1.1"}
    assert _gateway_as_dict(SimpleNamespace(model_dump=lambda mode="json": {"address": "2.2.2.2"})) == {"address": "2.2.2.2"}
    assert _gateway_as_dict(SimpleNamespace(model_dump=lambda mode="json": "bad")) is None
    assert _gateway_as_dict("not-a-gateway") is None


def test_protocol_surfaces_are_importable() -> None:
    """Gateway Protocols stay part of the public typing surface for fakes/tests."""
    assert callable(ApiClient.get_modules)
    assert callable(RealtimeManagerClient.hard_reset)
    assert callable(RealtimeManagerClient.add_on_disconnected)


@pytest.mark.asyncio
async def test_gateway_connectivity_edge_paths() -> None:
    """Cover refresh/ingest/stop edge cases that keep SPA parity fail-closed."""
    api = FakeApiClient()
    api.module_rows = [
        SimpleNamespace(
            devid="M1",
            connectedAt=50,
            gateway=SimpleNamespace(model_dump=lambda mode="json": {"address": "9.9.9.9"}),
        )
    ]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1", "M2"], ws=ws, connectivity_poll_interval=0)

    # Refresh before start is a no-op.
    await gw.refresh_module_connectivity()
    assert gw.module_online("M1") is None

    events: list[ModuleConnectivity] = []
    gw.on_module_connectivity(events.append)
    await gw.start()
    assert gw.module_online("M1") is True
    assert gw.module_gateway("M1") == {"address": "9.9.9.9"}
    events.clear()

    # Unusable connectedAt rows are skipped (no false offline).
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt="bad", gateway=None)]
    await gw.refresh_module_connectivity()
    assert gw.module_online("M1") is True
    assert events == []

    # WS ingest: ignore foreign devid / non-dict body / bad connectedAt.
    await gw._ingest_module_connection_status(
        {
            "OTHER": {"connectedAt": 1},
            "M1": "not-a-dict",
            "M2": {"connectedAt": "bad"},
        }
    )
    assert gw.module_online("M1") is True

    # Gateway-only WS update refreshes metadata without inventing online.
    await gw._ingest_module_connection_status({"M1": {"gateway": {"address": "8.8.8.8"}}})
    assert gw.module_gateway("M1") == {"address": "8.8.8.8"}
    assert gw.module_online("M1") is True

    # Gateway-only update with no prior online + empty gateway is ignored.
    await gw._ingest_module_connection_status({"M2": {"gateway": None}})
    assert gw.module_online("M2") is False

    # Ingest after stop is ignored.
    await gw.stop()
    await gw._ingest_module_connection_status({"M1": {"connectedAt": 0}})
    assert gw.module_online("M1") is True


@pytest.mark.asyncio
async def test_gateway_ws_reconnect_and_poll_exception_paths() -> None:
    """Reconnect hooks and poll-tick exceptions must not tear down the gateway."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0.05)
    await gw.start()

    # Stale reconnect while stopped is ignored.
    gw._ws_session_up = False
    gw._started = False
    await gw._on_ws_connected()
    assert gw.ws_session_up() is False
    gw._started = True

    async def _boom_resubscribe() -> bool:
        raise RuntimeError("resubscribe failed")

    gw.resubscribe = _boom_resubscribe  # type: ignore[method-assign]
    await gw._on_ws_connected()
    assert gw.ws_session_up() is True

    tick_hits = 0

    async def _boom_refresh(*, source: ConnectivitySource = "rest") -> None:
        nonlocal tick_hits
        _ = source
        tick_hits += 1
        raise RuntimeError("tick failed")

    gw._refresh_module_connectivity = _boom_refresh  # type: ignore[method-assign]
    await _wait_until(lambda: tick_hits >= 1)

    async def _boom_cancel() -> None:
        raise RuntimeError("cancel failed")

    gw._cancel_all_tasks = _boom_cancel  # type: ignore[method-assign]
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_ingest_skips_gateway_only_when_online_unknown() -> None:
    """Gateway-only WS updates require a known prior online bit."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1", "M2"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    gw._module_online.pop("M2", None)
    gw._module_gateway.pop("M2", None)
    await gw._ingest_module_connection_status({"M2": {"gateway": {"address": "1.2.3.4"}}})
    assert gw.module_online("M2") is None
    assert gw.module_gateway("M2") is None
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_start_registers_ws_hooks_once() -> None:
    """Second start after stop must not duplicate Socket.IO connected/disconnected hooks."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    assert len(ws._on_connected) == 1
    assert gw._ws_hooks_registered is True
    await gw.stop()
    # stop clears started but keeps hook registration so reconnect paths stay single-shot.
    assert gw._ws_hooks_registered is True
    await gw.start()
    assert len(ws._on_connected) == 1
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_start_requires_realtime_manager() -> None:
    """start() must fail when owned WS construction returns no client."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=None, connectivity_poll_interval=0)
    gw._make_realtime_manager = lambda: None  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="RealtimeManager is not initialized"):
        await gw.start()


@pytest.mark.asyncio
async def test_gateway_start_requires_namespace_sid() -> None:
    """start() must fail when Socket.IO reports no namespace SID after connect."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    ws.sid = lambda: None  # type: ignore[method-assign]
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    with pytest.raises(RuntimeError, match="No namespace SID"):
        await gw.start()


@pytest.mark.asyncio
async def test_gateway_reconnect_skips_stale_generation_refresh() -> None:
    """A reconnect finally block must not refresh after a newer disconnect generation."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    calls_before = api.get_modules_calls

    async def _slow_resubscribe() -> bool:
        await gw._on_ws_disconnected()
        return False

    gw.resubscribe = _slow_resubscribe  # type: ignore[method-assign]
    await gw._on_ws_connected()
    assert api.get_modules_calls == calls_before
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_cloud_session_callbacks_are_detectable() -> None:
    """Library↔cloud session flips notify on_cloud_session without touching module online."""
    from pybragerone.models.events import CloudSessionConnectivity

    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    sessions: list[CloudSessionConnectivity] = []
    gw.on_cloud_session(sessions.append)

    await gw.start()
    assert gw.ws_session_up() is True
    assert [(e.up, e.source) for e in sessions] == [(True, "connect")]
    assert gw.module_online("M1") is True

    sessions.clear()
    await ws.trigger_disconnected()
    assert gw.ws_session_up() is False
    assert [(e.up, e.source) for e in sessions] == [(False, "disconnect")]
    assert gw.module_online("M1") is True

    sessions.clear()
    await gw._on_ws_connected()
    assert gw.ws_session_up() is True
    assert sessions[0].up is True
    assert sessions[0].source == "connect"

    sessions.clear()
    await gw.stop()
    assert gw.ws_session_up() is False
    assert [(e.up, e.source) for e in sessions] == [(False, "stop")]


@pytest.mark.asyncio
async def test_gateway_cloud_session_outage_duration_and_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cloud session down→up records down_for_s / reason and logs restore."""
    from pybragerone.models.events import CloudSessionConnectivity

    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    sessions: list[CloudSessionConnectivity] = []
    gw.on_cloud_session(sessions.append)

    clock = {"mono": 1000.0, "wall": 1_700_000_000.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["mono"])
    monkeypatch.setattr(time, "time", lambda: clock["wall"])

    await gw.start()
    sessions.clear()
    await ws.trigger_disconnected()
    assert gw.ws_session_up() is False
    down_event = sessions[-1]
    assert down_event.up is False
    assert down_event.reason == "disconnect"
    assert down_event.down_since == 1_700_000_000.0
    assert down_event.down_for_s == 0.0
    snap = gw.cloud_session_outage()
    assert snap["reason"] == "disconnect"
    assert snap["down_since"] == 1_700_000_000.0

    clock["mono"] = 1012.5
    clock["wall"] = 1_700_000_012.5
    sessions.clear()
    await gw._on_ws_connected()
    assert gw.ws_session_up() is True
    up_event = sessions[0]
    assert up_event.up is True
    assert up_event.down_since is None
    assert up_event.down_for_s is None
    assert up_event.reason is None
    assert up_event.last_reason == "disconnect"
    assert up_event.last_down_for_s == 12.5
    snap = gw.cloud_session_outage()
    assert snap["down_since"] is None
    assert snap["last_reason"] == "disconnect"
    assert snap["last_down_for_s"] == 12.5
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_stop_while_down_does_not_carry_outage_across_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stop() while already down must close the outage so restart→connect is not a restore."""
    from pybragerone.models.events import CloudSessionConnectivity

    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    sessions: list[CloudSessionConnectivity] = []
    gw.on_cloud_session(sessions.append)

    clock = {"mono": 3000.0, "wall": 1_700_000_200.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["mono"])
    monkeypatch.setattr(time, "time", lambda: clock["wall"])

    await gw.start()
    sessions.clear()
    await ws.trigger_disconnected()
    assert gw.ws_session_up() is False
    assert gw.cloud_session_outage()["reason"] == "disconnect"
    assert gw.cloud_session_outage()["down_since"] == 1_700_000_200.0

    clock["mono"] = 3010.0
    clock["wall"] = 1_700_000_210.0
    await gw.stop()
    snap = gw.cloud_session_outage()
    assert snap["down_since"] is None
    assert snap["down_for_s"] is None
    assert snap["reason"] is None
    assert snap["last_reason"] == "disconnect"
    assert snap["last_down_for_s"] == 10.0

    clock["mono"] = 3500.0
    clock["wall"] = 1_700_000_700.0
    sessions.clear()
    await gw.start()
    assert gw.ws_session_up() is True
    up_event = sessions[0]
    assert up_event.up is True
    assert up_event.last_down_for_s == 10.0
    assert up_event.last_reason == "disconnect"
    # Must not report a "restore" that includes intentional stop downtime (~500s).
    assert up_event.down_since is None
    assert gw.cloud_session_outage()["down_since"] is None
    assert gw.cloud_session_outage()["last_down_for_s"] == 10.0
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_module_outage_duration_and_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """Module offline→online records outage duration without resetting on metadata-only updates."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway={"address": "a"})]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    events: list[ModuleConnectivity] = []
    gw.on_module_connectivity(events.append)

    clock = {"mono": 2000.0, "wall": 1_700_000_100.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["mono"])
    monkeypatch.setattr(time, "time", lambda: clock["wall"])

    await gw.start()
    events.clear()

    await gw._apply_connectivity(devid="M1", online=False, source="ws", connected_at=0)
    assert events[-1].online is False
    assert events[-1].reason == "ws"
    assert events[-1].down_since == 1_700_000_100.0
    down_since = events[-1].down_since

    clock["mono"] = 2008.0
    clock["wall"] = 1_700_000_108.0
    events.clear()
    await gw._apply_connectivity(
        devid="M1",
        online=False,
        source="rest",
        connected_at=0,
        gateway={"address": "b"},
    )
    assert events[-1].online_changed is False
    assert events[-1].reason == "ws"
    assert events[-1].down_since == down_since
    assert events[-1].down_for_s == 8.0

    events.clear()
    await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=99)
    up = events[-1]
    assert up.online is True
    assert up.down_since is None
    assert up.reason is None
    assert up.last_reason == "ws"
    assert up.last_down_for_s == 8.0
    snap = gw.module_outage("M1")
    assert snap["last_reason"] == "ws"
    assert snap["down_for_s"] is None
    await gw.stop()


async def test_gateway_duplicate_disconnect_does_not_bump_generation() -> None:
    """A second session-down while already down must not bump connectivity generation."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    await ws.trigger_disconnected()
    assert gw.ws_session_up() is False
    generation = gw._connectivity_generation
    await ws.trigger_disconnected()
    assert gw._connectivity_generation == generation
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_refresh_with_empty_module_list() -> None:
    """Empty subscription list skips derived-offline warnings."""
    api = FakeApiClient()
    api.module_rows = []
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=[], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    await gw.refresh_module_connectivity()
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_reprimes_parameters_while_ws_session_is_down() -> None:
    """While Socket.IO is down, the connectivity poll REST-primes so sensors can move."""
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
    primes_after_start = api.prime_params_calls
    assert primes_after_start >= 1

    await ws.trigger_disconnected()
    assert gw.ws_session_up() is False
    await _wait_until(lambda: api.prime_params_calls > primes_after_start)
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_logs_reprime_failure_while_ws_down() -> None:
    """REST re-prime exceptions while WS is down must not tear down the poll loop."""
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
    await ws.trigger_disconnected()
    assert gw.ws_session_up() is False

    hits = 0

    async def _boom_prime(tries: int = 3) -> tuple[bool, bool]:
        nonlocal hits
        _ = tries
        hits += 1
        raise RuntimeError("prime failed")

    gw._prime_with_retry = _boom_prime  # type: ignore[method-assign]
    await _wait_until(lambda: hits >= 1)
    assert gw._started is True
    await gw.stop()


@pytest.mark.asyncio
async def test_gateway_logs_reprime_503_as_warn_only(caplog: pytest.LogCaptureFixture) -> None:
    """Expected 503 during REST re-prime should warn without traceback spam."""
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
    await ws.trigger_disconnected()

    async def _boom_prime(tries: int = 3) -> tuple[bool, bool]:
        _ = tries
        raise ApiError(503, "<html>Service Unavailable</html>", {})

    gw._prime_with_retry = _boom_prime  # type: ignore[method-assign]  # test double replaces async method
    with caplog.at_level("WARNING"):
        await _wait_until(lambda: "REST re-prime failed due to expected upstream outage/timeout" in caplog.text)
    assert not any(record.exc_info for record in caplog.records)
    assert "ApiError(status=503)" in caplog.text
    assert "<html>" not in caplog.text
    assert gw._started is True
    await gw.stop()


async def test_gateway_reprimes_when_param_updates_stale_while_session_up() -> None:
    """A silent zombie session (up, no ParamUpdates) must REST-prime from the poll."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
        stale_prime_after_s=0.05,
        zombie_hard_restart_after=0,
    )
    await gw.start()
    primes_after_start = api.prime_params_calls
    assert gw.ws_session_up() is True
    assert gw.last_param_update_age_s() is None

    gw._last_param_publish_monotonic = 0.0
    await _wait_until(lambda: api.prime_params_calls > primes_after_start)
    assert gw.ws_session_up() is True
    assert ws.force_reconnect_calls == 0
    await gw.stop()


async def test_gateway_hard_restarts_ws_after_zombie_prime_streak() -> None:
    """After N consecutive zombie REST-primes, force SPA-style hard WS reconnect."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
        stale_prime_after_s=0.05,
        zombie_hard_restart_after=2,
    )
    await gw.start()
    connect_calls_after_start = api.modules_connect_calls
    primes_after_start = api.prime_params_calls
    gw._last_live_param_publish_monotonic = 0.0

    await _wait_until(lambda: ws.force_reconnect_calls >= 1)
    assert api.prime_params_calls > primes_after_start
    assert api.modules_connect_calls > connect_calls_after_start
    # Live WS parameter traffic clears the streak again.
    await ws.emit("app:modules:parameters:change", {"M1": {"P1": {"v0": {"value": 1}}}})
    assert gw._zombie_prime_streak == 0
    assert gw._zombie_hard_restart_streak == 0
    await gw.stop()


async def test_gateway_zombie_hard_restart_handles_ws_none_and_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Hard-restart path must tolerate a missing WS client and force_reconnect errors."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()

    async def _boom() -> None:
        raise RuntimeError("force failed")

    ws.force_reconnect = _boom  # type: ignore[method-assign]  # test double replaces async method
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
        stale_prime_after_s=0.05,
        zombie_hard_restart_after=1,
    )
    await gw.start()
    gw._last_live_param_publish_monotonic = 0.0
    with caplog.at_level("ERROR"):
        await _wait_until(lambda: "WS hard reconnect (zombie session) failed" in caplog.text)
    await gw.stop()

    # Controlled single-tick coverage for ``ws is None`` during hard restart.
    api2 = FakeApiClient()
    api2.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws2 = FakeRealtimeManager()
    gw2 = BragerOneGateway(
        api=api2,
        object_id=1,
        modules=["M1"],
        ws=ws2,
        connectivity_poll_interval=0,
        stale_prime_after_s=0.01,
        zombie_hard_restart_after=1,
    )
    await gw2.start()
    primes_after_start = api2.prime_params_calls
    # Cancel nothing — poll disabled. Drive one loop iteration via a short-lived task.
    gw2.ws = None
    gw2._ws_session_up = True
    gw2._zombie_prime_streak = 0
    gw2._last_live_param_publish_monotonic = 0.0
    gw2._connectivity_poll_interval = 0.01
    poll = asyncio.create_task(gw2._connectivity_poll_loop())
    try:
        with caplog.at_level("WARNING"):
            await _wait_until(lambda: "no WS client, REST-priming only" in caplog.text)
        await _wait_until(lambda: api2.prime_params_calls > primes_after_start)
    finally:
        poll.cancel()
        await asyncio.gather(poll, return_exceptions=True)
    await gw2.stop()


async def test_gateway_memory_updated_event_reprimes_module() -> None:
    """SPA EventChannel 0x16 (``22``) must REST-prime the named module."""
    from pybragerone.models.events import MODULE_MEMORY_UPDATED

    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    primes_after_start = api.prime_params_calls
    await ws.emit(MODULE_MEMORY_UPDATED, {"devid": "M1"})
    await _wait_until(lambda: api.prime_params_calls > primes_after_start)

    # Unknown / empty devid is ignored; non-dict payload is ignored.
    primes_mid = api.prime_params_calls
    await ws.emit(MODULE_MEMORY_UPDATED, {"devid": "OTHER"})
    await ws.emit(MODULE_MEMORY_UPDATED, {"devid": ""})
    await ws.emit(MODULE_MEMORY_UPDATED, {"devid": 123})
    await ws.emit(MODULE_MEMORY_UPDATED, "not-a-dict")
    await asyncio.sleep(0.05)
    assert api.prime_params_calls == primes_mid
    await gw.stop()


async def test_gateway_prime_devids_edge_and_memory_updated_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cover ``_prime_devids`` failure shapes and memory-updated exception paths."""
    from pybragerone.models.events import MODULE_MEMORY_UPDATED

    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()

    assert await gw._prime_devids(["OTHER"]) is False

    async def _bad_shape(*_a: Any, **_k: Any) -> bool:
        return False

    async def _bad_status(*_a: Any, **_k: Any) -> tuple[int, Any]:
        return 500, {"M1": {}}

    async def _non_dict_body(*_a: Any, **_k: Any) -> tuple[int, Any]:
        return 200, "not-a-dict"

    gw.api.modules_parameters_prime = _bad_shape  # type: ignore[method-assign]  # test double replaces async method
    assert await gw._prime_devids(["M1"]) is False
    gw.api.modules_parameters_prime = _bad_status  # type: ignore[method-assign]  # test double replaces async method
    assert await gw._prime_devids(["M1"]) is False
    gw.api.modules_parameters_prime = _non_dict_body  # type: ignore[method-assign]  # test double replaces async method
    assert await gw._prime_devids(["M1"]) is False

    async def _timeout_prime(*_a: Any, **_k: Any) -> tuple[int, Any]:
        raise ApiError(503, "<html>Service Unavailable</html>", {})

    async def _boom_prime(*_a: Any, **_k: Any) -> tuple[int, Any]:
        raise RuntimeError("prime exploded")

    gw.api.modules_parameters_prime = _timeout_prime  # type: ignore[method-assign]  # test double replaces async method
    with caplog.at_level("WARNING"):
        await ws.emit(MODULE_MEMORY_UPDATED, {"devid": "M1"})
        await _wait_until(lambda: "memory-updated REST prime failed (expected)" in caplog.text)

    caplog.clear()
    gw.api.modules_parameters_prime = _boom_prime  # type: ignore[method-assign]  # test double replaces async method
    with caplog.at_level("ERROR"):
        await ws.emit(MODULE_MEMORY_UPDATED, {"devid": "M1"})
        await _wait_until(lambda: "memory-updated REST prime failed for devid=M1" in caplog.text)
    await gw.stop()


async def test_gateway_zombie_uses_live_age_after_first_ws_update() -> None:
    """REST-only snapshots must not mask a dead WS push stream once live traffic existed."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
    )
    await gw.start()
    await ws.emit("app:modules:parameters:change", {"M1": {"P1": {"v0": {"value": 1}}}})
    assert gw.last_live_param_update_age_s() is not None

    stale_live_s = 500.0
    gw._last_live_param_publish_monotonic = time.monotonic() - stale_live_s
    gw._last_param_publish_monotonic = time.monotonic()
    zombie_age = gw._zombie_param_update_age_s()
    assert zombie_age is not None
    assert stale_live_s - 1.0 <= zombie_age <= stale_live_s + 1.0
    param_age = gw.last_param_update_age_s()
    assert param_age is not None
    assert param_age < 1.0
    await gw.stop()


async def test_gateway_skips_zombie_hard_restart_when_modules_offline() -> None:
    """Do not hammer WS recovery while every subscribed module is known offline."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=0, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
        stale_prime_after_s=0.05,
        zombie_hard_restart_after=1,
    )
    await gw.start()
    primes_after_start = api.prime_params_calls
    await gw._refresh_module_connectivity(source="rest")
    gw._last_live_param_publish_monotonic = 0.0
    await _wait_until(lambda: api.prime_params_calls > primes_after_start)
    assert ws.force_reconnect_calls == 0
    await gw.stop()


async def test_gateway_recycles_realtime_after_repeated_hard_restarts() -> None:
    """Escalate to full disconnect → connect → resubscribe after repeated failed hard restarts."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
        stale_prime_after_s=0.05,
        zombie_hard_restart_after=1,
        zombie_full_recycle_after=2,
        zombie_rebuild_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    assert ws.connect_calls == 1
    gw._last_live_param_publish_monotonic = 0.0
    await _wait_until(lambda: ws.force_reconnect_calls >= 2)
    await _wait_until(lambda: ws.hard_reset_calls >= 1)
    assert ws.connect_calls >= 2
    await gw.stop()


async def test_gateway_recover_zombie_session_recycles_when_hard_streak_reached() -> None:
    """Cover the recycle branch in ``_recover_zombie_session``."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_full_recycle_after=2,
        zombie_rebuild_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    gw._zombie_hard_restart_streak = 2
    await gw._recover_zombie_session(2)
    assert ws.hard_reset_calls >= 1
    assert ws.connect_calls >= 2
    await gw.stop()


async def test_gateway_recover_zombie_session_ws_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``_recover_zombie_session`` must tolerate a missing WS client."""
    api = FakeApiClient()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
    )
    await gw.start()
    gw.ws = None
    with caplog.at_level("WARNING"):
        await gw._recover_zombie_session(2)
        assert "no WS client, REST-priming only" in caplog.text
    await gw.stop()


async def test_gateway_recycle_realtime_session_ws_none() -> None:
    """``_recycle_realtime_session`` is a no-op when the WS client is missing."""
    api = FakeApiClient()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
    )
    await gw.start()
    gw.ws = None
    await gw._recycle_realtime_session(2)
    await gw.stop()


async def test_gateway_recycle_realtime_session_disconnect_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recycle must log and continue when hard_reset raises."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()

    async def _boom_hard_reset() -> None:
        raise RuntimeError("hard_reset failed")

    ws.hard_reset = _boom_hard_reset  # type: ignore[method-assign]
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    with caplog.at_level("ERROR"):
        await gw._recycle_realtime_session(2)
        assert "WS recycle (hard_reset/connect/resubscribe) failed" in caplog.text
    await gw.stop()


async def test_gateway_recycle_realtime_session_stopped_after_hard_reset() -> None:
    """Recycle must not resubscribe after the gateway stops during hard_reset."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    subscribe_calls_after_start = len(ws.subscribe_calls)

    async def _hard_reset_then_stop() -> None:
        gw._started = False

    ws.hard_reset = _hard_reset_then_stop  # type: ignore[method-assign]
    await gw._recycle_realtime_session(2)
    assert len(ws.subscribe_calls) == subscribe_calls_after_start
    await gw.stop()


async def test_gateway_recycle_realtime_session_connect_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recycle must log and continue when hard_reset/connect raises."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()

    async def _boom_hard_reset() -> None:
        raise RuntimeError("connect failed")

    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    ws.hard_reset = _boom_hard_reset  # type: ignore[method-assign]
    with caplog.at_level("ERROR"):
        await gw._recycle_realtime_session(2)
        assert "WS recycle (hard_reset/connect/resubscribe) failed" in caplog.text
    await gw.stop()


async def test_gateway_rebuilds_realtime_manager_after_repeated_recycles() -> None:
    """Owned WS clients escalate from recycle to a full RealtimeManager rebuild."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    rebuilt = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=2,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    gw._owns_ws = True
    gw._make_realtime_manager = lambda: rebuilt  # type: ignore[method-assign]
    gw._zombie_hard_restart_streak = 3
    await gw._recycle_realtime_session(2)
    assert ws.hard_reset_calls >= 1
    assert gw._zombie_recycle_streak == 1
    assert gw.ws is ws
    gw._zombie_hard_restart_streak = 3
    await gw._recycle_realtime_session(2)
    assert gw.ws is rebuilt
    assert rebuilt.connect_calls >= 1
    assert gw._ws_hooks_registered is True
    assert len(rebuilt._on_connected) >= 1
    await gw.stop()


async def test_gateway_rebuild_registers_hooks_before_failed_connect(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed rebuild connect must leave lifecycle hooks on the replacement client."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    rebuilt = FakeRealtimeManager()

    async def _boom_connect() -> None:
        raise RuntimeError("connect failed")

    rebuilt.connect = _boom_connect  # type: ignore[method-assign]
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=1,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    gw._owns_ws = True
    gw._make_realtime_manager = lambda: rebuilt  # type: ignore[method-assign]
    with caplog.at_level("ERROR"):
        await gw._rebuild_realtime_manager(2)
        assert "RealtimeManager rebuild (connect/resubscribe) failed" in caplog.text
    assert gw.ws is rebuilt
    assert gw._ws_hooks_registered is True
    assert len(rebuilt._on_connected) >= 1
    assert len(rebuilt._on_disconnected) >= 1
    await gw.stop()


async def test_gateway_zombie_recovery_cooldown_skips_ws_recovery(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """During cooldown the poll REST-primes but does not hard-reconnect or escalate."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
        stale_prime_after_s=0.05,
        zombie_hard_restart_after=1,
        zombie_recovery_cooldown_s=60,
    )
    await gw.start()
    gw._last_live_param_publish_monotonic = 0.0
    gw._zombie_prime_streak = 0
    gw._zombie_recovery_cooldown_until = time.monotonic() + 60.0
    primes_after_start = api.prime_params_calls
    await _wait_until(lambda: api.prime_params_calls > primes_after_start + 1)
    assert ws.force_reconnect_calls == 0
    assert gw._zombie_prime_streak == 0
    with caplog.at_level("DEBUG"):
        await _wait_until(lambda: "REST-priming during zombie recovery cooldown" in caplog.text)
    await gw.stop()


def test_arm_zombie_recovery_cooldown_resets_short_streaks() -> None:
    """Arming cooldown must clear prime/hard streaks so expiry does not thrash."""
    api = FakeApiClient()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
        zombie_recovery_cooldown_s=30,
    )
    gw._zombie_prime_streak = 11
    gw._zombie_hard_restart_streak = 3
    gw._zombie_recycle_streak = 2
    gw._arm_zombie_recovery_cooldown()
    assert gw._zombie_prime_streak == 0
    assert gw._zombie_hard_restart_streak == 0
    assert gw._zombie_recovery_in_cooldown() is True


async def test_gateway_resubscribe_skips_without_sid(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``resubscribe`` must warn and no-op when the namespace SID is missing."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    ws.sid = lambda: None  # type: ignore[method-assign]
    connects_after_start = api.modules_connect_calls
    with caplog.at_level("WARNING"):
        assert await gw.resubscribe() is False
        assert "no namespace SID after reconnect" in caplog.text
    assert api.modules_connect_calls == connects_after_start
    await gw.stop()


async def test_gateway_resubscribe_warns_when_modules_connect_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``resubscribe`` must WARNING-log when ``modules_connect`` returns False."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()

    async def _fail_connect(
        wsid_ns: str,
        modules: list[str],
        group_id: int | None = None,
        engine_sid: str | None = None,
    ) -> bool:
        api.modules_connect_calls += 1
        return False

    api.modules_connect = _fail_connect  # type: ignore[method-assign]
    gw._bound_ns_sid = None
    prime_before = api.prime_params_calls
    subscribe_before = len(ws.subscribe_calls)
    with caplog.at_level("WARNING"):
        assert await gw.resubscribe() is False
        assert "modules.connect (resub) failed" in caplog.text
    assert api.prime_params_calls > prime_before
    assert len(ws.subscribe_calls) == subscribe_before
    await gw.stop()


async def test_gateway_start_warns_when_modules_connect_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``start`` must WARNING-log when ``modules_connect`` returns False."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()

    async def _fail_connect(
        wsid_ns: str,
        modules: list[str],
        group_id: int | None = None,
        engine_sid: str | None = None,
    ) -> bool:
        api.modules_connect_calls += 1
        return False

    api.modules_connect = _fail_connect  # type: ignore[method-assign]
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    with caplog.at_level("WARNING"):
        await gw.start()
        assert "modules.connect failed" in caplog.text
    await gw.stop()


def test_gateway_zombie_helper_defaults() -> None:
    """Cover unknown-module-online and unset live-age helper paths."""
    api = FakeApiClient()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
    )
    assert gw._any_subscribed_module_online() is True
    assert gw.last_live_param_update_age_s() is None
    assert gw._zombie_param_update_age_s() is None


async def test_gateway_zombie_offline_skip_logs_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Offline modules should skip WS recovery but log at debug."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=0, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
        stale_prime_after_s=0.05,
        zombie_hard_restart_after=1,
    )
    await gw.start()
    await gw._refresh_module_connectivity(source="rest")
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    with caplog.at_level("DEBUG"):
        await _wait_until(lambda: "Skipping zombie WS recovery while all subscribed modules are offline" in caplog.text)
    await gw.stop()


async def test_gateway_poll_skips_prime_when_stopped_or_stale_disabled() -> None:
    """Poll must not REST-prime after stop, or when stale-prime is disabled and WS is up."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
        stale_prime_after_s=0,
    )
    await gw.start()
    primes_after_start = api.prime_params_calls
    gw._last_param_publish_monotonic = 0.0
    await asyncio.sleep(0.12)
    assert api.prime_params_calls == primes_after_start

    gw._started = False
    await asyncio.sleep(0.12)
    assert api.prime_params_calls == primes_after_start
    gw._started = True
    await gw.stop()


async def test_gateway_touch_param_publish_and_age() -> None:
    """Publishing parameter events stamps last_param_update_age_s."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    assert gw.last_param_update_age_s() is None
    gw._touch_param_publish(0)
    assert gw.last_param_update_age_s() is None
    gw._touch_param_publish(1)
    age = gw.last_param_update_age_s()
    assert age is not None
    assert age >= 0.0
    await gw.ingest_prime_parameters({"M1": {"P1": {"v0": {"value": 1}}}})
    await ws.emit("app:modules:parameters:change", {"M1": {"P1": {"v0": {"value": 2}}}})
    await ws.emit("snapshot", {"M1": {"P1": {"v0": {"value": 3}}}})
    assert gw.last_param_update_age_s() is not None
    await gw.stop()


def test_gateway_arm_zombie_recovery_cooldown_exponential() -> None:
    """Cooldown arms from base seconds and caps exponential growth."""
    gw = BragerOneGateway(
        api=FakeApiClient(),
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
        zombie_recovery_cooldown_s=10,
    )
    gw._zombie_recycle_streak = 1
    gw._arm_zombie_recovery_cooldown()
    assert gw._zombie_recovery_cooldown_until is not None
    first = gw._zombie_recovery_cooldown_until
    gw._zombie_recycle_streak = 20
    gw._arm_zombie_recovery_cooldown()
    assert gw._zombie_recovery_cooldown_until is not None
    assert gw._zombie_recovery_cooldown_until >= first


async def test_gateway_wait_for_ws_sid_retries_until_available() -> None:
    """``_wait_for_ws_sid`` polls until the namespace SID appears."""
    ws = FakeRealtimeManager()
    attempts = {"n": 0}

    def _sid() -> str | None:
        attempts["n"] += 1
        return "NS-SID" if attempts["n"] >= 3 else None

    ws.sid = _sid  # type: ignore[method-assign]
    gw = BragerOneGateway(api=FakeApiClient(), object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    assert await gw._wait_for_ws_sid(ws, timeout_s=1.0) == "NS-SID"
    assert attempts["n"] >= 3


async def test_gateway_recycle_falls_back_without_hard_reset() -> None:
    """Recycle uses disconnect/connect when ``hard_reset`` is unavailable."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    ws.hard_reset = None  # type: ignore[assignment]
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    connect_before = ws.connect_calls
    await gw._recycle_realtime_session(2)
    assert ws.disconnect_calls >= 1
    assert ws.connect_calls > connect_before
    await gw.stop()


async def test_gateway_recycle_token_refresh_failure_and_stop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recycle logs token failures and aborts when the gateway stops mid-refresh."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=0,
        zombie_recovery_cooldown_s=5,
    )
    await gw.start()

    async def _boom_token() -> str:
        raise RuntimeError("token boom")

    gw._fresh_ws_token = _boom_token  # type: ignore[method-assign]
    with caplog.at_level("ERROR"):
        await gw._recycle_realtime_session(2)
        assert "Forced fresh auth failed" in caplog.text
    assert gw._zombie_recovery_cooldown_until is not None

    async def _stop_during_token() -> str:
        gw._started = False
        return "tok"

    gw._fresh_ws_token = _stop_during_token  # type: ignore[method-assign]
    hard_before = ws.hard_reset_calls
    await gw._recycle_realtime_session(2)
    assert ws.hard_reset_calls == hard_before
    gw._started = True
    await gw.stop()


async def test_gateway_recycle_stops_after_disconnect_without_hard_reset() -> None:
    """Fallback recycle must not reconnect after stop during disconnect."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    ws.hard_reset = None  # type: ignore[assignment]
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    connect_before = ws.connect_calls

    async def _disconnect_then_stop() -> None:
        gw._started = False

    ws.disconnect = _disconnect_then_stop  # type: ignore[method-assign]
    await gw._recycle_realtime_session(2)
    assert ws.connect_calls == connect_before
    gw._started = True
    await gw.stop()


async def test_gateway_rebuild_edge_paths(caplog: pytest.LogCaptureFixture) -> None:
    """Cover rebuild early-exit, disconnect/token failures, and stop races."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=1,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    gw._owns_ws = False
    await gw._rebuild_realtime_manager(2)
    assert gw.ws is ws

    gw._owns_ws = True
    rebuilt_none = FakeRealtimeManager()
    gw._make_realtime_manager = lambda: rebuilt_none  # type: ignore[method-assign]
    gw.ws = None
    await gw._rebuild_realtime_manager(2)
    assert rebuilt_none.connect_calls >= 1
    assert gw._ws_hooks_registered is True

    gw._started = False
    await gw._rebuild_realtime_manager(2)
    gw._started = True

    async def _boom_disconnect() -> None:
        raise RuntimeError("disconnect boom")

    boom_ws = FakeRealtimeManager()
    boom_ws.disconnect = _boom_disconnect  # type: ignore[method-assign]
    gw.ws = boom_ws
    rebuilt = FakeRealtimeManager()
    gw._make_realtime_manager = lambda: rebuilt  # type: ignore[method-assign]
    with caplog.at_level("ERROR"):
        await gw._rebuild_realtime_manager(2)
        assert "WS disconnect during RealtimeManager rebuild failed" in caplog.text

    async def _disconnect_stop() -> None:
        gw._started = False

    stop_ws = FakeRealtimeManager()
    stop_ws.disconnect = _disconnect_stop  # type: ignore[method-assign]
    gw.ws = stop_ws
    await gw._rebuild_realtime_manager(2)
    assert gw._started is False
    gw._started = True

    async def _token_fail() -> str:
        raise RuntimeError("token boom")

    gw.ws = FakeRealtimeManager()
    gw._fresh_ws_token = _token_fail  # type: ignore[method-assign]
    fail_ws = gw.ws
    with caplog.at_level("ERROR"):
        await gw._rebuild_realtime_manager(2)
        assert "Forced fresh auth failed" in caplog.text
    assert fail_ws.disconnect_calls == 0
    assert gw.ws is fail_ws

    async def _token_stop() -> str:
        gw._started = False
        return "tok"

    gw.ws = FakeRealtimeManager()
    gw._fresh_ws_token = _token_stop  # type: ignore[method-assign]
    await gw._rebuild_realtime_manager(2)
    assert gw._started is False
    gw._started = True
    await gw.stop()


def test_gateway_make_realtime_manager_branches() -> None:
    """``_make_realtime_manager`` wires token providers for API clients."""
    from pybragerone.api.client import BragerOneApiClient
    from pybragerone.models.token import Token

    gw_fake = BragerOneGateway(
        api=FakeApiClient(),
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
    )
    mgr_fake = gw_fake._make_realtime_manager()
    assert mgr_fake._token == "fake-token"

    api = BragerOneApiClient(validate_on_start=False)
    api._token = Token(access_token="real-token")
    gw_real = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
    )
    mgr_real = gw_real._make_realtime_manager()
    assert mgr_real._token == "real-token"
    assert mgr_real._token_provider is not None


async def test_gateway_recovers_when_module_comes_online_during_zombie(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Module online during cooldown must clear backoff and resubscribe."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=1,
        zombie_recovery_cooldown_s=1800,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    gw._zombie_recovery_cooldown_until = time.monotonic() + 1800.0
    resub_calls = {"n": 0}

    async def _track_resubscribe() -> bool:
        resub_calls["n"] += 1
        return True

    gw.resubscribe = _track_resubscribe  # type: ignore[method-assign]
    with caplog.at_level("WARNING"):
        await gw._apply_connectivity(
            devid="M1",
            online=True,
            source="rest",
            connected_at=123,
        )
        assert "came online while zombie" in caplog.text
        assert "cleared cooldown" in caplog.text
    assert resub_calls["n"] == 1
    await gw.stop()


async def test_gateway_module_online_recovery_skips_when_auth_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cooldown-clearing module-online recovery must abort when forced re-login fails."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=1,
        zombie_recovery_cooldown_s=1800,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    gw._zombie_recovery_cooldown_until = time.monotonic() + 1800.0
    resub_calls = {"n": 0}

    async def _failed_auth() -> bool:
        return False

    async def _track_resubscribe() -> bool:
        resub_calls["n"] += 1
        return True

    gw._force_fresh_auth = _failed_auth  # type: ignore[method-assign]
    gw.resubscribe = _track_resubscribe  # type: ignore[method-assign]
    with caplog.at_level("WARNING"):
        await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=123)
        assert "Module-online recovery skipped: no usable token" in caplog.text
    assert resub_calls["n"] == 0
    assert gw._zombie_recovery_in_cooldown() is True
    await gw.stop()


async def test_gateway_module_online_recovery_rearms_cooldown_when_resubscribe_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failed resubscribe after clearing cooldown must re-arm backoff."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=1,
        zombie_recovery_cooldown_s=1800,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    gw._zombie_recovery_cooldown_until = time.monotonic() + 1800.0

    async def _ok_auth() -> bool:
        return True

    async def _boom_resubscribe() -> bool:
        raise RuntimeError("resub boom")

    gw._force_fresh_auth = _ok_auth  # type: ignore[method-assign]
    gw.resubscribe = _boom_resubscribe  # type: ignore[method-assign]
    with caplog.at_level("ERROR"):
        await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=123)
        assert "Zombie recovery after module online failed" in caplog.text
    assert gw._zombie_recovery_in_cooldown() is True
    await gw.stop()


async def test_gateway_module_online_recovery_rearms_cooldown_when_resubscribe_incomplete(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Soft resubscribe failure (False) must re-arm cooldown after clearing it."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=1,
        zombie_recovery_cooldown_s=1800,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    gw._zombie_recovery_cooldown_until = time.monotonic() + 1800.0

    async def _ok_auth() -> bool:
        return True

    async def _soft_fail_resubscribe() -> bool:
        return False

    gw._force_fresh_auth = _ok_auth  # type: ignore[method-assign]
    gw.resubscribe = _soft_fail_resubscribe  # type: ignore[method-assign]
    with caplog.at_level("WARNING"):
        await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=123)
        assert "resubscribe did not re-bind modules" in caplog.text
    assert gw._zombie_recovery_in_cooldown() is True
    await gw.stop()


async def test_gateway_module_online_recovery_skips_when_not_zombie() -> None:
    """Fresh live traffic must not trigger module-online rebuild."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
    )
    await gw.start()
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic()
    rebuild_calls = {"n": 0}

    async def _boom_rebuild(_streak: int) -> None:
        rebuild_calls["n"] += 1

    gw._rebuild_realtime_manager = _boom_rebuild  # type: ignore[method-assign,assignment]
    await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=1)
    assert rebuild_calls["n"] == 0
    await gw.stop()


async def test_gateway_force_fresh_auth_falls_back_for_fake_api() -> None:
    """Non-BragerOne API clients keep using the soft token path."""
    api = FakeApiClient()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
    )
    assert await gw._force_fresh_auth() is True


async def test_gateway_force_fresh_auth_rejects_empty_custom_token() -> None:
    """Custom ``ApiClient`` implementations must not report success without a token."""

    class _EmptyTokenApi(FakeApiClient):
        @property
        def access_token(self) -> str:
            return ""

    gw = BragerOneGateway(
        api=_EmptyTokenApi(),
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
    )
    assert await gw._force_fresh_auth() is False


@pytest.mark.asyncio
async def test_gateway_force_fresh_auth_without_creds_keeps_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Gateway recovery without creds_provider must not erase the only token."""
    from pybragerone.models.token import Token

    api = BragerOneApiClient(validate_on_start=False)
    api._token = Token(access_token="keep-me")
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
    )
    with caplog.at_level("WARNING"):
        assert await gw._force_fresh_auth() is True
        assert "no credentials available" in caplog.text
    assert api.access_token == "keep-me"
    await api.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_gateway_force_fresh_auth_invalidates_real_client(httpx_mock: HTTPXMock) -> None:
    """Real API clients must drop cached tokens during zombie recovery."""
    api = BragerOneApiClient(creds_provider=lambda: ("e@example.com", "secret"), validate_on_start=False)
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/auth/user", json={"accessToken": "T2"})
    await api.ensure_auth("e@example.com", "secret")
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=FakeRealtimeManager(),
        connectivity_poll_interval=0,
    )
    assert await gw._force_fresh_auth() is True
    await gw.stop()
    await api.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_gateway_recycle_calls_force_fresh_auth_on_real_client(httpx_mock: HTTPXMock) -> None:
    """Recycle/rebuild paths force re-login on the real HTTP client."""
    api = BragerOneApiClient(creds_provider=lambda: ("e@example.com", "secret"), validate_on_start=False)
    ws = FakeRealtimeManager()
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/auth/user", json={"accessToken": "T2"})
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/connect", status_code=204)
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/parameters", json={"M1": {}})
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/activity/quantity", status_code=204)
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/alarms/quantity", status_code=204)
    await api.ensure_auth("e@example.com", "secret")
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    await gw._recycle_realtime_session(2)
    assert api.access_token == "T2"
    await gw.stop()
    await api.close()


@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
@pytest.mark.asyncio
async def test_gateway_hard_reconnect_force_fresh_auth_on_real_client(httpx_mock: HTTPXMock) -> None:
    """Hard reconnect in ``_recover_zombie_session`` must invalidate the real HTTP client."""
    api = BragerOneApiClient(creds_provider=lambda: ("e@example.com", "secret"), validate_on_start=False)
    ws = FakeRealtimeManager()
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/auth/user", json={"accessToken": "T1"})
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/auth/user", json={"accessToken": "T2"})
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/connect", status_code=204)
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/parameters", json={"M1": {}})
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/activity/quantity", status_code=204)
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/alarms/quantity", status_code=204)
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/connect", status_code=204)
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/parameters", json={"M1": {}})
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/activity/quantity", status_code=204)
    httpx_mock.add_response(method="POST", url="https://io.brager.pl/v1/modules/alarms/quantity", status_code=204)
    await api.ensure_auth("e@example.com", "secret")
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_full_recycle_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    assert api.access_token == "T1"
    await gw._recover_zombie_session(2)
    assert ws.force_reconnect_calls >= 1
    assert api.access_token == "T2"
    await gw.stop()
    await api.close()


async def test_gateway_hard_reconnect_aborts_when_force_fresh_auth_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Hard reconnect must abort when ``_force_fresh_auth`` cannot obtain a token."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_full_recycle_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    reconnects_after_start = ws.force_reconnect_calls

    async def _failed_auth() -> bool:
        return False

    gw._force_fresh_auth = _failed_auth  # type: ignore[method-assign]
    with caplog.at_level("WARNING"):
        await gw._recover_zombie_session(2)
        assert "Aborting WS hard reconnect" in caplog.text
    assert ws.force_reconnect_calls == reconnects_after_start
    await gw.stop()


async def test_gateway_module_online_recovery_uses_recycle_path() -> None:
    """When not cooling down, module-online recovery escalates via the zombie ladder."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=0,
        zombie_full_recycle_after=1,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    recover_calls = {"n": 0}

    async def _track_recover(_streak: int) -> None:
        recover_calls["n"] += 1

    gw._recover_zombie_session = _track_recover  # type: ignore[method-assign,assignment]
    await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=1)
    assert recover_calls["n"] == 1
    await gw.stop()


async def test_gateway_module_online_recovery_resubscribe_only() -> None:
    """With recycle/rebuild disabled, module-online recovery escalates via the ladder."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=0,
        zombie_full_recycle_after=0,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    recover_calls = {"n": 0}

    async def _track_recover(_streak: int) -> None:
        recover_calls["n"] += 1

    gw._recover_zombie_session = _track_recover  # type: ignore[method-assign,assignment]
    await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=1)
    assert recover_calls["n"] == 1
    await gw.stop()


async def test_gateway_module_online_recovery_debounce_skips_second_attempt() -> None:
    """Repeated module-online signals within the debounce window are ignored."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=1,
    )
    await gw.start()
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    gw._zombie_last_module_online_recovery_monotonic = time.monotonic()
    recover_calls = {"n": 0}

    async def _track_recover(_streak: int) -> None:
        recover_calls["n"] += 1

    gw._recover_zombie_session = _track_recover  # type: ignore[method-assign,assignment]
    await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=1)
    assert recover_calls["n"] == 0
    await gw.stop()


async def test_gateway_module_online_recovery_skips_without_ws_session() -> None:
    """Module-online recovery requires an active library↔cloud session."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=1,
    )
    await gw.start()
    gw._ws_session_up = False
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    recover_calls = {"n": 0}

    async def _track_recover(_streak: int) -> None:
        recover_calls["n"] += 1

    gw._recover_zombie_session = _track_recover  # type: ignore[method-assign,assignment]
    await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=1)
    assert recover_calls["n"] == 0
    await gw.stop()


async def test_gateway_module_online_recovery_logs_without_cooldown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recovery log omits the cooldown suffix when none was active."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=1,
        zombie_recovery_cooldown_s=0,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    recover_calls = {"n": 0}

    async def _track_recover(_streak: int) -> None:
        recover_calls["n"] += 1

    gw._recover_zombie_session = _track_recover  # type: ignore[method-assign,assignment]
    with caplog.at_level("WARNING"):
        await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=1)
        assert "came online while zombie" in caplog.text
        assert "cleared cooldown" not in caplog.text
    assert recover_calls["n"] == 1
    await gw.stop()


async def test_gateway_module_online_recovery_skips_when_inflight() -> None:
    """Concurrent module-online recovery attempts must not stack."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=1,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    gw._zombie_module_online_recovery_inflight = True
    recover_calls = {"n": 0}

    async def _boom_recover(_streak: int) -> None:
        recover_calls["n"] += 1

    gw._recover_zombie_session = _boom_recover  # type: ignore[method-assign,assignment]
    await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=1)
    assert recover_calls["n"] == 0
    await gw.stop()


async def test_gateway_module_online_recovery_exception_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failures during module-online recovery must not kill connectivity polling."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_rebuild_after=1,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0

    async def _boom_recover(_streak: int) -> None:
        raise RuntimeError("recover failed")

    gw._recover_zombie_session = _boom_recover  # type: ignore[method-assign,assignment]
    with caplog.at_level("ERROR"):
        await gw._apply_connectivity(devid="M1", online=True, source="rest", connected_at=1)
        assert "Zombie recovery after module online failed" in caplog.text
    await gw.stop()


async def test_gateway_resubscribe_skips_duplicate_bind_for_same_sid() -> None:
    """Concurrent/repeat ``resubscribe`` on the same namespace SID must not re-POST connect."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    connects_after_start = api.modules_connect_calls
    first, second = await asyncio.gather(gw.resubscribe(), gw.resubscribe())
    assert first is True
    assert second is True
    assert api.modules_connect_calls == connects_after_start
    await gw.stop()


async def test_gateway_quarantine_skips_zombie_hard_reconnect(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """After the rebuild cap, WS recovery pauses; REST primes continue."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0.05,
        stale_prime_after_s=0.05,
        zombie_hard_restart_after=1,
        zombie_quarantine_after=1,
        zombie_quarantine_s=1800,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = 0.0
    gw._zombie_rebuild_count = 1
    gw._arm_zombie_quarantine()
    primes_before = api.prime_params_calls
    reconnects_before = ws.force_reconnect_calls
    await _wait_until(lambda: api.prime_params_calls > primes_before)
    await asyncio.sleep(0.12)
    assert ws.force_reconnect_calls == reconnects_before
    assert gw._zombie_recovery_in_quarantine() is True
    await ws.emit("app:modules:parameters:change", {"M1": {"P1": {"v0": {"value": 1}}}})
    assert gw._zombie_quarantine_until is None
    assert gw._zombie_rebuild_count == 0
    await gw.stop()


async def test_gateway_quarantine_disabled_when_s_zero() -> None:
    """When zombie_quarantine_s <= 0, _arm_zombie_quarantine must no-op."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_quarantine_after=1,
        zombie_quarantine_s=0,
    )
    gw._zombie_rebuild_count = 5
    gw._arm_zombie_quarantine()
    assert gw._zombie_quarantine_until is None
    await gw.stop()


async def test_gateway_rebuild_arms_quarantine_after_cap(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The Nth silent rebuild arms REST-only quarantine instead of a short cooldown."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    rebuilt = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        zombie_rebuild_after=1,
        zombie_recovery_cooldown_s=300,
        zombie_quarantine_after=1,
        zombie_quarantine_s=1800,
    )
    await gw.start()
    gw._owns_ws = True
    gw._make_realtime_manager = lambda: rebuilt  # type: ignore[method-assign]
    with caplog.at_level("WARNING"):
        await gw._rebuild_realtime_manager(2)
        assert "quarantined" in caplog.text
    assert gw._zombie_rebuild_count == 1
    assert gw._zombie_recovery_in_quarantine() is True
    assert gw._zombie_recovery_in_cooldown() is False
    await gw.stop()


async def test_gateway_module_online_clears_quarantine(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A module returning online during quarantine must resubscribe immediately."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(
        api=api,
        object_id=1,
        modules=["M1"],
        ws=ws,
        connectivity_poll_interval=0,
        stale_prime_after_s=180,
        zombie_quarantine_s=1800,
    )
    await gw.start()
    gw._owns_ws = True
    gw._ws_session_up = True
    gw._last_live_param_publish_monotonic = time.monotonic() - 500.0
    gw._zombie_rebuild_count = 3
    gw._arm_zombie_quarantine()
    resub_calls = {"n": 0}

    async def _track_resubscribe() -> bool:
        resub_calls["n"] += 1
        return True

    gw.resubscribe = _track_resubscribe  # type: ignore[method-assign]
    with caplog.at_level("WARNING"):
        await gw._apply_connectivity(
            devid="M1",
            online=True,
            source="rest",
            connected_at=123,
        )
        assert "cleared quarantine" in caplog.text
    assert resub_calls["n"] == 1
    assert gw._zombie_quarantine_until is None
    await gw.stop()
