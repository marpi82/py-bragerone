from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, Dict, Optional, List

import socketio

from .api import Api
from .labels import LabelFetcher

# --- BASE URLS & CONSTS ---
IO_BASE   = "https://io.brager.pl"     # API + login + WS
ONE_BASE  = "https://one.brager.pl"    # assety frontendu (etykiety)
API_BASE  = f"{IO_BASE}/v1"
WS_NS     = "/ws"                       # namespace socket.io
SOCK_PATH = "/socket.io"                # ścieżka socket.io


class BragerOneClient:
    def __init__(self, email: str, password: str, object_id: int, lang: str = "pl"):
        self.email = email
        self.password = password
        self.object_id = object_id
        self.lang = lang

        self.log = logging.getLogger("BragerOne")

        self.api = Api()
        # Nie wymuszamy transports=["websocket"] — lib sam zrobi negotiation + upgrade.
        self.sio = socketio.AsyncClient(reconnection=True, request_timeout=20)

        self.jwt: Optional[str] = None
        self.devid: Optional[str] = None
        self.devids: List[str] = []

        # etykiety + stan
        self.labels = LabelFetcher(base_url=ONE_BASE, http_get=self._http_get)  # SEE labels.py
        self._state: Dict[str, Any] = {}  # P?.v? -> value

        # rejestrujemy handlery WS
        self._register_ws_handlers()

    # --------------- lifecycle ---------------
    async def close(self):
        try:
            await self.sio.disconnect()
        except Exception:
            pass
        await self.api.close()

    async def _http_get(self, url: str) -> str:
        # GET dla LabelFetcher-a
        return await self.api._req("GET", url)

    # --------------- REST ---------------
    async def login(self):
        # Api.login ustawia też self.api.jwt
        _ = await self.api.login(self.email, self.password)
        self.jwt = self.api.jwt
        self.log.info("Login OK")

    async def pick_modules(self):
        mods = await self.api.list_modules(self.object_id)
        ids = [m.get("devid") or m.get("device_id") or m.get("id") for m in (mods or [])]
        ids = [str(d) for d in ids if d]
        if not ids:
            raise RuntimeError("Brak modułów dla tego obiektu")
        self.devids = ids
        self.devid = ids[0]
        self.log.info("Modules: %s", ids)

    # --------------- LABELS ---------------
    async def _bootstrap_labels(self):
        try:
            await self.labels.bootstrap(lang=self.lang)
            self.log.debug("[labels] bootstrap ok")
        except Exception as e:
            self.log.debug("[labels] bootstrap skipped: %s", e)

    def _pretty_name(self, pool: str, var: str) -> str:
        """
        Zwraca przyjazną nazwę: `P6.v7 [Temperatura załączenia pomp]` jeśli label dostępny,
        w przeciwnym razie `P6.v7`.
        """
        # spróbuj wyciągnąć numer parametru z 'v7', 'u1', 's3', ...
        num: Optional[int] = None
        try:
            if var and var[0] in ("v", "u", "s", "n", "x"):
                num = int(var[1:])
        except Exception:
            num = None

        label: Optional[str] = None
        if num is not None and hasattr(self.labels, "param_label"):
            try:
                label = self.labels.param_label(pool, num, self.lang)
            except Exception:
                label = None

        if label:
            return f"{pool}.{var} [{label}]"
        return f"{pool}.{var}"

    # --------------- SNAPSHOT ---------------
    async def initial_snapshot(self):
        snap = await self.api.snapshot_parameters([self.devid])
        # spłaszcz i zaloguj
        for _dev, pools in (snap or {}).items():
            if not isinstance(pools, dict):
                continue
            for pool, vars_ in pools.items():
                if not isinstance(vars_, dict):
                    continue
                for var, meta in vars_.items():
                    val = (meta or {}).get("value") if isinstance(meta, dict) else meta
                    key = f"{pool}.{var}"
                    self._state[key] = val
                    self.log.info("[init] %s = %s", self._pretty_name(pool, var), val)

    # --------------- WS handlers ---------------
    def _register_ws_handlers(self):
        # connect / disconnect / error (na default NS i na /ws)
        @self.sio.event
        async def connect():
            # connect na domyślnym NS — bez logów; właściwy poniżej
            pass

        @self.sio.event
        async def connect_error(data):
            self.log.warning("WS connect_error: %s", data)

        @self.sio.event
        async def disconnect():
            self.log.info("WS disconnected")

        @self.sio.event(namespace=WS_NS)
        async def connect():
            self.log.info("WS connected %s", WS_NS)

        # wspólny parser zmian
        async def _handle_change(evname: str, payload: Any):
            if not isinstance(payload, dict):
                self.log.debug("[change] %s non-dict: %r", evname, payload)
                return
            try:
                for _devid, pools in (payload or {}).items():
                    if not isinstance(pools, dict):
                        continue
                    for pool, vars_ in pools.items():
                        if not isinstance(vars_, dict):
                            continue
                        for var, meta in vars_.items():
                            new_val = meta.get("value") if isinstance(meta, dict) else meta
                            key = f"{pool}.{var}"
                            old_val = self._state.get(key)
                            if new_val != old_val:
                                self._state[key] = new_val
                                self.log.info("[change] %s: %s -> %s",
                                              self._pretty_name(pool, var),
                                              old_val, new_val)
            except Exception as e:
                self.log.debug("on_change parse error: %s | raw=%s", e, payload)

        # rejestrujemy aliasy eventów
        @self.sio.on("app:modules:parameters:change", namespace=WS_NS)
        async def _on_change_app(payload):
            await _handle_change("app:modules:parameters:change", payload)

        @self.sio.on("modules:parameters:change", namespace=WS_NS)
        async def _on_change_modules(payload):
            await _handle_change("modules:parameters:change", payload)

        @self.sio.on("parameters:change", namespace=WS_NS)
        async def _on_change_plain(payload):
            await _handle_change("parameters:change", payload)

        # snapshot i zwykłe message — tylko DEBUG
        @self.sio.on("snapshot", namespace=WS_NS)
        async def _on_snapshot(payload):
            try:
                self.log.debug("[ws snapshot] %s",
                               json.dumps(payload, ensure_ascii=False) if isinstance(payload, (dict, list))
                               else repr(payload))
            except Exception:
                self.log.debug("[ws snapshot] %r", payload)

        @self.sio.on("message", namespace=WS_NS)
        async def _on_message(payload):
            try:
                self.log.debug("[ws message] %s",
                               json.dumps(payload, ensure_ascii=False) if isinstance(payload, (dict, list))
                               else repr(payload))
            except Exception:
                self.log.debug("[ws message] %r", payload)

    # --------------- WS connect ---------------
    async def connect_ws(self):
        if not self.jwt:
            raise RuntimeError("Brak JWT do WS")

        headers = {
            "Authorization": f"Bearer {self.jwt}",
            "Origin": ONE_BASE,
            "Referer": f"{ONE_BASE}/",
        }

        # Łączymy się pod bazowym hostem; socketio zrobi negotiation + upgrade.
        await self.sio.connect(
            IO_BASE,
            headers=headers,
            socketio_path=SOCK_PATH,
            namespaces=[WS_NS],
        )
        self.log.info("WS connected")

        # powiązanie sesji WS z modułem przez REST
        sid = self.sio.get_sid(WS_NS) or self.sio.sid
        ok = await self.api.modules_connect(sid, self.devids, object_id=self.object_id)
        self.log.info("modules.connect: %s", ok)

        # subskrypcje – to, co działało wcześniej (tylko /ws)
        payload = {"modules": self.devids}
        await self.sio.emit("app:modules:parameters:listen", payload, namespace=WS_NS)
        self.log.debug("[emit] app:modules:parameters:listen %s ns=%s", payload, WS_NS)

        await self.sio.emit("app:modules:activity:quantity:listen", payload, namespace=WS_NS)
        self.log.debug("[emit] app:modules:activity:quantity:listen %s ns=%s", payload, WS_NS)

        # opcjonalnie jednorazowy snapshot via WS:
        await self.sio.emit("app:modules:parameters:snapshot", self.devids, namespace=WS_NS)
        self.log.debug("[emit] app:modules:parameters:snapshot %s ns=%s", self.devids, WS_NS)

        # nasłuch (blokuje)
        await self.sio.wait()

    # --------------- Orkiestracja ---------------
    async def run_full_flow(self):
        # 1) login + moduły
        await self.login()
        await self.pick_modules()

        # 2) etykiety (best effort)
        await self._bootstrap_labels()

        # 3) snapshot init (z ładnymi nazwami)
        await self.initial_snapshot()

        # 4) WS + nasłuch
        await self.connect_ws()
