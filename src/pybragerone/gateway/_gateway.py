"""Gateway facade: lifecycle, EventBus, ingest/dispatch, and mixin wiring."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from typing import Any, Literal

from ..api import BragerOneApiClient, ServerConfig
from ..api.client import format_expected_failure_reason, is_expected_upstream_unavailable
from ..models.events import (
    MODULE_CONNECTION_STATUS_CHANGED,
    MODULE_MEMORY_UPDATED,
    AlarmQuantityChanged,
    CloudOutageReason,
    EventBus,
    ModuleOutageReason,
    ParamUpdate,
)
from .connectivity import _DEFAULT_CONNECTIVITY_POLL_INTERVAL_S, ConnectivityMixin
from .helpers import (
    AlarmQuantityCb,
    CloudSessionCb,
    GenericCb,
    ModuleConnectivityCb,
    ParametersCb,
    SnapshotCb,
    _is_api_dispatch_timeout,
    _is_http_timeout_error,
    _parse_alarm_quantity,
)
from .protocols import ApiClient, RealtimeManagerClient
from .recovery import (
    _DEFAULT_STALE_PRIME_AFTER_S,
    _DEFAULT_ZOMBIE_FULL_RECYCLE_AFTER,
    _DEFAULT_ZOMBIE_HARD_RESTART_AFTER,
    _DEFAULT_ZOMBIE_QUARANTINE_AFTER,
    _DEFAULT_ZOMBIE_QUARANTINE_S,
    _DEFAULT_ZOMBIE_REBUILD_AFTER,
    _DEFAULT_ZOMBIE_RECOVERY_COOLDOWN_S,
    RecoveryMixin,
)
from .session import SessionMixin

LOG = logging.getLogger(__name__)


class BragerOneGateway(ConnectivityMixin, SessionMixin, RecoveryMixin):
    """High-level orchestrator for BragerOne realtime data.

    Flow:
      1) ensure_auth (proactive/reactive refresh in HTTP client)
      2) Socket.IO connect → modules.connect (binding WS with DEV)
      3) subscribe to streams (parameters, activity)
      4) "prime" (REST snapshot of parameters + activity quantities)
      5) EventBus emits ParamUpdate for consumers (ParamStore/HA/CLI)
      6) Background REST poll of ``get_modules`` diffs ``connectedAt`` and
         notifies ``on_module_connectivity`` (module↔cloud; separate from EventBus)
      7) Socket.IO up/down notifies ``on_cloud_session`` (library↔cloud; self-healing)
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
        stale_prime_after_s: float = _DEFAULT_STALE_PRIME_AFTER_S,
        zombie_hard_restart_after: int = _DEFAULT_ZOMBIE_HARD_RESTART_AFTER,
        zombie_full_recycle_after: int = _DEFAULT_ZOMBIE_FULL_RECYCLE_AFTER,
        zombie_rebuild_after: int = _DEFAULT_ZOMBIE_REBUILD_AFTER,
        zombie_recovery_cooldown_s: float = _DEFAULT_ZOMBIE_RECOVERY_COOLDOWN_S,
        zombie_quarantine_after: int = _DEFAULT_ZOMBIE_QUARANTINE_AFTER,
        zombie_quarantine_s: float = _DEFAULT_ZOMBIE_QUARANTINE_S,
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
            stale_prime_after_s: Seconds without a published ``ParamUpdate`` after which
                the poll REST-primes even if Socket.IO still reports up (zombie session).
                Use ``0`` to disable stale-session priming.
            zombie_hard_restart_after: Consecutive zombie REST-primes before forcing a
                hard Socket.IO restart (SPA parity: reconnect then ``modules.connect`` +
                REST parameters). Use ``0`` to only REST-prime without tearing down WS.
            zombie_full_recycle_after: Consecutive hard restarts without live WS
                ``ParamUpdate`` traffic before a full disconnect → connect → resubscribe
                cycle. Use ``0`` to never escalate beyond hard restart.
            zombie_rebuild_after: Consecutive recycles without live traffic before
                rebuilding ``RealtimeManager`` (new Socket.IO client). Use ``0`` to
                never escalate beyond recycle.
            zombie_recovery_cooldown_s: Base seconds to skip WS recovery after a
                recycle/rebuild (exponential backoff, capped). REST primes still run.
            zombie_quarantine_after: RealtimeManager rebuilds without live traffic
                before REST-only quarantine. Use ``0`` to disable quarantine.
            zombie_quarantine_s: Seconds to skip WS recovery while quarantined
                (REST primes still run). Use ``0`` to disable the pause duration.
        """
        self.object_id = int(object_id)
        self.modules = sorted(set(modules))

        self.api: ApiClient = api
        self.ws: RealtimeManagerClient | None = ws
        self._owns_ws = ws is None
        self.bus = EventBus()

        self._owns_api = owns_api
        self._connectivity_poll_interval = float(connectivity_poll_interval)
        self._stale_prime_after_s = float(stale_prime_after_s)
        self._zombie_hard_restart_after = int(zombie_hard_restart_after)
        self._zombie_full_recycle_after = int(zombie_full_recycle_after)
        self._zombie_rebuild_after = int(zombie_rebuild_after)
        self._zombie_recovery_cooldown_s = float(zombie_recovery_cooldown_s)
        self._zombie_quarantine_after = int(zombie_quarantine_after)
        self._zombie_quarantine_s = float(zombie_quarantine_s)
        self._zombie_prime_streak = 0
        self._zombie_hard_restart_streak = 0
        self._zombie_recycle_streak = 0
        self._zombie_rebuild_count = 0
        self._zombie_recovery_cooldown_until: float | None = None
        self._zombie_quarantine_until: float | None = None
        self._zombie_module_online_recovery_inflight = False
        self._zombie_last_module_online_recovery_monotonic: float | None = None
        self._resubscribe_lock = asyncio.Lock()
        self._bound_ns_sid: str | None = None
        self._last_param_publish_monotonic: float | None = None
        self._last_live_param_publish_monotonic: float | None = None

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
        self._on_cloud_session: list[CloudSessionCb] = []
        self._on_alarm_quantity: list[AlarmQuantityCb] = []

        # Module↔cloud (REST/WS connectedAt) vs library↔cloud (Socket.IO session).
        # The session bit never forces module offline (SPA parity).
        self._ws_session_up = False
        self._ws_hooks_registered = False
        self._connectivity_generation = 0
        self._module_connected_at: dict[str, int] = {}
        self._module_online: dict[str, bool] = {}
        self._module_gateway: dict[str, dict[str, Any]] = {}
        # Outage clocks (monotonic for duration, wall for down_since attributes).
        self._cloud_down_since_mono: float | None = None
        self._cloud_down_since_wall: float | None = None
        self._cloud_down_reason: CloudOutageReason | None = None
        self._cloud_last_down_for_s: float | None = None
        self._cloud_last_reason: CloudOutageReason | None = None
        self._module_down_since_mono: dict[str, float] = {}
        self._module_down_since_wall: dict[str, float] = {}
        self._module_down_reason: dict[str, ModuleOutageReason] = {}
        self._module_last_down_for_s: dict[str, float] = {}
        self._module_last_reason: dict[str, ModuleOutageReason] = {}
        self._alarm_quantity_cache: dict[str, int | None] = {}
        self._alarm_quantity_ws_rev: dict[str, int] = {}
        self._alarm_quantity_ingest_lock = asyncio.Lock()
        self._alarm_quantity_rest_seq = 0
        self._alarm_quantity_rest_applied_seq = 0
        self._alarm_quantity_rest_seq_lock = asyncio.Lock()

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
        """Register callback for module↔cloud online/offline (SPA ``connectedAt``).

        Callbacks receive :class:`ModuleConnectivity`. This path is intentionally
        separate from :attr:`bus` so ``ParamUpdate`` subscribers stay unchanged.
        Offline modules are observed only — the client cannot repair plant↔cloud links.
        """
        self._on_module_connectivity.append(cb)

    def on_cloud_session(self, cb: CloudSessionCb) -> None:
        """Register callback for library↔cloud Socket.IO session up/down.

        Callbacks receive :class:`CloudSessionConnectivity`. Distinct from
        :meth:`on_module_connectivity`: a dropped client session must self-heal and
        stay detectable without looking like a module went offline.
        """
        self._on_cloud_session.append(cb)

    def on_alarm_quantity(self, cb: AlarmQuantityCb) -> None:
        """Register callback for per-module alarm count changes.

        Callbacks receive :class:`~pybragerone.models.events.AlarmQuantityChanged`
        when REST prime or Socket.IO ``app:modules:alarms:quantity:change`` reports
        a new count for a subscribed module.
        """
        self._on_alarm_quantity.append(cb)

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

    def ws_session_up(self) -> bool:
        """Return whether this gateway's Socket.IO (library↔cloud) session is up."""
        return self._ws_session_up

    def _is_running(self) -> bool:
        """Return whether the gateway lifecycle is active (not stopped)."""
        return self._started

    def last_param_update_age_s(self) -> float | None:
        """Return seconds since the last published ``ParamUpdate``, or ``None`` if never."""
        stamped = self._last_param_publish_monotonic
        if stamped is None:
            return None
        return time.monotonic() - stamped

    def last_live_param_update_age_s(self) -> float | None:
        """Return seconds since the last live (WS) ``ParamUpdate``, or ``None`` if never."""
        stamped = self._last_live_param_publish_monotonic
        if stamped is None:
            return None
        return time.monotonic() - stamped

    async def start(self) -> None:
        """Start the whole flow (idempotent)."""
        if self._started:
            return
        self._started = True
        started_at = time.monotonic()

        # 1) WS connect
        if self.ws is None:
            self.ws = self._make_realtime_manager()
            self._owns_ws = True
        ws = self.ws
        if ws is None:
            raise RuntimeError("RealtimeManager is not initialized")
        ws.on_event(self._ws_dispatch)
        await ws.connect()
        await self._set_ws_session_up(True, source="connect")
        if not self._ws_hooks_registered:
            ws.add_on_connected(self._on_ws_connected)
            ws.add_on_disconnected(self._on_ws_disconnected)
            self._ws_hooks_registered = True
        ws_connected_at = time.monotonic()

        # 3) modules.connect binds the current WS session with modules
        sid_ns = ws.sid()
        sid_engine = ws.engine_sid()
        if not sid_ns:
            raise RuntimeError("No namespace SID after connecting to WS (Socket.IO).")

        ok = await self.api.modules_connect(sid_ns, self.modules, group_id=self.object_id, engine_sid=sid_engine)
        if ok:
            LOG.info("modules.connect: %s (ns_sid=%s, engine_sid=%s)", ok, sid_ns, sid_engine)
            self._bound_ns_sid = sid_ns
        else:
            LOG.warning("modules.connect failed (ns_sid=%s, engine_sid=%s)", sid_ns, sid_engine)
            self._bound_ns_sid = None
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
        self._connectivity_generation += 1

        # 1) disconnect WS first so disconnect hooks see ``_started is False`` and skip work.
        try:
            if self.ws is not None:
                await self.ws.disconnect()
        except asyncio.CancelledError:
            # Shutdown must continue even if disconnect is cancelled mid-flight.
            pass  # intentionally ignore: CancelledError is expected during stop()
        except Exception:
            LOG.exception("Error while disconnecting WS")
        finally:
            await self._set_ws_session_up(False, source="stop")

        # 2) Cancel background tasks (including anything spawned by disconnect).
        try:
            await self._cancel_all_tasks()
        except Exception:
            LOG.exception("Error while canceling background tasks")

        # 3) close the HTTP client (if the gateway manages it)
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

    # ------------------------- Connectivity -------------------------

    # ------------------------- PRIME & ingest -------------------------

    async def ingest_prime_parameters(self, data: dict[str, Any]) -> None:
        """Treat /modules/parameters prime as "cold snapshot" and publish all pairs."""
        pairs = list(self.flatten_parameters(data, source="prime"))
        self._touch_param_publish(len(pairs))

        async def _pub_all() -> None:
            for upd in pairs:
                await self.bus.publish(upd)

        await _pub_all()

    async def ingest_activity_quantity(self, data: dict[str, Any] | None) -> None:
        """Ingest /modules/activity/quantity prime (optional)."""
        if isinstance(data, dict):
            LOG.debug("activityQuantity: %s", data.get("activityQuantity"))

    async def ingest_alarm_quantity(
        self,
        data: dict[str, Any] | None,
        *,
        source: Literal["rest", "ws"] = "rest",
        ws_floor: dict[str, int] | None = None,
        rest_seq: int | None = None,
    ) -> None:
        """Ingest alarm quantity payload and notify ``on_alarm_quantity`` listeners."""
        async with self._alarm_quantity_ingest_lock:
            if source == "rest" and rest_seq is not None and rest_seq < self._alarm_quantity_rest_applied_seq:
                return
            await self._ingest_alarm_quantity_payload(data, source=source, ws_floor=ws_floor)
            if source == "rest" and rest_seq is not None:
                self._alarm_quantity_rest_applied_seq = rest_seq

    async def _ingest_alarm_quantity_payload(
        self,
        data: dict[str, Any] | None,
        *,
        source: Literal["rest", "ws"],
        ws_floor: dict[str, int] | None = None,
    ) -> None:
        if not isinstance(data, dict):
            return
        qty_map = data.get("alarmsQuantity")
        if not isinstance(qty_map, dict):
            return
        wanted = set(self.modules)
        for raw_devid, raw_qty in qty_map.items():
            devid = str(raw_devid)
            if devid not in wanted:
                continue
            if source == "rest" and ws_floor is not None and self._alarm_quantity_ws_rev.get(devid, 0) > ws_floor.get(devid, 0):
                continue
            try:
                quantity = _parse_alarm_quantity(raw_qty)
            except ValueError:
                LOG.debug("Ignoring non-numeric alarmsQuantity for devid=%s: %r", devid, raw_qty)
                continue
            if source == "ws":
                self._alarm_quantity_ws_rev[devid] = self._alarm_quantity_ws_rev.get(devid, 0) + 1
            previous = self._alarm_quantity_cache.get(devid)
            changed = previous != quantity
            self._alarm_quantity_cache[devid] = quantity
            if not changed:
                continue
            event = AlarmQuantityChanged(devid=devid, quantity=quantity, source=source, changed=True)
            if self._on_alarm_quantity:
                await self._invoke_list(self._on_alarm_quantity, event)

    # ------------------------- WS dispatch -------------------------

    async def _invoke_list(self, cbs: list[Callable[..., Any]], *args: Any, **kwargs: Any) -> None:
        for cb in list(cbs):
            try:
                res = cb(*args, **kwargs)
                if asyncio.iscoroutine(res):
                    # Bind the discarded None so CodeQL does not treat bare ``await`` as ineffectual.
                    _ = await res
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
            self._touch_param_publish(len(pairs), live=True)

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
            self._touch_param_publish(len(pairs), live=True)

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

        # alarms:quantity:change
        if event_name.endswith("alarms:quantity:change") and isinstance(payload, dict):

            async def _alarms_quantity_changed() -> None:
                await self.ingest_alarm_quantity(payload, source="ws")

            self._spawn(_alarms_quantity_changed(), name="gateway.ingest_alarm_quantity")
            return None

        # SPA Layout/ObjectsLayout: EventChannel 0x16 → REST /modules/parameters for devid.
        if event_name == MODULE_MEMORY_UPDATED and isinstance(payload, dict):
            devid = payload.get("devid")
            if isinstance(devid, str) and devid:

                async def _memory_updated_prime() -> None:
                    try:
                        ok = await self._prime_devids([devid])
                        LOG.debug("memory-updated REST prime devid=%s ok=%s", devid, ok)
                    except Exception as err:
                        if _is_http_timeout_error(err) or _is_api_dispatch_timeout(err) or is_expected_upstream_unavailable(err):
                            LOG.warning(
                                "memory-updated REST prime failed (expected): devid=%s reason=%s",
                                devid,
                                format_expected_failure_reason(err),
                            )
                        else:
                            LOG.exception("memory-updated REST prime failed for devid=%s", devid)

                self._spawn(_memory_updated_prime(), name="gateway.memory_updated_prime")
            return None

        # SPA Layout handler: Object.entries(payload) → module.connectedAt / gateway
        if event_name == MODULE_CONNECTION_STATUS_CHANGED and isinstance(payload, dict):
            self._spawn(
                self._ingest_module_connection_status(payload),
                name="gateway.module_connection_status",
            )
        return None

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
