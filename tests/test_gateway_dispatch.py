"""Tests for gateway dispatch, flatten, lifecycle, and callbacks."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import pytest

from pybragerone.gateway import BragerOneGateway
from pybragerone.models.events import ParamUpdate


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
        payload: dict[str, Any] = {"DEV1": {"P4": {"v1": {"value": 123}}}}
        return 200, payload

    async def modules_activity_quantity_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Return a minimal activity prime payload."""
        self._prime_activity_calls.append(list(modules))
        if not return_data:
            return True
        return 200, {"activityQuantity": {}}

    async def close(self) -> None:
        """Mark the client as closed."""
        self.closed = True


class FakeRealtimeManager:
    """Fake WS manager implementing the gateway's realtime surface."""

    def __init__(self, *, sid: str | None = "NS-SID", engine_sid: str = "ENG-SID") -> None:
        """Initialize the fake realtime manager."""
        self._sid = sid
        self._engine_sid = engine_sid
        self._on_connected: list[Callable[[], Awaitable[None] | None]] = []
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

    def sid(self) -> str | None:
        """Return a namespace SID."""
        return self._sid

    def engine_sid(self) -> str | None:
        """Return an engine SID."""
        return self._engine_sid

    async def subscribe(self, modules: Iterable[str]) -> None:
        """Record a subscribe call."""
        self.subscribe_calls.append(list(modules))


def _gateway(
    *, sid: str | None = "NS-SID", owns_api: bool = False
) -> tuple[BragerOneGateway, FakeApiClient, FakeRealtimeManager]:
    """Build a gateway with fakes."""
    api = FakeApiClient()
    ws = FakeRealtimeManager(sid=sid)
    gw = BragerOneGateway(api=api, object_id=123, modules=["M1"], ws=ws, owns_api=owns_api)
    return gw, api, ws


def test_flatten_parameters_skips_invalid_shapes_and_keeps_meta() -> None:
    """Flatten skips non-dicts and short keys, and preserves extra body fields as meta."""
    gw, _, _ = _gateway()
    updates = gw.flatten_parameters(
        {
            "SKIP": "not-a-dict",
            "DEV2": {
                "P4": "not-entries",
                "P5": {
                    "x": 1,
                    "vX": 1,
                    "v1": 42,
                    "v2": {"value": 7, "unit": 1},
                },
            },
        },
        source="unit",
    )

    by_idx = {upd.idx: upd for upd in updates}
    assert set(by_idx) == {1, 2}
    assert by_idx[1].devid == "DEV2"
    assert by_idx[1].pool == "P5"
    assert by_idx[1].chan == "v"
    assert by_idx[1].value == 42
    assert by_idx[1].meta["_source"] == "unit"
    assert by_idx[2].value == 7
    assert by_idx[2].meta["unit"] == 1


@pytest.mark.asyncio
async def test_start_is_idempotent_and_wait_for_prime() -> None:
    """A second ``start`` is a no-op; prime wait returns True after start and False on timeout."""
    gw, _, ws = _gateway()
    assert await gw.wait_for_prime(timeout=0.01) is False
    await gw.start()
    await gw.start()
    assert ws.connect_calls == 1
    assert await gw.wait_for_prime(timeout=0.01) is True
    await gw.stop()


@pytest.mark.asyncio
async def test_stop_closes_owned_api_and_context_manager_stops() -> None:
    """``owns_api`` closes the HTTP client; async context manager starts and stops."""
    gw, api, ws = _gateway(owns_api=True)
    await gw.start()
    await gw.stop()
    assert api.closed is True
    assert ws.disconnect_calls == 1

    api2 = FakeApiClient()
    ws2 = FakeRealtimeManager()
    async with BragerOneGateway(api=api2, object_id=123, modules=["M1"], ws=ws2) as started:
        assert started is not None
        assert ws2.connect_calls == 1
    assert ws2.disconnect_calls == 1


@pytest.mark.asyncio
async def test_resubscribe_returns_early_without_ws_or_sid() -> None:
    """Resubscribe is a no-op when WS is missing or the namespace SID is empty."""
    gw, api, _ = _gateway()
    gw.ws = None
    await gw.resubscribe()
    assert api._modules_connect_calls == []

    gw2, api2, _ = _gateway(sid=None)
    await gw2.resubscribe()
    assert api2._modules_connect_calls == []


@pytest.mark.asyncio
async def test_ws_dispatch_publishes_snapshot_and_parameter_change() -> None:
    """Snapshot and ``parameters:change`` events flatten into bus updates and callbacks."""
    gw, _, _ = _gateway()
    await gw.start()

    snapshot_got = asyncio.Event()
    change_got = asyncio.Event()
    any_names: list[str] = []

    def on_any(name: str, _payload: object) -> None:
        """Record diagnostic event names."""
        any_names.append(name)

    async def on_snapshot(_payload: dict[str, Any]) -> None:
        """Mark snapshot callback completion."""
        snapshot_got.set()

    def on_change(_name: str, _payload: dict[str, Any]) -> None:
        """Mark parameter-change callback completion."""
        change_got.set()

    gw.on_any(on_any)
    gw.on_snapshot(on_snapshot)
    gw.on_parameters_change(on_change)

    bus = gw.bus.subscribe()
    try:
        gw._ws_dispatch("snapshot", {"DEV1": {"P4": {"v1": {"value": 5}}}})
        snap = await asyncio.wait_for(bus.__anext__(), timeout=1.0)
        assert isinstance(snap, ParamUpdate)
        assert snap.value == 5
        assert snap.meta["_source"] == "snapshot"
        await asyncio.wait_for(snapshot_got.wait(), timeout=1.0)

        gw._ws_dispatch("app:modules:parameters:change", {"DEV1": {"P4": {"v2": 9}}})
        change = await asyncio.wait_for(bus.__anext__(), timeout=1.0)
        assert change.idx == 2
        assert change.value == 9
        assert change.meta["_source"] == "ws"
        await asyncio.wait_for(change_got.wait(), timeout=1.0)
    finally:
        await bus.aclose()
        await gw.stop()

    assert "snapshot" in any_names
    assert "app:modules:parameters:change" in any_names


@pytest.mark.asyncio
async def test_ws_dispatch_continues_after_callback_error() -> None:
    """A raising ``on_any`` callback does not prevent later callbacks from running."""
    gw, _, _ = _gateway()
    await gw.start()
    done = asyncio.Event()

    def boom(_name: str, _payload: object) -> None:
        """Raise to exercise callback error handling."""
        raise RuntimeError("boom")

    def ok(_name: str, _payload: object) -> None:
        """Signal that invocation continued after the failure."""
        done.set()

    gw.on_any(boom)
    gw.on_any(ok)
    gw._ws_dispatch("diagnostic", {"ok": True})
    await asyncio.wait_for(done.wait(), timeout=1.0)
    await gw.stop()


@pytest.mark.asyncio
async def test_background_task_failure_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Spawned background tasks log exceptions instead of dying silently."""
    gw, _, _ = _gateway()

    async def fail() -> None:
        """Fail on purpose so the task finalizer logs it."""
        raise RuntimeError("spawn-fail")

    with caplog.at_level("ERROR"):
        task = gw._spawn(fail(), name="gateway.test_fail")
        result = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(result[0], RuntimeError)
    assert any("Background task failed" in rec.message for rec in caplog.records)
    await gw.stop()
