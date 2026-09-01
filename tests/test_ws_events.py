"""Tests for RealtimeManager event dispatch and subscribe emits."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pybragerone.api.ws import RealtimeManager
from pybragerone.models.events import MODULE_MEMORY_UPDATED
from pybragerone.utils import bg_tasks


class _FakeSio:
    """Minimal AsyncClient stub that records emits and handlers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize disconnected socket state."""
        self.connected = False
        self.namespaces: list[str] = []
        self.sid: str | None = "ENG-SID"
        self._handlers: dict[tuple[str, str], Any] = {}
        self.emits: list[tuple[str, Any]] = []
        self.emit_error = False
        self.sid_error = False

    def on(self, event: str, handler: Any, namespace: str) -> None:
        """Register an event handler."""
        self._handlers[(namespace, event)] = handler

    async def connect(self, *args: Any, **kwargs: Any) -> None:
        """Mark connected and invoke the connect handler."""
        self.connected = True
        namespace = kwargs.get("namespaces", ["/ws"])[0]
        self.namespaces = [namespace]
        handler = self._handlers.get((namespace, "connect"))
        if handler is not None:
            await handler()

    async def disconnect(self) -> None:
        """Mark disconnected."""
        self.connected = False

    async def emit(self, event: str, payload: Any, namespace: str | None = None) -> None:
        """Record an emit or raise when ``emit_error`` is set."""
        del namespace
        if self.emit_error:
            raise RuntimeError("emit failed")
        self.emits.append((event, payload))

    def get_sid(self, namespace: str) -> str:
        """Return a namespace SID, or raise when ``sid_error`` is set."""
        if self.sid_error:
            raise RuntimeError("no sid")
        return f"NS-{namespace}"


async def _drain_spawned() -> None:
    """Yield until ``spawn()`` callbacks finish; fail if tasks leak."""
    for _ in range(50):
        if not bg_tasks:
            return
        await asyncio.sleep(0)
    remaining = list(bg_tasks)
    for task in remaining:
        task.cancel()
    if remaining:
        await asyncio.wait(set(remaining))
    raise AssertionError(f"background tasks did not finish: {remaining!r}")


def _manager(monkeypatch: pytest.MonkeyPatch) -> tuple[RealtimeManager, _FakeSio]:
    """Build a RealtimeManager backed by ``_FakeSio``."""
    fake = _FakeSio()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)
    return RealtimeManager(token="tkn"), fake


async def test_domain_handlers_dispatch_and_survive_callback_errors(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Snapshot/parameter/task handlers forward to on_event; callback errors are logged."""
    manager, _fake = _manager(monkeypatch)

    class _Recorder:
        def __init__(self) -> None:
            self.seen: list[tuple[str, Any]] = []

        def __call__(self, event_name: str, payload: Any) -> None:
            self.seen.append((event_name, payload))
            if event_name == "snapshot":
                raise RuntimeError("callback failed")

    recorder = _Recorder()
    manager.on_event(recorder)
    with caplog.at_level("ERROR"):
        await manager._on_snapshot({"k": 1})
        await manager._on_app_modules_parameters_change({"k": 2})
        await manager._on_modules_parameters_change({"k": 3})
        await manager._on_parameters_change({"k": 4})
        await manager._on_app_modules_task_created({"k": 5})
        await manager._on_app_modules_task_status_changed({"k": 6})
        await manager._on_app_modules_task_completed({"k": 7})
        await manager._on_app_module_connection_status_changed({"M1": {"connectedAt": 1}})
        await manager._on_module_memory_updated({"devid": "M1"})
        await manager._on_ev60({"k": 8})
        await manager._on_ev61({"k": 9})
        await manager._on_ev63({"k": 10})

    names = [name for name, _payload in recorder.seen]
    assert names == [
        "snapshot",
        "app:modules:parameters:change",
        "modules:parameters:change",
        "parameters:change",
        "app:module:task:created",
        "app:module:task:status:changed",
        "app:module:task:completed",
        "app:module:connection:status:changed",
        MODULE_MEMORY_UPDATED,
        "app:module:task:status:changed",
        "app:module:task:created",
        "app:module:task:completed",
    ]
    assert "callback failed" in caplog.text


async def test_lifecycle_handlers_and_connect_callbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connect runs sync/async callbacks; lifecycle handlers do not raise."""
    manager, fake = _manager(monkeypatch)
    calls: list[str] = []

    def _sync() -> None:
        calls.append("sync")

    async def _async() -> None:
        calls.append("async")

    def _boom() -> None:
        raise RuntimeError("connect-cb")

    manager.add_on_connected(_sync)
    manager.add_on_connected(_async)
    manager.add_on_connected(_boom)

    await manager._on_connect()
    await _drain_spawned()
    assert "sync" in calls
    assert "async" in calls
    assert manager._connected.is_set()

    disc: list[str] = []

    def _disc() -> None:
        disc.append("disc")

    async def _disc_async() -> None:
        disc.append("disc-async")

    manager.add_on_disconnected(_disc)
    manager.add_on_disconnected(_disc_async)
    manager.add_on_disconnected(_boom)

    await manager._on_connect_error("nope")
    assert not manager._connected.is_set()
    # connect_error after connect: was_connected True → disconnect callbacks
    await _drain_spawned()
    assert "disc" in disc
    assert "disc-async" in disc

    disc.clear()
    # connect_error while already disconnected does not re-fire disconnect callbacks
    await manager._on_connect_error("still-down")
    await _drain_spawned()
    assert disc == []

    disc.clear()
    await manager._on_disconnect()
    await _drain_spawned()
    assert disc == []
    await manager._on_reconnect()
    await manager._on_reconnect_attempt(2)
    await manager._on_reconnect_error("err")
    await manager._on_error("err")
    await manager._on_message("hi")

    fake.sid_error = True
    assert manager.sid() is None
    assert manager.engine_sid() == "ENG-SID"


async def test_subscribe_emits_variants_and_skips_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subscribe is a no-op for no modules and emits listen variants with group_id."""
    manager, fake = _manager(monkeypatch)
    await manager.subscribe([])
    assert fake.emits == []

    manager.group_id = 9
    await manager.subscribe(["M2", "M1", "M1"])
    events = [event for event, _payload in fake.emits]
    assert events == [
        "app:modules:parameters:listen",
        "app:modules:parameters:listen",
        "app:modules:activity:quantity:listen",
        "app:modules:activity:quantity:listen",
        "app:modules:alarms:quantity:listen",
        "app:modules:alarms:quantity:listen",
    ]
    assert fake.emits[0][1] == {"modules": ["M1", "M2"], "group_id": 9}
    assert fake.emits[1][1] == {"devids": ["M1", "M2"], "group_id": 9}

    fake.emits.clear()
    await manager.resubscribe()
    assert fake.emits


async def test_subscribe_logs_emit_failures(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """A failed emit is logged and does not abort the remaining listen variants."""
    manager, fake = _manager(monkeypatch)
    fake.emit_error = True
    with caplog.at_level("ERROR"):
        await manager.subscribe(["M1"])
    assert "Emit failed" in caplog.text
