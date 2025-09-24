from __future__ import annotations

"""Module src/pybragerone/realtime/ws.py."""
import asyncio
import logging
from collections.abc import Callable
from typing import Any

import socketio

IO_BASE = "https://io.brager.pl"
SOCK_PATH = "/socket.io"
WS_NAMESPACE = "/ws"

LOG = logging.getLogger("pybragerone.ws")
EventHandler = Callable[[str, Any], None]


class RealtimeManager:
    """Wzorowane na Twojej działającej implementacji:
    - autoryzacja tylko przez headers (Authorization/Origin/Referer)
    - SID bierzemy z namespace (`get_sid('/ws')`)
    - słuchamy *zmian* (`…:change`) + `snapshot`
    - listen wysyłamy w kilku wariantach payloadu (modules/devids + opcjonalnie group_id)
    """
    def __init__(self, token: str,
                 origin: str = "https://one.brager.pl",
                 referer: str = "https://one.brager.pl/"):
        """Init  .
    
        Args:
        token: TODO.
        origin: TODO.
        referer: TODO.

        Returns:
        TODO.
        """
        self._token = token
        self._origin = origin
        self._referer = referer
        self._sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=1.0,
            reconnection_delay_max=10.0,
        )
        self._connected = asyncio.Event()
        self._on_event: EventHandler | None = None
        self._modules: list[str] = []
        self._group_id: int | None = None

        @self._sio.event(namespace=WS_NAMESPACE)
        async def connect():
            """Connect.
    
            Returns:
            TODO.
            """
            ns_sid = self.sid()
            eng_sid = self.engine_sid()
            LOG.info("WS connected, SID=%s", eng_sid)
            LOG.info("WS connected, namespace_sid=%s, engine_sid=%s, namespaces=%s",
                     ns_sid, eng_sid, list(self._sio.namespaces))
            self._connected.set()

        @self._sio.event(namespace=WS_NAMESPACE)
        async def disconnect():
            """Disconnect.
    
            Returns:
            TODO.
            """
            LOG.info("WS disconnected")
            self._connected.clear()

        @self._sio.event
        async def connect_error(data=None):
            """Connect error.
    
            Args:
            data: TODO.

            Returns:
            TODO.
            """
            LOG.warning("WS connect_error: %s", data)

        @self._sio.on("error", namespace=WS_NAMESPACE)
        async def on_error(data):
            """On error.
    
            Args:
            data: TODO.

            Returns:
            TODO.
            """
            LOG.error("WS ERROR: %s", data)

        @self._sio.on("message", namespace=WS_NAMESPACE)
        async def on_message(data):
            """On message.
    
            Args:
            data: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS message → %s", data)

        # --- KLUCZOWE HANDLERY, jak w Twojej wersji ---
        @self._sio.on("snapshot", namespace=WS_NAMESPACE)
        async def on_snapshot(payload):
            """On snapshot.
    
            Args:
            payload: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT snapshot → %s", payload)
            self._dispatch("snapshot", payload)

        @self._sio.on("app:modules:parameters:change", namespace=WS_NAMESPACE)
        async def on_params_change(payload):
            """On params change.
    
            Args:
            payload: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT app:modules:parameters:change → %s", payload)
            self._dispatch("app:modules:parameters:change", payload)

        @self._sio.on("modules:parameters:change", namespace=WS_NAMESPACE)
        async def on_params_change2(payload):
            """On params change2.
    
            Args:
            payload: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT modules:parameters:change → %s", payload)
            self._dispatch("modules:parameters:change", payload)

        @self._sio.on("parameters:change", namespace=WS_NAMESPACE)
        async def on_params_change3(payload):
            """On params change3.
    
            Args:
            payload: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT parameters:change → %s", payload)
            self._dispatch("parameters:change", payload)

        # opcjonalnie taski — bywa, że lecą numerami
        @self._sio.on("app:module:task:created", namespace=WS_NAMESPACE)
        async def on_task_created(p):
            """On task created.
    
            Args:
            p: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT app:module:task:created → %s", p)
            self._dispatch("app:module:task:created", p)

        @self._sio.on("app:module:task:status:changed", namespace=WS_NAMESPACE)
        async def on_task_status(p):
            """On task status.
    
            Args:
            p: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT app:module:task:status:changed → %s", p)
            self._dispatch("app:module:task:status:changed", p)

        @self._sio.on("app:module:task:completed", namespace=WS_NAMESPACE)
        async def on_task_done(p):
            """On task done.
    
            Args:
            p: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT app:module:task:completed → %s", p)
            self._dispatch("app:module:task:completed", p)

        @self._sio.on("60", namespace=WS_NAMESPACE)
        async def _ev60(p):
            """ev60.
    
            Args:
            p: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT 60 → %s", p)
            self._dispatch("app:module:task:status:changed", p)

        @self._sio.on("61", namespace=WS_NAMESPACE)
        async def _ev61(p):
            """ev61.
    
            Args:
            p: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT 61 → %s", p)
            self._dispatch("app:module:task:created", p)

        @self._sio.on("63", namespace=WS_NAMESPACE)
        async def _ev63(p):
            """ev63.
    
            Args:
            p: TODO.

            Returns:
            TODO.
            """
            LOG.debug("WS EVENT 63 → %s", p)
            self._dispatch("app:module:task:completed", p)

    def _dispatch(self, name: str, payload: Any):
        """Dispatch.
    
        Args:
        name: TODO.
        payload: TODO.

        Returns:
        TODO.
        """
        if self._on_event:
            try:
                self._on_event(name, payload)
            except Exception:
                LOG.exception("Błąd w callbacku _on_event(%s)", name)

    async def connect(self):
        """Connect.
    
        Returns:
        TODO.
        """
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Origin": self._origin,
            "Referer": self._referer,
            "Accept-Language": "pl-PL,pl;q=0.9",
            "x-appversion": "1.1.78",
        }
        await self._sio.connect(
            IO_BASE,
            headers=headers,
            transports=["websocket"],
            socketio_path=SOCK_PATH,
            namespaces=[WS_NAMESPACE],
        )
        # krótki lag zanim namespace w pełni "siądzie"
        await self._connected.wait()
        await asyncio.sleep(0.1)

    def sid(self) -> str | None:
        """Sid.
    
        Returns:
        TODO.
        """
        try:
            return self._sio.get_sid(WS_NAMESPACE)  # SID namespace'u /ws
        except Exception:
            return None

    def engine_sid(self) -> str | None:
        """Engine sid.
    
        Returns:
        TODO.
        """
        return getattr(self._sio, "sid", None)  # engine.io sid

    async def disconnect(self):
        """Disconnect.
    
        Returns:
        TODO.
        """
        if self._sio.connected:
            await self._sio.disconnect()

    def on_event(self, handler: EventHandler):
        """On event.
    
        Args:
        handler: TODO.

        Returns:
        TODO.
        """
        self._on_event = handler

    def set_group(self, group_id: int | None):
        """Set group.
    
        Args:
        group_id: TODO.

        Returns:
        TODO.
        """
        self._group_id = group_id

    async def subscribe(self, modules: list[str]):
        """Subscribe.
    
        Args:
        modules: TODO.

        Returns:
        TODO.
        """
        self._modules = sorted(set(modules))
        if not self._modules:
            return
        payloads = []
        base = {"modules": self._modules}
        base_alt = {"devids": self._modules}       # fallback — spotykany wariant
        if self._group_id is not None:
            base = {**base, "group_id": self._group_id}
            base_alt = {**base_alt, "group_id": self._group_id}

        payloads.append(("app:modules:parameters:listen", base))
        payloads.append(("app:modules:parameters:listen", base_alt))
        payloads.append(("app:modules:activity:quantity:listen", base))
        payloads.append(("app:modules:activity:quantity:listen", base_alt))

        for ev, pl in payloads:
            LOG.debug("EMIT %s %s", ev, pl)
            try:
                await self._sio.emit(ev, pl, namespace=WS_NAMESPACE)
            except Exception:
                LOG.exception("Emit failed for %s", ev)

    async def resubscribe(self):
        """Resubscribe.
    
        Returns:
        TODO.
        """
        if self._modules:
            await self.subscribe(self._modules)
