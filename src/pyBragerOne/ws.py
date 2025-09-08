from __future__ import annotations
import socketio
from typing import Any, Callable, Optional

BASE_IO = "https://io.brager.pl"
SOCK_PATH = "/socket.io"
ORIGIN = "https://one.brager.pl"
REFERER = "https://one.brager.pl/"
NS = "/ws"

class WsClient:
    def __init__(self, token_getter):
        """
        token_getter: funkcja bezargumentowa zwracająca aktualny JWT (str)
        """
        self.sio: Optional[socketio.AsyncClient] = None
        self._get_token = token_getter
        self.wsid: Optional[str] = None
        self.on_event: list[Callable[[str, Any], None]] = []
        self.on_change: list[Callable[[dict], None]] = []

    # --- API callbacków ---
    def add_event_cb(self, cb: Callable[[str, Any], None]) -> None:
        self.on_event.append(cb)

    def add_change_cb(self, cb: Callable[[dict], None]) -> None:
        self.on_change.append(cb)

    # --- wewnętrzne emitery do callbacków ---
    def _emit_event(self, name: str, data: Any):
        for cb in list(self.on_event):
            try:
                cb(name, data)
            except Exception:
                pass

    def _emit_change(self, payload: dict):
        for cb in list(self.on_change):
            try:
                cb(payload)
            except Exception:
                pass

    # --- połączenie ---
    async def connect(self):
        """
        Łączy z io.brager.pl na namespace /ws.
        Uwierzytelnia przez nagłówek Authorization: Bearer <jwt>.
        NIE wymusza 'websocket' — pozwalamy libce dobrać transport (bez 400).
        """
        if self.sio is None:
            self.sio = socketio.AsyncClient(
                reconnection=True,
                request_timeout=20,
            )
            self._wire()

        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Origin": ORIGIN,
            "Referer": REFERER,
        }

        await self.sio.connect(
            BASE_IO,                 # baza: https://io.brager.pl
            namespaces=[NS],         # od razu /ws
            socketio_path=SOCK_PATH  # /socket.io
            # bez transports=[] i bez auth=...
        )

        # SID z namespaca /ws (jeśli dostępny), inaczej engine SID
        try:
            ns_sid = self.sio.get_sid(NS)
        except Exception:
            ns_sid = None
        self.wsid = ns_sid or getattr(self.sio, "sid", None)
        return self.wsid

    async def disconnect(self):
        if self.sio:
            await self.sio.disconnect()

    async def subscribe(self, devs: list[str], group_id: int | None = None):
        """
        Subskrypcje zdarzeń parametrów i aktywności. Dodajemy group_id gdy jest.
        """
        if not self.sio:
            return
        payload = {"modules": devs}
        if group_id is not None:
            payload["group_id"] = group_id

        await self.sio.emit("app:modules:parameters:listen", payload, namespace=NS)
        await self.sio.emit("app:modules:activity:quantity:listen", payload, namespace=NS)

        # Opcjonalnie jednorazowy snapshot z WS (nie zawsze potrzebny):
        await self.sio.emit("app:modules:parameters:snapshot", devs, namespace=NS)

    async def bind_modules(self, api, object_id: int, devs: list[str]) -> bool:
        """
        Powiązanie sesji WS z modułami po stronie REST (to co mamy w client.py).
        """
        if not self.wsid:
            return False
        try:
            return await api.modules_connect(self.wsid, devs, object_id=object_id)
        except Exception:
            return False

    # --- rejestracja handlerów ---
    def _wire(self):
        sio = self.sio

        # Połączenie / rozłączenie na namespacu /ws
        @sio.event(namespace=NS)
        async def connect():
            self._emit_event("socket.connect", {"ns": NS})

        @sio.event(namespace=NS)
        async def disconnect():
            self._emit_event("socket.disconnect", {"ns": NS})

        # Błąd połączenia (czasem backend wyrzuca)
        @sio.event
        async def connect_error(err):
            self._emit_event("socket.connect_error", err)

        # Zmiana parametrów – główny kanał
        @sio.on("app:modules:parameters:change", namespace=NS)
        async def _pc(payload):
            if isinstance(payload, dict):
                self._emit_change(payload)
            else:
                self._emit_event("app:modules:parameters:change(raw)", payload)

        # Dodatkowe aliasy (niektóre backendy używają skróconych nazw)
        sio.on("modules:parameters:change", namespace=NS)(_pc)
        sio.on("parameters:change", namespace=NS)(_pc)

        # Ilości aktywności – przekazujemy do event_cb
        @sio.on("app:modules:activity:quantity", namespace=NS)
        async def _aq(payload):
            self._emit_event("app:modules:activity:quantity", payload)
