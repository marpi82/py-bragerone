from __future__ import annotations
import logging
from typing import Any, Dict, Optional

from .api import Api
from .ws import WsClient
from .labels import LabelFetcher, format_value


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
        logger: Optional[logging.Logger] = None,
    ):
        self.email = email
        self.password = password
        self.object_id = object_id
        self.lang = lang

        self.log = logger or logging.getLogger("BragerOne")
        self.api = Api()
        self.labels = LabelFetcher()

        # WS client (token on demand from Api)
        self.ws = WsClient(lambda: self.api.jwt, logger=self.log.getChild("ws"))
        self.ws.set_event_handler(self._on_ws_event)
        self.ws.set_change_handler(self._on_ws_change)

        # chosen device ids
        self.devids: list[str] = []

        # current flat state: "P6.v7" -> value
        self._state: Dict[str, Any] = {}

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

    async def bootstrap_labels(self) -> None:
        """Ensure labels cache (v1: cache-only)."""
        self.labels.bootstrap(self.lang)
        self.log.debug(
            "[labels] bootstrap ok (vars=%d, langs=%d)",
            self.labels.count_vars(),
            self.labels.count_langs(),
        )

    async def initial_snapshot(self) -> None:
        """
        Fetch & flatten snapshot for current devids. Update _state and log.
        """
        flat = await self.snapshot_flat()
        self.log.info("[init] snapshot items: %d", len(flat))
        for key, val in flat.items():
            pool, var = key.split(".", 1)
            pretty = self.pretty_label(pool, var)
            formatted = format_value(pool, var, val, self.labels, self.lang)
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
        try:
            await self.stop_ws()
        except Exception:
            pass
        await self.api.close()

    # ---------------------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------------------

    async def snapshot_flat(self) -> Dict[str, Any]:
        """
        Fresh snapshot as flat dict: "P4.v2" -> value
        Also updates internal baseline (_state).
        """
        if not self.devids:
            raise RuntimeError("Call pick_modules() first to populate devids")

        snap = await self.api.snapshot_parameters(self.devids)
        flat: Dict[str, Any] = {}
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

    def pretty_label(self, pool: str, var: str) -> str:
        """
        Human label for variable name (e.g. P6.v7). Adds param label if available.
        """
        num = None
        if var and var[0] in ("v", "n", "x", "u", "s"):
            try:
                num = int(var[1:])
            except Exception:
                num = None

        if num is not None:
            label = self.labels.get_param_label(pool, num, self.lang)
            if label:
                return f"{pool}.{var} [{label}]"
        return f"{pool}.{var}"

    # ---------------------------------------------------------------------
    # WS callbacks
    # ---------------------------------------------------------------------

    def _on_ws_event(self, name: str, data: Any) -> None:
        # keep engine chatter quiet; still handy for diagnostics at DEBUG
        if name in ("socket.connect", "socket.disconnect"):
            return
        try:
            self.log.debug("[ws %s] %r", name, data)
        except Exception:
            pass

    def _on_ws_change(self, payload: Dict[str, Any]) -> None:
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
                            pretty = self.pretty_label(pool, var)
                            formatted = format_value(pool, var, new_val, self.labels, self.lang)
                            self.log.debug("[change] %s: %s -> %s", pretty, old_val, formatted)
        except Exception as e:
            self.log.debug("on_change parse error: %s | raw=%r", e, payload)

