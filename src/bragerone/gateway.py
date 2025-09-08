from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from .const import IO_BASE, ONE_BASE, API_BASE, WS_NAMESPACE
from .api import Api
from .labels import LabelFetcher
from .ws import WsClient


class Gateway:
    """
    Spina Api (REST), LabelFetcher (etykiety z frontendowych assetów) i WsClient (socket.io).
    Utrzymuje prosty stan ostatnich wartości i robi czytelne logi zmian.
    """

    def __init__(self, email: str, password: str, object_id: int, lang: str = "en"):
        self.email = email
        self.password = password
        self.object_id = object_id
        self.lang = lang

        self.log = logging.getLogger("BragerOne")
        self.api = Api()
        self.labels = LabelFetcher(base_url=ONE_BASE, http_get=self._http_get)
        self.ws = WsClient(self.api, logger=self.log.getChild("ws"))

        self.jwt: Optional[str] = None
        self.devids: list[str] = []
        self._state: Dict[str, Any] = {}  # np. {"P6.v0": 65}

        # CB z WS
        self.ws.add_event_cb(self._on_ws_event)
        self.ws.add_change_cb(self._on_ws_change)

    # -------- helpers --------

    async def _http_get(self, url: str) -> str:
        # delegat dla LabelFetcher-a
        return await self.api._req("GET", url)

    def _pretty_name(self, pool: str, var: str) -> str:
        # stosujemy aliasy z LabelFetcher, jeśli są; inaczej proste pool.var
        label = self.labels.param_label(pool, var, self.lang)
        if label:
            return f"{pool}.{var} [{label}]"
        # druga próba: label po numerze (vNN -> NN)
        try:
            if var and var[0].isalpha():
                num = int(var[1:])
            else:
                num = None
        except Exception:
            num = None
        if num is not None:
            lbl2 = self.labels.param_label(pool, num, self.lang)
            if lbl2:
                return f"{pool}.{var} [{lbl2}]"
        return f"{pool}.{var}"

    # -------- public flow --------

    async def login(self) -> None:
        await self.api.ensure()
        await self.api.login(self.email, self.password)
        self.jwt = self.api.jwt
        self.log.info("Login OK")

    async def pick_modules(self) -> None:
        mods = await self.api.list_modules(self.object_id)
        devids = [m.get("devid") or m.get("device_id") or m.get("id") for m in mods if m]
        self.devids = [d for d in devids if d]
        if not self.devids:
            raise RuntimeError("No modules for that object_id")
        self.log.info("Modules: %s", self.devids)

    async def bootstrap_labels(self) -> None:
        try:
            await self.labels.bootstrap(lang=self.lang)
            self.log.debug("[labels] bootstrap ok")
        except Exception as e:
            self.log.warning("[labels] bootstrap failed: %s", e)

    async def initial_snapshot(self) -> None:
        snap = await self.api.snapshot_parameters(self.devids)
        # flatten + log
        cnt = 0
        for _dev, pools in (snap or {}).items():
            if not isinstance(pools, dict):
                continue
            for pool, vars_ in (pools or {}).items():
                if not isinstance(vars_, dict):
                    continue
                for var, meta in (vars_ or {}).items():
                    if not isinstance(meta, dict):
                        continue
                    val = meta.get("value")
                    key = f"{pool}.{var}"
                    self._state[key] = val
                    self.log.info("[init] %s = %s", self._pretty_name(pool, var), val)
                    cnt += 1
        self.log.debug("[init] snapshot items: %d", cnt)

    async def start_ws(self) -> None:
        """
        Proxy dla kompatybilności z __main__.py.
        Łączy WS, wiąże sesję z modułem i subskrybuje zmiany parametrów.
        """
        if not self.jwt:
            raise RuntimeError("JWT is empty – call login() first")

        # 1) uruchom websocket (autoryzacja tokenem)
        await self.ws.start_ws(self.jwt, namespace=WS_NAMESPACE)
        self.log.info("WS connected %s", WS_NAMESPACE)

        # 2) powiązanie sesji WS z modułami przez REST
        sid = self.ws.get_sid()
        ok = await self.api.modules_connect(sid, self.devids, object_id=self.object_id)
        self.log.info("modules.connect: %s", ok)

        # 3) subskrypcje (to co wcześniej działało)
        await self.ws.subscribe(self.devids, namespace=WS_NAMESPACE)

    async def connect_ws(self) -> None:
        if not self.jwt:
            raise RuntimeError("JWT missing; call login() first")

        await self.ws.start_ws(self.jwt, namespace=WS_NAMESPACE)

        # powiązanie sesji WS z modułem przez REST (to jest endpoint HTTP)
        try:
            ok = await self.api.modules_connect(self.ws.sio.sid, self.devids, object_id=self.object_id)
            self.log.info("modules.connect: %s", ok)
        except Exception as e:
            self.log.warning("modules.connect failed: %s", e)

        # subskrypcje
        await self.ws.subscribe(self.devids, namespace=WS_NAMESPACE)

    async def run_full_flow(self) -> None:
        """
        Używane przez CLI: login -> modules -> labels -> snapshot -> WS -> wait.
        """
        await self.login()
        await self.pick_modules()
        await self.bootstrap_labels()
        await self.initial_snapshot()
        await self.connect_ws()
        await self.ws.wait_forever()

    async def close(self) -> None:
        await self.ws.close()
        await self.api.close()

    # -------- WS callbacks --------

    def _on_ws_event(self, name: str, data: Any) -> None:
        # lekki log przydatny w debug
        try:
            if isinstance(data, (dict, list)):
                self.log.debug("[ws %s] %s", name, json.dumps(data, ensure_ascii=False))
            else:
                self.log.debug("[ws %s] %r", name, data)
        except Exception:
            self.log.debug("[ws %s] %r", name, data)

    def _on_ws_change(self, payload: dict) -> None:
        # payload: {"<devid>":{"P6":{"v0":{"value":65}}}}
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
                                          self._pretty_name(pool, var), old_val, new_val)
        except Exception as e:
            self.log.debug("on_change parse error: %s | raw=%s", e, payload)

