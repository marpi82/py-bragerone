"""Tests for gateway per-module cloud connectivity signals."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterable
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ReadTimeout, TimeoutException

from pybragerone.api.client import ApiError
from pybragerone.gateway import (
    ApiClient,
    BragerOneGateway,
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


@pytest.mark.asyncio
async def test_protocol_stubs_raise_not_implemented() -> None:
    """Protocol default bodies exist so structural typing stays explicit."""

    class _Probe:
        pass

    probe = _Probe()
    with pytest.raises(NotImplementedError):
        await ApiClient.get_modules(probe, 1)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        RealtimeManagerClient.add_on_disconnected(probe, lambda: None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        await RealtimeManagerClient.force_reconnect(probe)  # type: ignore[arg-type]


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

    async def _boom_resubscribe() -> None:
        raise RuntimeError("resubscribe failed")

    gw.resubscribe = _boom_resubscribe  # type: ignore[method-assign]
    await gw._on_ws_connected()
    assert gw.ws_session_up() is True

    tick_hits = 0

    async def _boom_refresh(*, source: str) -> None:
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
async def test_gateway_reconnect_skips_stale_generation_refresh() -> None:
    """A reconnect finally block must not refresh after a newer disconnect generation."""
    api = FakeApiClient()
    api.module_rows = [SimpleNamespace(devid="M1", connectedAt=50, gateway=None)]
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    calls_before = api.get_modules_calls

    async def _slow_resubscribe() -> None:
        await gw._on_ws_disconnected()
        return None

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
    )
    await gw.start()
    assert ws.connect_calls == 1
    gw._last_live_param_publish_monotonic = 0.0
    await _wait_until(lambda: ws.force_reconnect_calls >= 2)
    await _wait_until(lambda: ws.disconnect_calls >= 1)
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
    )
    await gw.start()
    gw._zombie_hard_restart_streak = 2
    await gw._recover_zombie_session(2)
    assert ws.disconnect_calls >= 1
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
    """Recycle must log and continue when disconnect raises."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()

    async def _boom_disconnect() -> None:
        raise RuntimeError("disconnect failed")

    ws.disconnect = _boom_disconnect  # type: ignore[method-assign]
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    with caplog.at_level("ERROR"):
        await gw._recycle_realtime_session(2)
        assert "WS disconnect during realtime recycle failed" in caplog.text
    await gw.stop()


async def test_gateway_recycle_realtime_session_stopped_after_disconnect() -> None:
    """Recycle must not reconnect after the gateway stops during disconnect."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()
    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    connect_calls_after_start = ws.connect_calls

    async def _disconnect_then_stop() -> None:
        gw._started = False

    ws.disconnect = _disconnect_then_stop  # type: ignore[method-assign]
    await gw._recycle_realtime_session(2)
    assert ws.connect_calls == connect_calls_after_start
    await gw.stop()


async def test_gateway_recycle_realtime_session_connect_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recycle must log and continue when connect raises."""
    api = FakeApiClient()
    ws = FakeRealtimeManager()

    async def _boom_connect() -> None:
        raise RuntimeError("connect failed")

    gw = BragerOneGateway(api=api, object_id=1, modules=["M1"], ws=ws, connectivity_poll_interval=0)
    await gw.start()
    ws.connect = _boom_connect  # type: ignore[method-assign]
    with caplog.at_level("ERROR"):
        await gw._recycle_realtime_session(2)
        assert "WS recycle (connect/resubscribe) failed" in caplog.text
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
