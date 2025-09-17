from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from logging import Logger
from typing import Any

from socketio import AsyncClient

from .const import IO_BASE, ONE_BASE
from .const import WS_NAMESPACE as NS


class WsClient:
    """
    Thin Socket.IO wrapper responsible only for:
      - connecting/disconnecting,
      - (re)subscribing,
      - forwarding incoming messages to provided callbacks.

    Gateway handles REST 'modules.connect' and business logic.
    """

    def __init__(self, token_getter: Callable[[], str | None], logger=None):
        self._get_token: str = token_getter
        self.log: Logger = logger
        self.sio: AsyncClient | None = None
        self._on_change: Callable[[dict], None] | None = None
        self._on_event: Callable[[str, Any], None] | None = None

    # ---- public API ----

    def set_change_handler(self, cb: Callable[[dict], None]) -> None:
        """Called with payloads of parameters changes."""
        self._on_change = cb

    def set_event_handler(self, cb: Callable[[str, Any], None]) -> None:
        """Called for generic events (debug/log use)."""
        self._on_event = cb

    async def connect(self) -> str:
        """Open WS to /ws namespace with Bearer token."""
        if self.sio is None:
            self.sio = AsyncClient(reconnection=True)
            self._wire()

        token = self._get_token() or ""
        headers = {
            "Authorization": f"Bearer {token}",
            "Origin": ONE_BASE,
            "Referer": f"{ONE_BASE}/",
        }

        # Connect to base host; python-socketio handles upgrade internally.
        await self.sio.connect(
            IO_BASE,  # keep https; engine does WS upgrade itself
            headers=headers,
            transports=["websocket"],
            socketio_path="/socket.io",
            namespaces=[NS],
        )

        sid = self.sid()
        if self.log:
            self.log.info("WS connected %s", NS)
        return sid or ""

    async def subscribe(self, devs: list[str]) -> None:
        """Subscribe to parameter & activity streams."""
        if not self.sio:
            return
        await self.sio.emit("app:modules:parameters:listen", {"modules": devs}, namespace=NS)
        if self.log:
            self.log.debug("[emit] app:modules:parameters:listen %s ns=%s", {"modules": devs}, NS)

        await self.sio.emit("app:modules:activity:quantity:listen", {"modules": devs}, namespace=NS)
        if self.log:
            self.log.debug(
                "[emit] app:modules:activity:quantity:listen %s ns=%s", {"modules": devs}, NS
            )

    async def close(self) -> None:
        """Gracefully close the socket (idempotent)."""
        try:
            if self.sio:
                await self.sio.disconnect()
                if self.log:
                    self.log.info("WS disconnected %s", NS)
        finally:
            self.sio = None

    def sid(self) -> str | None:
        """Return namespace SID if available, fallback to engine SID."""
        if not self.sio:
            return None
        try:
            ns_sid = self.sio.get_sid(NS)
        except Exception:
            ns_sid = None
        return ns_sid or getattr(self.sio, "sid", None)

    # ---- internals ----

    def _fire_event(self, name: str, data: Any) -> None:
        if self._on_event:
            with contextlib.suppress(Exception):
                self._on_event(name, data)

    def _fire_change(self, payload: dict) -> None:
        if self._on_change:
            with contextlib.suppress(Exception):
                self._on_change(payload)

    def _wire(self) -> None:
        sio = self.sio
        assert sio is not None

        @sio.on("connect", namespace=NS)
        async def _on_connect() -> None:
            if self.log:
                self.log.debug("[ws] connected")
            self._fire_event("socket.connect", {"ns": NS})

        @sio.on("disconnect", namespace=NS)
        async def _on_disconnect() -> None:
            if self.log:
                self.log.debug("[ws] disconnected")
            self._fire_event("socket.disconnect", {"ns": NS})

        @sio.event
        async def connect_error(data) -> None:
            # Engine-level connect error has no namespace
            if self.log:
                self.log.warning("WS connect_error: %s", data)
            self._fire_event("socket.connect_error", data)

        # Parameter changes (multiple aliases seen in the wild)
        @sio.on("app:modules:parameters:change", namespace=NS)
        async def _change1(payload) -> None:
            self._fire_change(payload)

        @sio.on("modules:parameters:change", namespace=NS)
        async def _change2(payload) -> None:
            self._fire_change(payload)

        @sio.on("parameters:change", namespace=NS)
        async def _change3(payload) -> None:
            self._fire_change(payload)

        # Optional snapshot push
        @sio.on("snapshot", namespace=NS)
        async def _snapshot(payload) -> None:
            try:
                txt = json.dumps(payload, ensure_ascii=False)
            except Exception:
                txt = repr(payload)
            self._fire_event("snapshot", txt)

        # Catch-all for debugging (namespaced)
        @sio.on("*", namespace=NS)
        async def _any(event, data=None) -> None:
            self._fire_event(event, data)

        # --- module task lifecycle (optional pretty logs) ---
        @sio.on("app:module:task:created", namespace=NS)
        async def _task_created(payload) -> None:
            self._fire_event("app:module:task:created", payload)

        @sio.on("app:module:task:status:changed", namespace=NS)
        async def _task_status(payload) -> None:
            self._fire_event("app:module:task:status:changed", payload)

        @sio.on("app:module:task:completed", namespace=NS)
        async def _task_done(payload) -> None:
            self._fire_event("app:module:task:completed", payload)

        # (spotykane czasem numeryczne aliasy)
        @sio.on("60", namespace=NS)
        async def _ev60(payload) -> None:
            self._fire_event("app:module:task:status:changed", payload)

        @sio.on("61", namespace=NS)
        async def _ev61(payload) -> None:
            self._fire_event("app:module:task:created", payload)

        @sio.on("63", namespace=NS)
        async def _ev63(payload) -> None:
            self._fire_event("app:module:task:completed", payload)
