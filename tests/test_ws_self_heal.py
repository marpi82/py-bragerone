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

    def on(self, event: str, handler: Any, namespace: str) -> None:
        """Register an event handler under namespace/event key."""
        self._handlers[(namespace, event)] = handler

    async def connect(self, *args: Any, **kwargs: Any) -> None:
        """Simulate a successful socket connect and emit connect callback."""
        self.connect_calls += 1
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

    await asyncio.sleep(0.05)
    assert fake.connect_calls >= 2

    await manager.disconnect()
