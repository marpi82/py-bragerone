"""Gateway: login → WS connect → modules.connect → listen → prime.

Maintains the WS connection and emits ParamUpdate events on the EventBus.
Does not contain heavy logic (such as mapping) internally — this is the role of ParamStore/HA.
"""

from __future__ import annotations

import asyncio
import logging
from asyncio import CancelledError, Event, Task, TaskGroup, create_task, gather, sleep
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from typing import Any

from .api import API_BASE, BragerOneApiClient, RealtimeManager
from .models.events import EventBus, ParamUpdate

LOG = logging.getLogger(__name__)

# Callback signatures
ParametersCb = Callable[[str, dict[str, Any]], Awaitable[None] | None]  # (event_name, payload)
SnapshotCb = Callable[[dict[str, Any]], Awaitable[None] | None]
GenericCb = Callable[[str, Any], Awaitable[None] | None]


class BragerOneGateway:
    """High-level orchestrator for Brager One realtime data.

    Flow:
      1) ensure_auth (proaktywny/reaktywny refresh w kliencie HTTP)
      2) Socket.IO connect → modules.connect (powiązanie WS z DEV)
      3) subscribe na strumienie (parameters, activity)
      4) „prime” (REST snapshot parametrów + ilości aktywności)
      5) EventBus emituje ParamUpdate dla konsumentów (ParamStore/HA/CLI)
    """

    def __init__(
        self,
        *,
        email: str,
        password: str,
        object_id: int,
        modules: Iterable[str],
    ):
        """Initialize the gateway but do not start it yet."""
        self.email = email
        self.password = password
        self.object_id = int(object_id)
        self.modules = sorted(set(modules))

        self.api: BragerOneApiClient | None = None
        self.ws: RealtimeManager | None = None
        self.bus = EventBus()

        self._tasks: set[Task[Any]] = set()
        self._started = False

        # (opcjonalne) sygnały do diagnostyki
        self._prime_done = Event()
        self._prime_seq: int | None = None
        self._first_snapshot = Event()

        # callbacks (opcjonalna kompatybilność)
        self._on_parameters_change: list[ParametersCb] = []
        self._on_snapshot: list[SnapshotCb] = []
        self._on_any: list[GenericCb] = []

    # ------------------------- Public API -------------------------

    def on_parameters_change(self, cb: ParametersCb) -> None:
        """Register callback for `app:modules:parameters:change`."""
        self._on_parameters_change.append(cb)

    def on_snapshot(self, cb: SnapshotCb) -> None:
        """Register callback for `snapshot` event (full state-like payload)."""
        self._on_snapshot.append(cb)

    def on_any(self, cb: GenericCb) -> None:
        """Register callback for *any* WS event for diagnostics."""
        self._on_any.append(cb)

    async def start(self) -> None:
        """Start the whole flow (idempotent)."""
        if self._started:
            return
        self._started = True

        # 1) HTTP API + login (token automatically refreshed by the client)
        self.api = BragerOneApiClient()
        await self.api.ensure_auth(self.email, self.password)
        token = self.api._token.access_token if self.api and self.api._token else ""  # pragmatic access

        # 2) WS connect
        self.ws = RealtimeManager(token=token or "")
        self.ws.on_event(self._ws_dispatch)
        await self.ws.connect()
        self.ws.add_on_connected(lambda: self.resubscribe())  # in case of reconnect

        # 3) modules.connect binds the current WS session with modules
        sid_ns = self.ws.sid()
        sid_engine = self.ws.engine_sid()
        if not sid_ns:
            raise RuntimeError("No namespace SID after connecting to WS (Socket.IO).")

        ok = await self._api_modules_connect(sid_ns, self.modules, group_id=self.object_id, engine_sid=sid_engine)
        LOG.info("modules.connect: %s (ns_sid=%s, engine_sid=%s)", ok, sid_ns, sid_engine)

        # 4) WS subscribe + PRIME via REST (in parallel)
        self.ws.group_id = self.object_id
        await self.ws.subscribe(self.modules)
        ok_params, ok_act = await self._prime_with_retry()
        LOG.debug("prime injected: parameters=%s activity=%s", ok_params, ok_act)
        LOG.info(
            "Gateway started: object_id=%s, modules=%s",
            self.object_id,
            ",".join(self.modules),
        )

    async def stop(self) -> None:
        """Gracefully stop the gateway: drop WS and release HTTP resources."""
        self._started = False
        # 1) disconnect WS
        try:
            if self.ws is not None:
                await self.ws.disconnect()
        except asyncio.CancelledError:
            # do not propagate CancelledError during shutdown
            pass
        except Exception:
            LOG.exception("Error while disconnecting WS")

        # 2) close the HTTP client (if the gateway manages it)
        try:
            if self.api is not None:
                await self.api.close()
        except Exception:
            LOG.exception("Error while closing ApiClient")

    async def __aenter__(self) -> BragerOneGateway:
        """Async context manager enter."""
        await self.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Async context manager exit."""
        await self.stop()

    async def resubscribe(self) -> None:
        """Call after WS reconnect to re-bind modules + prime again."""
        if not (self.api and self.ws):
            return
        sid_ns = self.ws.sid()
        sid_engine = self.ws.engine_sid()
        if not sid_ns:
            return
        ok = await self._api_modules_connect(sid_ns, self.modules, group_id=self.object_id, engine_sid=sid_engine)
        LOG.info("modules.connect (resub): %s", ok)
        await self.ws.subscribe(self.modules)
        okp, oka = await self._prime_with_retry()
        LOG.debug("prime after resubscribe: parameters=%s activity=%s", okp, oka)

    # ------------------------- PRIME & ingest -------------------------

    async def _prime(self) -> tuple[bool, bool]:
        """Fetch initial state via REST (/modules/parameters + /modules/activity/quantity)."""
        if self.api is None:
            raise RuntimeError("API client not initialized")
        ok_params = False
        ok_act = False

        async with TaskGroup() as tg:
            """Fetch parameters and activity quantities in parallel."""
            t_params = tg.create_task(
                self._api_modules_parameters_prime(self.modules, return_data=True),
                name="gateway.api.modules_parameters_prime",
            )
            t_act = tg.create_task(
                self._api_modules_activity_quantity_prime(self.modules, return_data=True),
                name="gateway.api.modules_activity_quantity_prime",
            )

        st1, data1 = t_params.result()
        if st1 in (200, 204) and isinstance(data1, dict):
            await self.ingest_prime_parameters(data1)
            ok_params = True

        st2, data2 = t_act.result()
        if st2 in (200, 204):
            await self.ingest_activity_quantity(data2 if isinstance(data2, dict) else None)
            ok_act = True

        self._prime_seq = self.bus.last_seq()
        self._prime_done.set()
        return ok_params, ok_act

    async def _prime_with_retry(self, tries: int = 3) -> tuple[bool, bool]:
        """Retry prime a few times with exponential backoff."""
        delay = 0.25
        for _ in range(tries):
            okp, oka = await self._prime()
            if okp:  # zależy nam głównie na parametrach
                return okp, oka
            await sleep(delay)
            delay = min(delay * 2.0, 2.0)
        return False, False

    async def ingest_prime_parameters(self, data: dict[str, Any]) -> None:
        """Treat /modules/parameters prime as „cold snapshot” and publish all pairs."""
        pairs = list(self.flatten_parameters(data))

        async def _pub_all() -> None:
            for upd in pairs:
                await self.bus.publish(upd)

        await _pub_all()

    async def ingest_activity_quantity(self, data: dict[str, Any] | None) -> None:
        """Ingest /modules/activity/quantity prime (optional)."""
        if isinstance(data, dict):
            LOG.debug("activityQuantity: %s", data.get("activityQuantity"))

    # ------------------------- WS dispatch -------------------------

    async def _invoke_list(self, cbs: list[Callable[..., Any]], *args: Any, **kwargs: Any) -> None:
        for cb in list(cbs):
            try:
                res = cb(*args, **kwargs)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                LOG.exception("Callback error")

    def _ws_dispatch(self, event_name: str, payload: Any) -> Awaitable[None] | None:
        # Any-listeners (diagnostyka)
        if self._on_any:
            self._spawn(
                self._invoke_list(self._on_any, event_name, payload),
                name="gateway.on_any",
            )

        # snapshot
        if event_name == "snapshot" and isinstance(payload, dict):
            pairs = list(self.flatten_parameters(payload))

            async def _pub_all() -> None:
                for upd in pairs:
                    await self.bus.publish(upd)

            self._spawn(_pub_all(), name="gateway.publish_snapshot")
            if self._on_snapshot:
                self._spawn(
                    self._invoke_list(self._on_snapshot, payload),
                    name="gateway.on_snapshot",
                )
            self._first_snapshot.set()
            return None

        # parameters:change
        if event_name.endswith("parameters:change") and isinstance(payload, dict):
            pairs = list(self.flatten_parameters(payload))

            async def _pub_all() -> None:
                for upd in pairs:
                    await self.bus.publish(upd)

            self._spawn(_pub_all(), name="gateway.publish_parameters_change")
            if self._on_parameters_change:
                self._spawn(
                    self._invoke_list(self._on_parameters_change, event_name, payload),
                    name="gateway.on_parameters_change",
                )
        return None

    # ------------------------- Helpers -------------------------

    def flatten_parameters(self, payload: dict[str, Any]) -> list[ParamUpdate]:
        """Convert WS/REST parameter payload into ParamUpdate events."""
        out: list[ParamUpdate] = []
        for devid, pools in payload.items():
            if not isinstance(pools, dict):
                continue
            for pool, entries in pools.items():
                if not isinstance(entries, dict):
                    continue
                for chan_idx, body in entries.items():
                    if not isinstance(chan_idx, str) or len(chan_idx) < 2:
                        continue
                    chan = chan_idx[0]
                    try:
                        idx = int(chan_idx[1:])
                    except ValueError:
                        continue
                    val: Any | None = None
                    meta: dict[str, Any] = {}
                    if isinstance(body, dict):
                        if "value" in body:
                            val = body["value"]
                        meta = {k: v for k, v in body.items() if k != "value"}
                    else:
                        val = body
                    out.append(
                        ParamUpdate(
                            devid=str(devid),
                            pool=str(pool),
                            chan=chan,
                            idx=idx,
                            value=val,
                            meta=meta,
                        )
                    )
        return out

    def _spawn(self, coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> Task[Any]:
        """Start a background task, keep reference, and log exceptions."""
        t = create_task(coro, name=name)
        self._tasks.add(t)

        def _finalizer(task: Task[Any]) -> None:
            try:
                _ = task.result()
            except CancelledError:
                pass
            except Exception:
                LOG.exception("Background task failed: %s", task.get_name() or "<unnamed>")
            finally:
                self._tasks.discard(task)

        t.add_done_callback(_finalizer)
        return t

    async def _cancel_all_tasks(self) -> None:
        """Cancel all tracked tasks and wait for completion."""
        if not self._tasks:
            return
        for t in list(self._tasks):
            t.cancel()
        await gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    # ------------------------- Raw REST helpers (no coupling on external API surface) -------------------------

    async def _api_modules_connect(
        self,
        wsid: str,
        modules: Iterable[str],
        *,
        group_id: int | None,
        engine_sid: str | None,
    ) -> bool:
        if self.api is None:
            raise RuntimeError("API client not initialized")
        payloads: list[dict[str, Any]] = [
            {"wsid": wsid, "modules": list(modules)},
            {"sid": wsid, "modules": list(modules)},
        ]
        if group_id is not None:
            payloads.append({"wsid": wsid, "group_id": int(group_id), "modules": list(modules)})

        for pl in payloads:
            try:
                st, data, _ = await self.api._req("POST", f"{API_BASE}/modules/connect", json=pl)
                LOG.debug("modules.connect try %s → %s %s", pl, st, data)
                if st == 200:
                    return True
            except Exception:
                continue  # nosec B112 - intentionally try multiple payloads until one succeeds
        return False

    async def _api_modules_parameters_prime(self, modules: Iterable[str], *, return_data: bool = True) -> tuple[int, Any | None]:
        if self.api is None:
            raise RuntimeError("API client not initialized")
        pl = {"modules": list(modules)}
        st, data, _ = await self.api._req("POST", f"{API_BASE}/modules/parameters", json=pl)
        return st, (data if return_data else None)

    async def _api_modules_activity_quantity_prime(
        self, modules: Iterable[str], *, return_data: bool = True
    ) -> tuple[int, Any | None]:
        if self.api is None:
            raise RuntimeError("API client not initialized")
        pl = {"modules": list(modules)}
        st, data, _ = await self.api._req("POST", f"{API_BASE}/modules/activity/quantity", json=pl)
        return st, (data if return_data else None)
