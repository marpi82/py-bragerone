"""Gateway: WS connect → modules.connect → listen → prime.

Maintains the WS connection and emits ParamUpdate events on the EventBus.
Does not contain heavy logic (such as mapping) internally — this is the role of ParamStore/HA.

Also tracks per-module cloud connectivity (REST ``connectedAt`` + WS session) via a
dedicated callback path — not the ParamUpdate EventBus — so Home Assistant can keep
iterating ``bus.subscribe()`` unchanged.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from typing import Any, Literal, Protocol

from .api import BragerOneApiClient, RealtimeManager, ServerConfig
from .models.api.modules import Module
from .models.events import EventBus, ModuleConnectivity, ParamUpdate

LOG = logging.getLogger(__name__)

# Default REST poll interval for module connectedAt refresh (seconds).
_DEFAULT_CONNECTIVITY_POLL_INTERVAL_S = 60.0

ConnectivitySource = Literal["rest", "ws", "derived"]

# Callback signatures
ParametersCb = Callable[[str, dict[str, Any]], Awaitable[None] | None]  # (event_name, payload)
SnapshotCb = Callable[[dict[str, Any]], Awaitable[None] | None]
GenericCb = Callable[[str, Any], Awaitable[None] | None]
ModuleConnectivityCb = Callable[[ModuleConnectivity], Awaitable[None] | None]


def module_connected_at_means_online(connected_at: int) -> bool:
    """Return whether a ``connectedAt`` value means the module is online.

    Mirrors the SPA ternary ``connectedAt ? 'connected' : 'notConnected'``.
    Upstream uses ``0`` as the offline sentinel (see fixtures and live payloads).
    """
    return int(connected_at) != 0


# Socket.IO event the official SPA listens for in Layout / ObjectsLayout.
MODULE_CONNECTION_STATUS_CHANGED = "app:module:connection:status:changed"


class ApiClient(Protocol):
    """Protocol for the HTTP client used by the gateway.

    This makes the gateway easy to test by allowing a lightweight fake.
    """

    @property
    def access_token(self) -> str:  # noqa: D102
        raise NotImplementedError

    async def modules_connect(  # noqa: D102
        self,
        wsid_ns: str,
        modules: list[str],
        group_id: int | None = None,
        engine_sid: str | None = None,
    ) -> bool:
        raise NotImplementedError

    async def modules_parameters_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:  # noqa: D102
        raise NotImplementedError

    async def modules_activity_quantity_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:  # noqa: D102
        raise NotImplementedError

    async def get_modules(self, object_id: int) -> list[Module]:  # noqa: D102
        ...

    async def close(self) -> None:  # noqa: D102
        raise NotImplementedError


class RealtimeManagerClient(Protocol):
    """Protocol for the WS client used by the gateway."""

    @property
    def group_id(self) -> int | None:  # noqa: D102
        raise NotImplementedError

    @group_id.setter
    def group_id(self, group_id: int | None) -> None:
        raise NotImplementedError

    def on_event(self, handler: Any) -> None:  # noqa: D102
        raise NotImplementedError

    async def connect(self) -> None:  # noqa: D102
        raise NotImplementedError

    async def disconnect(self) -> None:  # noqa: D102
        raise NotImplementedError

    def add_on_connected(self, cb: Callable[[], Awaitable[None] | None]) -> None:  # noqa: D102
        raise NotImplementedError

    def add_on_disconnected(self, cb: Callable[[], Awaitable[None] | None]) -> None:  # noqa: D102
        ...

    def sid(self) -> str | None:  # noqa: D102
        raise NotImplementedError

    def engine_sid(self) -> str | None:  # noqa: D102
        raise NotImplementedError

    async def subscribe(self, modules: list[str]) -> None:  # noqa: D102
        raise NotImplementedError


class BragerOneGateway:
    """High-level orchestrator for BragerOne realtime data.

    Flow:
      1) ensure_auth (proactive/reactive refresh in HTTP client)
      2) Socket.IO connect → modules.connect (binding WS with DEV)
      3) subscribe to streams (parameters, activity)
      4) "prime" (REST snapshot of parameters + activity quantities)
      5) EventBus emits ParamUpdate for consumers (ParamStore/HA/CLI)
      6) Background REST poll of ``get_modules`` diffs ``connectedAt`` and
         notifies ``on_module_connectivity`` (separate from EventBus)
    """

    def __init__(
        self,
        *,
        api: ApiClient,
        object_id: int,
        modules: Iterable[str],
        ws: RealtimeManagerClient | None = None,
        owns_api: bool = False,
        connectivity_poll_interval: float = _DEFAULT_CONNECTIVITY_POLL_INTERVAL_S,
    ) -> None:
        """Initialize the gateway but do not start it yet.

        Args:
            api: Authenticated API client. The gateway uses it for module binding and primes.
            object_id: BragerOne object/group ID.
            modules: Modules to subscribe.
            ws: Optional WS client instance (useful for testing).
            owns_api: If True, the gateway closes the API client on :meth:`stop`.
            connectivity_poll_interval: Seconds between REST ``get_modules`` connectivity
                refreshes. Use ``0`` to disable the background poll (manual
                :meth:`refresh_module_connectivity` / WS hooks still work).
        """
        self.object_id = int(object_id)
        self.modules = sorted(set(modules))

        self.api: ApiClient = api
        self.ws: RealtimeManagerClient | None = ws
        self.bus = EventBus()

        self._owns_api = owns_api
        self._connectivity_poll_interval = float(connectivity_poll_interval)

        self._tasks: set[asyncio.Task[Any]] = set()
        self._started = False

        # (optional) diagnostic signals
        self._prime_done = asyncio.Event()
        self._prime_seq: int | None = None
        self._first_snapshot = asyncio.Event()

        # callbacks (optional backward compatibility)
        self._on_parameters_change: list[ParametersCb] = []
        self._on_snapshot: list[SnapshotCb] = []
        self._on_any: list[GenericCb] = []
        self._on_module_connectivity: list[ModuleConnectivityCb] = []

        # Per-module cloud connectivity (REST/WS connectedAt) + gateway WS session.
        self._ws_session_up = False
        self._module_connected_at: dict[str, int] = {}
        self._module_online: dict[str, bool] = {}
        self._module_gateway: dict[str, dict[str, Any]] = {}

    @classmethod
    async def from_credentials(
        cls,
        *,
        email: str,
        password: str,
        object_id: int,
        modules: Iterable[str],
        server: ServerConfig | None = None,
        ws: RealtimeManagerClient | None = None,
        api: BragerOneApiClient | None = None,
        connectivity_poll_interval: float = _DEFAULT_CONNECTIVITY_POLL_INTERVAL_S,
    ) -> BragerOneGateway:
        """Create a gateway from credentials.

        This is a convenience helper for CLI/examples.

        Args:
            email: BragerOne account email.
            password: BragerOne account password.
            object_id: BragerOne object/group ID.
            modules: Modules to subscribe.
            server: Optional server/platform configuration (e.g. TiSConnect).
            ws: Optional WS client instance (testing).
            api: Optional API client instance (testing/customization).
            connectivity_poll_interval: See :meth:`__init__`.

        Returns:
            An initialized gateway (not started).
        """
        owned_api = api is None
        api_client = api or BragerOneApiClient(
            server=server,
            # Retain credentials so ensure_auth() can re-login when the token
            # expires mid-session (e.g. WS reconnect after a long outage).
            creds_provider=lambda: (email, password),
        )
        await api_client.ensure_auth(email, password)
        return cls(
            api=api_client,
            object_id=object_id,
            modules=modules,
            ws=ws,
            owns_api=owned_api,
            connectivity_poll_interval=connectivity_poll_interval,
        )

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

    def on_module_connectivity(self, cb: ModuleConnectivityCb) -> None:
        """Register callback for per-module online/offline transitions.

        Callbacks receive :class:`ModuleConnectivity`. This path is intentionally
        separate from :attr:`bus` so ``ParamUpdate`` subscribers stay unchanged.
        """
        self._on_module_connectivity.append(cb)

    def module_online(self, devid: str) -> bool | None:
        """Return current online state for *devid*, or ``None`` if not yet known."""
        return self._module_online.get(devid)

    def module_connected_at(self, devid: str) -> int | None:
        """Return the last ``connectedAt`` for *devid*, or ``None`` if unknown."""
        return self._module_connected_at.get(devid)

    def module_gateway(self, devid: str) -> dict[str, Any] | None:
        """Return the last gateway blob for *devid* (address/interface/version)."""
        gateway = self._module_gateway.get(devid)
        return dict(gateway) if isinstance(gateway, dict) else None

    async def refresh_module_connectivity(self) -> None:
        """Refresh connectivity from REST ``get_modules`` (no-op when WS session is down)."""
        await self._refresh_module_connectivity(source="rest")

    async def start(self) -> None:
        """Start the whole flow (idempotent)."""
        if self._started:
            return
        self._started = True
        started_at = time.monotonic()

        # 1) WS connect
        if self.ws is None:
            if isinstance(self.api, BragerOneApiClient):
                self.ws = RealtimeManager(
                    token=self.api.access_token,
                    token_provider=self._fresh_ws_token,
                    origin=self.api.one_base,
                    referer=f"{self.api.one_base}/",
                    io_base=self.api.io_base,
                )
            else:
                self.ws = RealtimeManager(token=self.api.access_token)
        ws = self.ws
        if ws is None:
            raise RuntimeError("RealtimeManager is not initialized")
        ws.on_event(self._ws_dispatch)
        await ws.connect()
        self._ws_session_up = True
        ws.add_on_connected(self._on_ws_connected)
        ws.add_on_disconnected(self._on_ws_disconnected)
        ws_connected_at = time.monotonic()

        # 3) modules.connect binds the current WS session with modules
        sid_ns = ws.sid()
        sid_engine = ws.engine_sid()
        if not sid_ns:
            raise RuntimeError("No namespace SID after connecting to WS (Socket.IO).")

        ok = await self.api.modules_connect(sid_ns, self.modules, group_id=self.object_id, engine_sid=sid_engine)
        LOG.info("modules.connect: %s (ns_sid=%s, engine_sid=%s)", ok, sid_ns, sid_engine)
        modules_connected_at = time.monotonic()

        # 4) WS subscribe + PRIME via REST (in parallel)
        ws.group_id = self.object_id
        await ws.subscribe(self.modules)
        subscribed_at = time.monotonic()
        ok_params, ok_act = await self._prime_with_retry()
        primed_at = time.monotonic()
        LOG.debug("prime injected: parameters=%s activity=%s", ok_params, ok_act)
        await self._refresh_module_connectivity(source="rest")
        if self._connectivity_poll_interval > 0:
            self._spawn(self._connectivity_poll_loop(), name="gateway.connectivity_poll")
        LOG.info(
            "Gateway started: object_id=%s, modules=%s",
            self.object_id,
            ",".join(self.modules),
        )
        LOG.debug(
            "Gateway startup timings: total=%.3fs ws_connect=%.3fs modules_connect=%.3fs subscribe=%.3fs prime=%.3fs",
            primed_at - started_at,
            ws_connected_at - started_at,
            modules_connected_at - ws_connected_at,
            subscribed_at - modules_connected_at,
            primed_at - subscribed_at,
        )

    async def stop(self) -> None:
        """Gracefully stop the gateway: drop WS and release HTTP resources."""
        self._started = False

        # Cancel background tasks first (callbacks / bus injectors)
        try:
            await self._cancel_all_tasks()
        except Exception:
            LOG.exception("Error while canceling background tasks")

        # 1) disconnect WS
        try:
            if self.ws is not None:
                await self.ws.disconnect()
        except asyncio.CancelledError:
            # Shutdown must continue even if disconnect is cancelled mid-flight.
            pass  # intentionally ignore: CancelledError is expected during stop()
        except Exception:
            LOG.exception("Error while disconnecting WS")
        finally:
            self._ws_session_up = False

        # 2) close the HTTP client (if the gateway manages it)
        try:
            if self._owns_api:
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

    async def _fresh_ws_token(self) -> str:
        """Return a valid token for a WS (re)connect, re-authenticating if expired."""
        api = self.api
        if not isinstance(api, BragerOneApiClient):
            return api.access_token
        await api.ensure_auth()
        return api.access_token

    async def _on_ws_connected(self) -> None:
        """Re-bind modules after WS reconnect, then refresh connectivity."""
        self._ws_session_up = True
        await self.resubscribe()
        await self._refresh_module_connectivity(source="rest")

    def _on_ws_disconnected(self) -> None:
        """Mark subscribed modules offline while the client Socket.IO session is down."""
        self._ws_session_up = False
        self._spawn(self._mark_modules_offline_from_ws(), name="gateway.ws_disconnect_offline")

    async def _mark_modules_offline_from_ws(self) -> None:
        for devid in self.modules:
            await self._apply_connectivity(
                devid=devid,
                online=False,
                source="ws",
                connected_at=self._module_connected_at.get(devid),
            )

    async def resubscribe(self) -> None:
        """Call after WS reconnect to re-bind modules + prime again."""
        ws = self.ws
        if ws is None:
            return
        sid_ns = ws.sid()
        sid_engine = ws.engine_sid()
        if not sid_ns:
            return
        ok = await self.api.modules_connect(sid_ns, self.modules, group_id=self.object_id, engine_sid=sid_engine)
        LOG.info("modules.connect (resub): %s", ok)
        await ws.subscribe(self.modules)
        okp, oka = await self._prime_with_retry()
        LOG.debug("prime after resubscribe: parameters=%s activity=%s", okp, oka)

    async def wait_for_prime(self, timeout: float | None = None) -> bool:
        """Wait until the latest prime pass is finished.

        Args:
            timeout: Optional timeout in seconds. When ``None``, waits indefinitely.

        Returns:
            ``True`` if prime completion event was observed, ``False`` on timeout.
        """
        if self._prime_done.is_set():
            return True
        try:
            if timeout is None:
                await self._prime_done.wait()
            else:
                await asyncio.wait_for(self._prime_done.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    # ------------------------- Connectivity -------------------------

    async def _connectivity_poll_loop(self) -> None:
        """Periodically refresh REST connectedAt while the gateway is running.

        Stop cancels this task; cancellation during ``sleep`` / refresh ends the loop.
        """
        interval = self._connectivity_poll_interval
        while True:
            await asyncio.sleep(interval)
            await self._refresh_module_connectivity(source="rest")

    async def _refresh_module_connectivity(self, *, source: ConnectivitySource) -> None:
        """Pull ``get_modules`` and apply online state for subscribed devids."""
        if not self._ws_session_up:
            # Client session down: keep modules offline until reconnect + refresh.
            return
        try:
            rows = await self.api.get_modules(self.object_id)
        except Exception:
            LOG.exception("get_modules failed during connectivity refresh")
            return

        wanted = set(self.modules)
        seen: set[str] = set()
        for row in rows:
            devid = str(getattr(row, "devid", "") or "")
            if not devid or devid not in wanted:
                continue
            seen.add(devid)
            connected_at = int(getattr(row, "connectedAt", 0) or 0)
            rest_online = module_connected_at_means_online(connected_at)
            gateway_obj = getattr(row, "gateway", None)
            gateway: dict[str, Any] | None = None
            if gateway_obj is not None:
                dump = getattr(gateway_obj, "model_dump", None)
                if callable(dump):
                    raw = dump(mode="json")
                    if isinstance(raw, dict):
                        gateway = raw
                elif isinstance(gateway_obj, dict):
                    gateway = dict(gateway_obj)
            await self._apply_connectivity(
                devid=devid,
                online=rest_online and self._ws_session_up,
                source=source,
                connected_at=connected_at,
                gateway=gateway,
            )

        # Subscribed modules missing from the object listing → offline.
        for devid in wanted - seen:
            await self._apply_connectivity(
                devid=devid,
                online=False,
                source="derived",
                connected_at=self._module_connected_at.get(devid, 0),
            )

    async def _apply_connectivity(
        self,
        *,
        devid: str,
        online: bool,
        source: ConnectivitySource,
        connected_at: int | None,
        gateway: dict[str, Any] | None = None,
    ) -> None:
        """Update cache and notify listeners when the online bit changes."""
        if connected_at is not None:
            self._module_connected_at[devid] = int(connected_at)
        if gateway is not None:
            self._module_gateway[devid] = dict(gateway)
        previous = self._module_online.get(devid)
        if previous is online:
            return
        self._module_online[devid] = online
        event = ModuleConnectivity(
            devid=devid,
            online=online,
            source=source,
            connected_at=self._module_connected_at.get(devid),
            gateway=self.module_gateway(devid),
        )
        LOG.info(
            "Module connectivity: devid=%s online=%s source=%s connectedAt=%s",
            devid,
            online,
            source,
            event.connected_at,
        )
        if self._on_module_connectivity:
            await self._invoke_list(self._on_module_connectivity, event)

    # ------------------------- PRIME & ingest -------------------------

    async def _prime(self) -> tuple[bool, bool]:
        """Fetch initial state via REST (/modules/parameters + /modules/activity/quantity)."""
        ok_params = False
        ok_act = False

        # Fetch parameters and activity quantities in parallel.
        async with asyncio.TaskGroup() as tg:
            t_params = tg.create_task(
                self.api.modules_parameters_prime(self.modules, return_data=True),
                name="gateway.api.modules_parameters_prime",
            )
            t_act = tg.create_task(
                self.api.modules_activity_quantity_prime(self.modules, return_data=True),
                name="gateway.api.modules_activity_quantity_prime",
            )

        res1 = t_params.result()
        if isinstance(res1, tuple) and len(res1) == 2:
            st1, data1 = res1
            if st1 in (200, 204) and isinstance(data1, dict):
                await self.ingest_prime_parameters(data1)
                ok_params = True

        res2 = t_act.result()
        if isinstance(res2, tuple) and len(res2) == 2:
            st2, data2 = res2
            if st2 in (200, 204):
                await self.ingest_activity_quantity(data2 if isinstance(data2, dict) else None)
                ok_act = True

        self._prime_seq = self.bus.last_seq()
        self._prime_done.set()
        return ok_params, ok_act

    async def _prime_with_retry(self, tries: int = 3) -> tuple[bool, bool]:
        """Retry prime a few times with exponential backoff."""
        delay = 0.25
        for attempt in range(tries):
            attempt_started = time.monotonic()
            okp, oka = await self._prime()
            LOG.debug(
                "Prime attempt %s/%s finished in %.3fs (parameters=%s activity=%s)",
                attempt + 1,
                tries,
                time.monotonic() - attempt_started,
                okp,
                oka,
            )
            if okp:  # we care mainly about parameters
                return okp, oka
            await asyncio.sleep(delay)
            delay = min(delay * 2.0, 2.0)
        return False, False

    async def ingest_prime_parameters(self, data: dict[str, Any]) -> None:
        """Treat /modules/parameters prime as "cold snapshot" and publish all pairs."""
        pairs = list(self.flatten_parameters(data, source="prime"))

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
        # Any-listeners (diagnostics)
        if self._on_any:
            self._spawn(
                self._invoke_list(self._on_any, event_name, payload),
                name="gateway.on_any",
            )

        # snapshot
        if event_name == "snapshot" and isinstance(payload, dict):
            pairs = list(self.flatten_parameters(payload, source="snapshot"))

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
            pairs = list(self.flatten_parameters(payload, source="ws"))

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

        # SPA Layout handler: Object.entries(payload) → module.connectedAt / gateway
        if event_name == MODULE_CONNECTION_STATUS_CHANGED and isinstance(payload, dict):
            self._spawn(
                self._ingest_module_connection_status(payload),
                name="gateway.module_connection_status",
            )
        return None

    async def _ingest_module_connection_status(self, payload: dict[str, Any]) -> None:
        """Apply SPA ``app:module:connection:status:changed`` payloads per devid."""
        if not self._ws_session_up:
            return
        wanted = set(self.modules)
        for raw_devid, body in payload.items():
            devid = str(raw_devid or "")
            if not devid or devid not in wanted or not isinstance(body, dict):
                continue
            connected_raw = body.get("connectedAt", body.get("connected_at", 0))
            try:
                connected_at = int(connected_raw or 0)
            except (TypeError, ValueError):
                connected_at = 0
            gateway_raw = body.get("gateway")
            gateway = dict(gateway_raw) if isinstance(gateway_raw, dict) else None
            await self._apply_connectivity(
                devid=devid,
                online=module_connected_at_means_online(connected_at),
                source="ws",
                connected_at=connected_at,
                gateway=gateway,
            )

    # ------------------------- Helpers -------------------------

    def flatten_parameters(self, payload: dict[str, Any], *, source: str = "unknown") -> list[ParamUpdate]:
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
                    meta["_source"] = source
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

    def _spawn(self, coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> asyncio.Task[Any]:
        """Start a background task, keep reference, and log exceptions."""
        t = asyncio.create_task(coro, name=name)
        self._tasks.add(t)

        def _finalizer(task: asyncio.Task[Any]) -> None:
            try:
                _ = task.result()
            except asyncio.CancelledError:
                pass  # intentionally ignore: cancelled background tasks are expected
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
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
