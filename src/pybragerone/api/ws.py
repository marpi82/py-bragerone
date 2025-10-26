"""WebSocket (Socket.IO) client for BragerOne realtime events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import (
    Any,
    Protocol,
    TypedDict,
    runtime_checkable,
)

import socketio  # type: ignore[import-untyped]

from ..utils import spawn
from .constants import IO_BASE, ONE_BASE, SOCK_PATH, WS_NAMESPACE

log = logging.getLogger(__name__)
sio_log = logging.getLogger(__name__ + ".sio")
eio_log = logging.getLogger(__name__ + ".eio")


# Signature for a generic event handler used by the gateway.
EventHandler = Callable[[str, Any], None]
# Signature for a callback invoked on connection establishment.
ConnectedCb = Callable[[], None | Awaitable[None]]


@runtime_checkable
class EventDispatcher(Protocol):
    """Protocol for an event dispatcher used by the realtime manager."""

    def __call__(self, event_name: str, payload: Any) -> None | Awaitable[None]:
        """Handle an event with the given name and payload.

        Args:
            event_name: The event name.
            payload: The event payload (varies by event).
        """
        ...


class _SubPayload(TypedDict, total=False):
    """Payload for subscription events."""

    modules: list[str]
    devids: list[str]
    group_id: int


class RealtimeManager:
    """Thin Socket.IO wrapper for BragerOne realtime channel.

    The manager keeps a single AsyncClient connection, exposes the Engine.IO
    SID and the namespace SID, and forwards selected events to a user-provided
    callback (``EventHandler``). It does **not** interpret payloads; that is the
    gateway's responsibility.

    Notes:
        - Authentication is provided **only** via HTTP headers (Bearer token).
        - We always connect to the `:data:`~.constants.WS_NAMESPACE`` namespace.
        - We listen to: ``snapshot`` and the various ``*:parameters:change`` events.
        - Subscriptions are emitted in a few payload variants (``modules`` /
          ``devids``) and optionally include ``group_id``.
    """

    def __init__(
        self,
        token: str,
        *,
        origin: str = ONE_BASE,
        referer: str = f"{ONE_BASE}/",
        io_base: str = IO_BASE,
        socket_path: str = SOCK_PATH,
        namespace: str = WS_NAMESPACE,
    ) -> None:
        """Initialize the realtime manager.

        Args:
            token: Bearer token used for the initial Socket.IO HTTP upgrade.
            origin: HTTP ``Origin`` header value (default: :data:`~.constants.ONE_BASE`).
            referer: HTTP ``Referer`` header value (default: :data:`~.constants.ONE_BASE` + ``/``).
            io_base: Base URL of the Engine.IO/Socket.IO server (default: :data:`~.constants.IO_BASE`).
            socket_path: Socket.IO path on the server (default: :data:`~.constants.SOCK_PATH`).
            namespace: The namespace to join (default: :data:`~.constants.WS_NAMESPACE`).
        """
        self._token = token
        self._origin = origin
        self._referer = referer
        self._io_base = io_base.rstrip("/")
        self._socket_path = socket_path
        self._namespace = namespace

        self._connected = asyncio.Event()
        self._on_connected: list[ConnectedCb] = []
        self._on_event: EventDispatcher | None = None
        self._modules: list[str] = []
        self._group_id: int | None = None

        # Configure AsyncClient with reconnection enabled.
        self._sio: socketio.AsyncClient = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0,  # infinite
            reconnection_delay=1,
            reconnection_delay_max=10,
            logger=sio_log,  # pyright: ignore[reportArgumentType] # route socket.io logs to a sub-logger
            engineio_logger=eio_log,  # route engine.io logs to a sub-logger
        )

        ns = self._namespace
        # Register built-in event handlers.
        self._sio.on("connect", self._on_connect, namespace=ns)
        self._sio.on("disconnect", self._on_disconnect, namespace=ns)
        self._sio.on("connect_error", self._on_connect_error, namespace=ns)
        self._sio.on("reconnect", self._on_reconnect, namespace=ns)
        self._sio.on("reconnect_attempt", self._on_reconnect_attempt, namespace=ns)
        self._sio.on("reconnect_error", self._on_reconnect_error, namespace=ns)
        self._sio.on("error", self._on_error, namespace=ns)
        self._sio.on("message", self._on_message, namespace=ns)
        # Register key domain event handlers.
        self._sio.on("snapshot", self._on_snapshot, namespace=ns)
        self._sio.on(
            "app:modules:parameters:change",
            self._on_app_modules_parameters_change,
            namespace=ns,
        )
        self._sio.on(
            "modules:parameters:change",  # fallback alt name
            self._on_modules_parameters_change,
            namespace=ns,
        )
        self._sio.on(
            "parameters:change",
            self._on_parameters_change,
            namespace=ns,
        )
        self._sio.on(
            "app:module:task:created",
            self._on_app_modules_task_created,
            namespace=ns,
        )
        self._sio.on(
            "app:module:task:status:changed",
            self._on_app_modules_task_status_changed,
            namespace=ns,
        )
        self._sio.on(
            "app:module:task:completed",
            self._on_app_modules_task_completed,
            namespace=ns,
        )
        # Numeric fallbacks observed in some builds
        self._sio.on("60", self._on_ev60, namespace=ns)
        self._sio.on("61", self._on_ev61, namespace=ns)
        self._sio.on("63", self._on_ev63, namespace=ns)

    # ---- Built-in handlers ----
    async def _on_connect(self) -> None:
        ns_sid = self.sid()
        eng_sid = self.engine_sid()
        log.info("WS connected, SID=%s", eng_sid)
        log.info(
            "WS connected, namespace_sid=%s, engine_sid=%s, namespaces=%s",
            ns_sid,
            eng_sid,
            list(self._sio.namespaces),
        )
        for cb in list(self._on_connected):
            try:
                res = cb()
                if asyncio.iscoroutine(res):
                    spawn(res, "on_connected_cb", log)
            except Exception:
                log.exception("Error in on_connected callback")

        self._connected.set()

    async def _on_disconnect(self) -> None:
        log.info("WS disconnected")
        self._connected.clear()

    async def _on_connect_error(self, data: Any | None = None) -> None:
        log.warning("WS connect_error: %s", data)

    async def _on_reconnect(self) -> None:
        log.info("WS reconnect OK")

    async def _on_reconnect_attempt(self, number: int) -> None:
        log.info("WS reconnect attempt #%s", number)

    async def _on_reconnect_error(self, data: Any | None = None) -> None:
        log.warning("WS reconnect_error: %s", data)

    async def _on_error(self, data: Any) -> None:
        log.error("WS ERROR: %s", data)

    async def _on_message(self, data: Any) -> None:
        log.debug("WS message → %s", data)

    # --- Key domain events ---
    async def _on_snapshot(self, payload: Any) -> None:
        log.debug("WS EVENT snapshot → %s", payload)
        self._dispatch("snapshot", payload)

    async def _on_app_modules_parameters_change(self, payload: Any) -> None:
        log.debug("WS EVENT app:modules:parameters:change → %s", payload)
        self._dispatch("app:modules:parameters:change", payload)

    # Fallback alt names occasionally seen in traces
    async def _on_modules_parameters_change(self, payload: Any) -> None:
        log.debug("WS EVENT modules:parameters:change → %s", payload)
        self._dispatch("modules:parameters:change", payload)

    async def _on_parameters_change(self, payload: Any) -> None:
        log.debug("WS EVENT parameters:change → %s", payload)
        self._dispatch("parameters:change", payload)

    # Optional task-related events; kept for completeness/diagnostics.
    async def _on_app_modules_task_created(self, p: Any) -> None:
        log.debug("WS EVENT app:module:task:created → %s", p)
        self._dispatch("app:module:task:created", p)

    async def _on_app_modules_task_status_changed(self, p: Any) -> None:
        log.debug("WS EVENT app:module:task:status:changed → %s", p)
        self._dispatch("app:module:task:status:changed", p)

    async def _on_app_modules_task_completed(self, p: Any) -> None:
        log.debug("WS EVENT app:module:task:completed → %s", p)
        self._dispatch("app:module:task:completed", p)

    # Numeric fallbacks observed in some builds
    async def _on_ev60(self, p: Any) -> None:
        log.debug("WS EVENT 60 → %s", p)
        self._dispatch("app:module:task:status:changed", p)

    async def _on_ev61(self, p: Any) -> None:
        log.debug("WS EVENT 61 → %s", p)
        self._dispatch("app:module:task:created", p)

    async def _on_ev63(self, p: Any) -> None:
        log.debug("WS EVENT 63 → %s", p)
        self._dispatch("app:module:task:completed", p)

    # ---------------- Public API ----------------

    async def connect(self) -> None:
        """Open a Socket.IO connection with appropriate headers and wait for join."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Origin": self._origin,
            "Referer": self._referer,
            "Accept-Language": "pl-PL,pl;q=0.9",
            "x-appversion": "1.1.78",
        }
        await self._sio.connect(
            self._io_base,
            headers=headers,
            transports=["pooling", "websocket"],
            socketio_path=self._socket_path,
            namespaces=[self._namespace],
        )
        # Short grace period to ensure the namespace is fully established
        await self._connected.wait()
        await asyncio.sleep(0.1)

    def sid(self) -> str | None:
        """Return the namespace SID (``/ws``), if available."""
        try:
            return str(self._sio.get_sid(self._namespace))
        except Exception:
            return None

    def engine_sid(self) -> str | None:
        """Return the underlying Engine.IO SID (transport-level)."""
        return getattr(self._sio, "sid", None)

    async def disconnect(self) -> None:
        """Close the Socket.IO connection if open."""
        if self._sio.connected:
            await self._sio.disconnect()

    def on_event(self, handler: EventDispatcher) -> None:
        """Register a single event dispatcher (gateway attaches here)."""
        self._on_event = handler

    def add_on_connected(self, cb: ConnectedCb) -> None:
        """Register a callback to be called when the connection is established."""
        self._on_connected.append(cb)

    @property
    def group_id(self) -> int | None:
        """Return the optional ``group_id`` included in subscription payloads."""
        return self._group_id

    @group_id.setter
    def group_id(self, group_id: int | None) -> None:
        """Set an optional ``group_id`` to be included in subscription payloads."""
        self._group_id = group_id

    async def subscribe(self, modules: list[str]) -> None:
        """Emit listen events for the provided devices (devids/modules)."""
        self._modules = sorted(set(modules))
        if not self._modules:
            return

        # Base variants: "modules" and alt. "devids"
        base: _SubPayload = {"modules": self._modules}
        base_alt: _SubPayload = {"devids": self._modules}

        # Optionally include "group_id"
        if self.group_id is not None:
            base["group_id"] = self.group_id
            base_alt["group_id"] = self.group_id

        payloads: list[tuple[str, _SubPayload]] = [
            ("app:modules:parameters:listen", base),
            ("app:modules:parameters:listen", base_alt),
            ("app:modules:activity:quantity:listen", base),
            ("app:modules:activity:quantity:listen", base_alt),
        ]

        for ev, pl in payloads:
            log.debug("EMIT %s %s", ev, pl)
            try:
                await self._sio.emit(ev, pl, namespace=self._namespace)
            except Exception:
                log.exception("Emit failed for %s", ev)

    async def resubscribe(self) -> None:
        """Re-emit subscription events after a reconnect."""
        if self._modules:
            await self.subscribe(self._modules)

    # ---------------- Internal ----------------

    def _dispatch(self, name: str, payload: Any) -> None:
        """Forward an event to the registered dispatcher (if any)."""
        if self._on_event:
            try:
                self._on_event(name, payload)
            except Exception:
                log.exception("Error in on_event(%s) callback", name)
