"""Tests for websocket self-healing behavior in RealtimeManager."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pybragerone.api.ws import RealtimeManager


class FakeAsyncClient:
    """Minimal AsyncClient stub used by RealtimeManager tests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize fake socket state and event handlers."""
        self.connected = False
        self.namespaces: list[str] = []
        self.sid: str | None = "ENG-SID"
        self._handlers: dict[tuple[str, str], Any] = {}
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.reconnect_event = asyncio.Event()
        self.eio: Any = None

    def on(self, event: str, handler: Any, namespace: str) -> None:
        """Register an event handler under namespace/event key."""
        self._handlers[(namespace, event)] = handler

    async def connect(self, *args: Any, **kwargs: Any) -> None:
        """Simulate a successful socket connect and emit connect callback."""
        self.connect_calls += 1
        if self.connect_calls > 1:
            self.reconnect_event.set()
        self.connected = True
        namespace = kwargs.get("namespaces", ["/ws"])[0]
        self.namespaces = [namespace]
        handler = self._handlers.get((namespace, "connect"))
        if handler is not None:
            await handler()

    async def disconnect(self) -> None:
        """Simulate socket disconnect."""
        self.disconnect_calls += 1
        self.connected = False

    async def emit(self, *args: Any, **kwargs: Any) -> None:
        """Accept emits without side effects for this test."""
        return None

    def get_sid(self, namespace: str) -> str:
        """Return deterministic namespace SID."""
        return f"NS-{namespace}"


async def test_realtime_manager_forces_reconnect_when_disconnected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supervisor should reconnect if client remains disconnected."""
    fake = FakeAsyncClient()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    manager = RealtimeManager(token="tkn")
    manager._supervisor_interval_s = 0.01

    await manager.connect()
    assert fake.connect_calls == 1

    fake.connected = False
    await manager._on_disconnect()

    await asyncio.wait_for(fake.reconnect_event.wait(), timeout=1.0)
    assert fake.connect_calls >= 2

    await manager.disconnect()


class HangingAsyncClient(FakeAsyncClient):
    """Fake whose connect hangs forever once `hang` is set (simulates stuck DNS/TCP)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize with a hang flag and an event to synchronize on hang attempts."""
        super().__init__(*args, **kwargs)
        self.hang = False
        self.hang_calls = 0
        self.third_hang = asyncio.Event()

    async def connect(self, *args: Any, **kwargs: Any) -> None:
        """Hang indefinitely when the hang flag is set."""
        if self.hang:
            self.connect_calls += 1
            self.hang_calls += 1
            if self.hang_calls >= 3:
                self.third_hang.set()
            await asyncio.Event().wait()  # never returns
        else:
            await super().connect(*args, **kwargs)


async def test_supervisor_survives_hung_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hung connect attempt must be aborted by the timeout and retried, not wedge the supervisor."""
    fake = HangingAsyncClient()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)
    manager._supervisor_interval_s = 0.01

    await manager.connect()
    assert fake.connect_calls == 1

    fake.hang = True
    fake.connected = False
    await manager._on_disconnect()

    # The supervisor must keep timing out and retrying instead of hanging inside connect().
    await asyncio.wait_for(fake.third_hang.wait(), timeout=1.0)
    assert manager._supervisor_task is not None and not manager._supervisor_task.done()

    await manager.disconnect()


async def test_reconnect_uses_fresh_token_from_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each connect attempt resolves the token via the provider, so expired tokens recover."""
    fake = FakeAsyncClient()
    captured: list[str] = []

    async def _connect(*args: Any, **kwargs: Any) -> None:
        captured.append(kwargs["headers"]["Authorization"])
        await FakeAsyncClient.connect(fake, *args, **kwargs)

    # method-assign: the fake instance needs per-call header capture; FakeAsyncClient has no hook for it
    fake.connect = _connect  # type: ignore[method-assign]
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    counter = 0

    async def _provider() -> str:
        nonlocal counter
        counter += 1
        return f"fresh-{counter}"

    manager = RealtimeManager(token="stale", token_provider=_provider, connect_timeout_s=0.05)
    manager._supervisor_interval_s = 0.01

    await manager.connect()
    fake.connected = False
    await manager._on_disconnect()
    await asyncio.wait_for(fake.reconnect_event.wait(), timeout=1.0)

    assert captured[0] == "Bearer fresh-1"
    assert captured[-1] != "Bearer stale"
    assert counter >= 2

    await manager.disconnect()


async def test_token_provider_failure_falls_back_to_static_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the provider raises (auth backend down), the attempt still uses the last known token."""
    fake = FakeAsyncClient()
    captured: list[str] = []

    async def _connect(*args: Any, **kwargs: Any) -> None:
        captured.append(kwargs["headers"]["Authorization"])
        await FakeAsyncClient.connect(fake, *args, **kwargs)

    # method-assign: the fake instance needs per-call header capture; FakeAsyncClient has no hook for it
    fake.connect = _connect  # type: ignore[method-assign]
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    async def _failing() -> str:
        raise RuntimeError("auth backend unreachable")

    manager = RealtimeManager(token="last-known", token_provider=_failing, connect_timeout_s=0.05)
    await manager.connect()

    assert captured[0] == "Bearer last-known"

    await manager.disconnect()


async def test_supervisor_survives_unexpected_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """An exception escaping _ensure_connected must not kill the supervisor task."""
    fake = FakeAsyncClient()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)
    manager._supervisor_interval_s = 0.01

    # Force the disconnected path, then make _ensure_connected itself blow up —
    # this bypasses its internal except-Exception and hits the supervisor guard.
    attempts = 0
    survived = asyncio.Event()

    async def _exploding(*args: Any, **kwargs: Any) -> None:
        nonlocal attempts
        attempts += 1
        if attempts >= 2:
            survived.set()  # second iteration means the guard caught the first explosion
        raise RuntimeError("guard me")

    # method-assign: the guard is only exercised when _ensure_connected itself raises
    manager._ensure_connected = _exploding  # type: ignore[method-assign]

    manager._start_supervisor()

    await asyncio.wait_for(survived.wait(), timeout=1.0)
    assert manager._supervisor_task is not None and not manager._supervisor_task.done()

    await manager.disconnect()


async def test_hanging_token_provider_falls_back_to_static_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stalled token provider must not wedge the supervisor — fall back to the last known token."""
    fake = FakeAsyncClient()
    captured: list[str] = []

    async def _connect(*args: Any, **kwargs: Any) -> None:
        captured.append(kwargs["headers"]["Authorization"])
        await FakeAsyncClient.connect(fake, *args, **kwargs)

    # method-assign: the fake instance needs per-call header capture; FakeAsyncClient has no hook for it
    fake.connect = _connect  # type: ignore[method-assign]
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    async def _hanging() -> str:
        await asyncio.Event().wait()  # never returns
        return "unreachable"

    manager = RealtimeManager(token="last-known", token_provider=_hanging, connect_timeout_s=0.05)
    await asyncio.wait_for(manager.connect(), timeout=1.0)

    assert captured[0] == "Bearer last-known"

    await manager.disconnect()


class ZombieAfterTimeoutClient(FakeAsyncClient):
    """Fake that leaves ``connected=True`` when connect times out (Engine.IO leftover)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize with a fail-next flag."""
        super().__init__(*args, **kwargs)
        self.fail_next = False
        self.reset_after_timeout = asyncio.Event()

    async def connect(self, *args: Any, **kwargs: Any) -> None:
        """Succeed, or set connected and raise TimeoutError like a cancelled handshake."""
        if self.fail_next:
            self.connect_calls += 1
            self.connected = True
            raise TimeoutError("simulated connect timeout")
        await super().connect(*args, **kwargs)

    async def disconnect(self) -> None:
        """Record leftover teardown after a timed-out connect."""
        was_connected = self.connected
        await super().disconnect()
        if was_connected and self.connect_calls >= 2:
            self.reset_after_timeout.set()


async def test_timed_out_connect_resets_leftover_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connect timeout must disconnect leftover ``connected=True`` before the next retry."""
    fake = ZombieAfterTimeoutClient()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)
    manager._supervisor_interval_s = 0.01

    await manager.connect()
    fake.fail_next = True
    fake.connected = False
    await manager._on_disconnect()

    await asyncio.wait_for(fake.reset_after_timeout.wait(), timeout=1.0)
    leftover_cleared = fake.connected
    assert leftover_cleared is False
    assert fake.disconnect_calls >= 2

    fake.fail_next = False
    await asyncio.wait_for(fake.reconnect_event.wait(), timeout=1.0)
    assert fake.connected is True

    await manager.disconnect()


class HangingDisconnectClient(FakeAsyncClient):
    """Fake whose disconnect hangs forever (Engine.IO read/write deadlock after abort)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize hang tracking."""
        super().__init__(*args, **kwargs)
        self.disconnect_started = asyncio.Event()

    async def disconnect(self) -> None:
        """Block until cancelled, simulating a wedged Engine.IO teardown."""
        self.disconnect_calls += 1
        self.disconnect_started.set()
        await asyncio.Event().wait()


async def test_supervisor_notifies_disconnect_when_engineio_aborts_without_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Engine.IO abort that skips Socket.IO disconnect must still notify session-down."""
    fake = FakeAsyncClient()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)
    manager._supervisor_interval_s = 0.01
    notified = asyncio.Event()
    manager.add_on_disconnected(notified.set)

    await manager.connect()
    assert fake.connect_calls == 1
    # Abort path: transport looks dead, but ``_on_disconnect`` never ran.
    fake.connected = False
    manager._connected.clear()

    await asyncio.wait_for(notified.wait(), timeout=1.0)
    await asyncio.wait_for(fake.reconnect_event.wait(), timeout=1.0)
    assert fake.connect_calls >= 2

    await manager.disconnect()


async def test_hanging_disconnect_is_replaced_so_supervisor_can_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deadlocked ``disconnect()`` must not wedge reconnect; replace the client."""
    clients: list[FakeAsyncClient] = []

    def _factory(**kwargs: Any) -> FakeAsyncClient:
        del kwargs
        if not clients:
            first = HangingDisconnectClient()
            clients.append(first)
            return first
        nxt = FakeAsyncClient()
        clients.append(nxt)
        return nxt

    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", _factory)

    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)
    manager._supervisor_interval_s = 0.01
    notified = asyncio.Event()
    manager.add_on_disconnected(notified.set)

    await manager.connect()
    first = clients[0]
    assert isinstance(first, HangingDisconnectClient)
    first.connected = False
    manager._connected.clear()

    await asyncio.wait_for(notified.wait(), timeout=1.0)
    await asyncio.wait_for(first.disconnect_started.wait(), timeout=1.0)
    await asyncio.wait_for(_wait_for_reconnect(clients), timeout=1.0)
    assert len(clients) >= 2
    assert clients[-1].connect_calls >= 1
    assert manager._sio is clients[-1]

    await manager.disconnect()


async def _wait_for_reconnect(clients: list[FakeAsyncClient]) -> None:
    """Spin until a replacement client has connected."""
    while True:
        if len(clients) >= 2 and clients[-1].connect_calls >= 1:
            return
        await asyncio.sleep(0)


class RaisingDisconnectClient(FakeAsyncClient):
    """Fake whose disconnect raises, forcing a client replace."""

    async def disconnect(self) -> None:
        """Raise instead of closing cleanly."""
        self.disconnect_calls += 1
        raise RuntimeError("teardown exploded")


async def test_failed_disconnect_replaces_client_and_reconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    """A raising ``disconnect()`` must replace the client so reconnect can proceed."""
    clients: list[FakeAsyncClient] = []

    def _factory(**kwargs: Any) -> FakeAsyncClient:
        del kwargs
        if not clients:
            first = RaisingDisconnectClient()
            clients.append(first)
            return first
        nxt = FakeAsyncClient()
        clients.append(nxt)
        return nxt

    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", _factory)

    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)
    manager._supervisor_interval_s = 0.01

    await manager.connect()
    clients[0].connected = False
    manager._connected.clear()

    await asyncio.wait_for(_wait_for_reconnect(clients), timeout=1.0)
    assert len(clients) >= 2
    await manager.disconnect()


class _FakeEio:
    """Minimal Engine.IO stub used when abandoning a wedged client."""

    def __init__(self) -> None:
        """Track abort disconnect calls."""
        self.abort_calls = 0

    async def disconnect(self, abort: bool = False) -> None:
        """Record an abort-style disconnect."""
        if abort:
            self.abort_calls += 1


class EioAbortClient(FakeAsyncClient):
    """Fake that exposes an Engine.IO ``disconnect(abort=True)`` hook."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Attach a stub Engine.IO client."""
        super().__init__(*args, **kwargs)
        self.eio = _FakeEio()


async def test_replace_client_aborts_leftover_engineio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replacing a hung transport should fire Engine.IO disconnect(abort=True)."""
    fake = EioAbortClient()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)
    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)
    manager._replace_client()
    await asyncio.sleep(0)
    assert fake.eio.abort_calls == 1
    await manager.disconnect()


async def test_abandon_client_and_notify_edge_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Abandon/notify helpers must swallow leftover-client failures and skip duplicate notifies."""
    fake = FakeAsyncClient()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)
    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)

    manager._abandon_client(fake)  # no eio

    class _NoDisconnect:
        """Engine.IO stub without a disconnect method."""

    fake.eio = _NoDisconnect()
    manager._abandon_client(fake)

    class _SyncOk:
        def disconnect(self, abort: bool = False) -> None:
            _ = abort

    fake.eio = _SyncOk()
    manager._abandon_client(fake)

    class _NoAbortKwarg:
        def disconnect(self) -> None:
            return None

    fake.eio = _NoAbortKwarg()
    manager._abandon_client(fake)

    class _TypeThenBoom:
        def disconnect(self, *args: Any, **kwargs: Any) -> None:
            if kwargs.get("abort"):
                raise TypeError("abort not supported")
            raise RuntimeError("fallback failed")

    fake.eio = _TypeThenBoom()
    manager._abandon_client(fake)

    class _BoomAbort:
        def disconnect(self, abort: bool = False) -> None:
            _ = abort
            raise RuntimeError("abort exploded")

    fake.eio = _BoomAbort()
    manager._abandon_client(fake)

    calls: list[int] = []
    manager.add_on_disconnected(lambda: calls.append(1))
    manager._disconnect_notified = True
    manager._notify_disconnected()
    assert calls == []
    manager._notify_disconnected(force=True)
    assert calls == [1]
    await manager.disconnect()


def test_disconnect_timeout_is_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero/huge connect timeouts must not produce a non-positive disconnect wait."""
    fake = FakeAsyncClient()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)
    too_small = RealtimeManager(token="tkn", connect_timeout_s=0)
    assert too_small._disconnect_timeout_s == 0.05
    too_large = RealtimeManager(token="tkn", connect_timeout_s=30)
    assert too_large._disconnect_timeout_s == 5.0


async def test_supervisor_reconnect_503_is_warn_only(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Expected upstream 503 during reconnect must not attach full exc_info."""
    from pybragerone.api.client import ApiError

    class _FailThenOk(FakeAsyncClient):
        async def connect(self, *args: Any, **kwargs: Any) -> None:
            next_call = self.connect_calls + 1
            if next_call == 2:
                self.connect_calls = next_call
                raise ApiError(503, "<html>Service Unavailable</html>", {})
            await super().connect(*args, **kwargs)

    fake = _FailThenOk()
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)
    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)
    manager._supervisor_interval_s = 0.01
    await manager.connect()

    with caplog.at_level("WARNING"):
        fake.connected = False
        await manager._on_disconnect()
        await asyncio.wait_for(fake.reconnect_event.wait(), timeout=1.0)

    assert any("expected upstream/transient" in record.getMessage() for record in caplog.records)
    assert not any(record.exc_info for record in caplog.records if "reconnect failed" in record.getMessage())
    await manager.disconnect()
