# ws.py
from __future__ import annotations
import socketio
from typing import Any, Callable, Optional

from .const import IO_BASE, ONE_BASE, WS_NAMESPACE

SOCK_PATH = "/socket.io"

class WsClient:
    def __init__(self, api, logger=None):
        self.api = api
        self.log = logger
        self.sio: Optional[socketio.AsyncClient] = None
        self._ws_sid: Optional[str] = None
        self._ns: str = WS_NAMESPACE
        self._on_event: list[Callable[[str, Any], None]] = []
        self._on_change: list[Callable[[dict], None]] = []

    # --- kompatybilność: używa tego Gateway ---
    @property
    def wsid(self) -> Optional[str]:
        return self.get_sid()

    def get_sid(self) -> Optional[str]:
        if self._ws_sid:
            return self._ws_sid
        if self.sio:
            try:
                sid_ns = self.sio.get_sid(self._ns)
            except Exception:
                sid_ns = None
            return sid_ns or getattr(self.sio, "sid", None)
        return None

    # --- callbacki opcjonalne (jeśli ich używasz gdzie indziej) ---
    def add_event_cb(self, cb): self._on_event.append(cb)
    def add_change_cb(self, cb): self._on_change.append(cb)

    def _emit_event(self, name: str, data: Any):
        for cb in list(self._on_event):
            try: cb(name, data)
            except Exception: pass

    def _emit_change(self, payload: dict):
        for cb in list(self._on_change):
            try: cb(payload)
            except Exception: pass

    def _wire_handlers(self, namespace: str):
        sio = self.sio

        @sio.on("connect", namespace=namespace)
        async def _on_conn():
            if self.log:
                self.log.info("WS connected %s", namespace)
            self._emit_event("socket.connect", {"ns": namespace})

        @sio.on("disconnect", namespace=namespace)
        async def _on_disc():
            if self.log:
                self.log.info("WS disconnected %s", namespace)
            self._emit_event("socket.disconnect", {"ns": namespace})

        @sio.event
        async def connect_error(err):
            if self.log:
                self.log.warning("WS connect_error: %s", err)
            self._emit_event("socket.connect_error", err)

        @sio.on("app:modules:parameters:change", namespace=namespace)
        async def _on_params_change(payload):
            self._emit_change(payload)

        @sio.on("app:modules:activity:quantity", namespace=namespace)
        async def _on_act_qty(payload):
            self._emit_event("app:modules:activity:quantity", payload)

    async def start_ws(self, jwt: str, namespace: str | None = None) -> None:
        ns = namespace or self._ns
        self._ns = ns
        if self.sio is None:
            self.sio = socketio.AsyncClient(reconnection=True)
            self._wire_handlers(ns)

        headers = {
            "Authorization": f"Bearer {jwt}",
            "Origin": ONE_BASE,
            "Referer": f"{ONE_BASE}/",
        }
        await self.sio.connect(
            IO_BASE,                      # python-socketio sam zrobi upgrade do WS
            namespaces=[ns],
            transports=["websocket"],
            socketio_path=SOCK_PATH,
            headers=headers,
        )
        # zapamiętaj SID (zarówno namespacowy jak i engine.io fallback)
        try:
            sid_ns = self.sio.get_sid(ns)
        except Exception:
            sid_ns = None
        self._ws_sid = sid_ns or getattr(self.sio, "sid", None)

    async def subscribe(self, devs: list[str], namespace: str | None = None) -> None:
        if not self.sio:
            return
        ns = namespace or self._ns
        await self.sio.emit("app:modules:parameters:listen", {"modules": devs}, namespace=ns)
        await self.sio.emit("app:modules:activity:quantity:listen", {"modules": devs}, namespace=ns)

    async def wait(self) -> None:
        if self.sio:
            await self.sio.wait()

    async def disconnect(self) -> None:
        if self.sio:
            await self.sio.disconnect()
            self._ws_sid = None

