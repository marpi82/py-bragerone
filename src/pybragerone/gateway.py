from __future__ import annotations

import contextlib
import logging
from typing import Any

from .api import Api
from .labels import LabelFetcher
from .ws import WsClient


class Gateway:
    """
    Orchestrates:
      - REST API (Api)
      - WebSocket client (WsClient)
      - Labels cache/formatting (LabelFetcher)

    Small and composable: CLI uses it end-to-end, HA can call individual pieces.
    """

    def __init__(
        self,
        email: str,
        password: str,
        *,
        object_id: int,
        lang: str = "en",
        logger: logging.Logger | None = None,
    ):
        self.email = email
        self.password = password
        self.object_id = object_id
        self.lang = lang

        self.log = logger or logging.getLogger("BragerOne")
        self.api = Api()
        self.labels = LabelFetcher(lang=self.lang, session=self.api.session, logger=self.log)

        # WS client (token on demand from Api)
        self.ws = WsClient(lambda: self.api.jwt, logger=self.log.getChild("ws"))
        self.ws.set_event_handler(self._on_ws_event)
        self.ws.set_change_handler(self._on_ws_change)

        # chosen device ids
        self.devids: list[str] = []

        # current snap state: "P6.v7" -> value
        self._state: dict[str, Any] = {}

    # ---------------------------------------------------------------------
    # High-level steps (used by CLI)
    # ---------------------------------------------------------------------

    async def login(self) -> None:
        """Authenticate; does not pick modules."""
        await self.api.login(self.email, self.password)
        self.log.info("Login OK")

    async def pick_modules(self) -> None:
        """Fetch modules for object and pick device ids."""
        mods = await self.api.list_modules(self.object_id)
        devids = [m.get("devid") or m.get("device_id") or m.get("id") for m in (mods or []) if m]
        self.devids = [d for d in devids if d]
        if not self.devids:
            raise RuntimeError("No modules found for this object_id")
        self.log.info("Modules: %s", self.devids)

    async def bootstrap(self) -> None:
        await self.labels.bootstrap_from_frontend()

    async def initial_snapshot(self, prefetch_assets: bool = False) -> None:
        """
        Fetch & flatten snapshot for current devids. Update _state and log.
        """
        snap = await self.snapshot_flat()
        self.log.info("[init] snapshot items: %d", len(snap))

        # --- po snapshot - doważ jednostki, jeżeli mamy już katalog ---
        if prefetch_assets:
            await self.bootstrap()
            if self.labels and self.labels.catalog:
                bound = self.labels.bind_units_from_snapshot(snap)
                if self.log:
                    self.log.debug("[labels] bound %d unit(s) from snapshot", bound)

        for key, val in snap.items():
            pool, var = key.split(".", 1)
            pretty = self.labels.pretty_label(pool, var)
            formatted = self.labels.format_value(pool, var, val, self.lang)
            self.log.debug("[init] %s = %s", pretty, formatted)

    async def start_ws(self) -> None:
        """Connect WS, link session to modules (REST), subscribe to changes."""
        if not self.devids:
            raise RuntimeError("Call pick_modules() first to populate devids")

        await self.ws.connect()

        # link WS session to our modules via REST
        sid = self.ws.sid()
        if sid:
            ok = await self.api.modules_connect(sid, self.devids, object_id=self.object_id)
            self.log.info("modules.connect: %s", ok)

        # subscribe streams
        await self.ws.subscribe(self.devids)

    async def stop_ws(self) -> None:
        await self.ws.close()

    async def close(self) -> None:
        """Graceful shutdown (WS + HTTP)."""
        with contextlib.suppress(Exception):
            await self.stop_ws()
        await self.api.close()

    # ---------------------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------------------

    async def snapshot_flat(self) -> dict[str, Any]:
        """
        Fresh snapshot as flat dict: "P4.v2" -> value
        Also updates internal baseline (_state).
        """
        if not self.devids:
            raise RuntimeError("Call pick_modules() first to populate devids")

        snap = await self.api.snapshot_parameters(self.devids)
        flat: dict[str, Any] = {}
        for _devid, pools in (snap or {}).items():
            if not isinstance(pools, dict):
                continue
            for pool, vars_ in pools.items():
                if not isinstance(vars_, dict):
                    continue
                for var, meta in vars_.items():
                    key = f"{pool}.{var}"
                    val = (meta or {}).get("value") if isinstance(meta, dict) else meta
                    flat[key] = val

        self._state.update(flat)
        return flat

    # ---------------------------------------------------------------------
    # WS callbacks
    # ---------------------------------------------------------------------

    def _on_ws_event(self, name: str, data: Any) -> None:
        # keep engine chatter quiet; still handy for diagnostics at DEBUG
        if name in ("socket.connect", "socket.disconnect"):
            return
        with contextlib.suppress(Exception):
            self.log.debug("[ws %s] %r", name, data)

    def _on_ws_change(self, payload: dict[str, Any]) -> None:
        """
        Called by WsClient on parameter changes.
        Payload example:
          { "<devid>": { "P4": { "v2": {"value": 46}, ... }, ... } }
        """
        if not isinstance(payload, dict):
            self.log.debug("[change] non-dict: %r", payload)
            return

        try:
            for _devid, pools in payload.items():
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
                            pretty = self.labels.pretty_label(pool, var)
                            formatted = self.labels.format_value(pool, var, new_val, self.lang)
                            self.log.debug("[change] %s: %s -> %s", pretty, old_val, formatted)
        except Exception as e:
            self.log.debug("on_change parse error: %s | raw=%r", e, payload)
