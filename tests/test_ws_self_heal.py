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
        self.reconnect_event = asyncio.Event()

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
        self.connected = False

    async def emit(self, *args: Any, **kwargs: Any) -> None:
        """Accept emits without side effects for this test."""
        return None

    def get_sid(self, namespace: str) -> str:
        """Return deterministic namespace SID."""
        return f"NS-{namespace}"


@pytest.mark.asyncio
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
        """Initialize with a hang flag."""
        super().__init__(*args, **kwargs)
        self.hang = False

    async def connect(self, *args: Any, **kwargs: Any) -> None:
        """Hang indefinitely when the hang flag is set."""
        if self.hang:
            self.connect_calls += 1
            await asyncio.Event().wait()  # never returns
        else:
            await super().connect(*args, **kwargs)


@pytest.mark.asyncio
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
    await asyncio.sleep(0.5)
    assert fake.connect_calls >= 3
    assert manager._supervisor_task is not None and not manager._supervisor_task.done()

    await manager.disconnect()


@pytest.mark.asyncio
async def test_reconnect_uses_fresh_token_from_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each connect attempt resolves the token via the provider, so expired tokens recover."""
    fake = FakeAsyncClient()
    captured: list[str] = []

    async def _connect(*args: Any, **kwargs: Any) -> None:
        captured.append(kwargs["headers"]["Authorization"])
        await FakeAsyncClient.connect(fake, *args, **kwargs)

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


@pytest.mark.asyncio
async def test_token_provider_failure_falls_back_to_static_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the provider raises (auth backend down), the attempt still uses the last known token."""
    fake = FakeAsyncClient()
    captured: list[str] = []

    async def _connect(*args: Any, **kwargs: Any) -> None:
        captured.append(kwargs["headers"]["Authorization"])
        await FakeAsyncClient.connect(fake, *args, **kwargs)

    fake.connect = _connect  # type: ignore[method-assign]
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    async def _failing() -> str:
        raise RuntimeError("auth backend unreachable")

    manager = RealtimeManager(token="last-known", token_provider=_failing, connect_timeout_s=0.05)
    await manager.connect()

    assert captured[0] == "Bearer last-known"

    await manager.disconnect()


@pytest.mark.asyncio
async def test_supervisor_survives_unexpected_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unexpected exception in a reconnect attempt must not kill the supervisor task."""
    fake = FakeAsyncClient()

    async def _boom(*args: Any, **kwargs: Any) -> None:
        fake.connect_calls += 1
        raise RuntimeError("unexpected")

    fake.connect = _boom  # type: ignore[method-assign]
    monkeypatch.setattr("pybragerone.api.ws.socketio.AsyncClient", lambda **kwargs: fake)

    manager = RealtimeManager(token="tkn", connect_timeout_s=0.05)
    manager._supervisor_interval_s = 0.01

    # Initial connect raises; start the supervisor directly for this unit test.
    with pytest.raises(RuntimeError, match="unexpected"):
        await manager._ensure_connected(initial=True)
    manager._start_supervisor()

    await asyncio.sleep(0.2)
    assert fake.connect_calls >= 2
    assert manager._supervisor_task is not None and not manager._supervisor_task.done()

    await manager.disconnect()
