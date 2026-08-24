"""Gateway: WS connect → modules.connect → listen → prime.

Maintains the WS connection and emits ParamUpdate events on the EventBus.
Does not contain heavy logic (such as mapping) internally — this is the role of ParamStore/HA.

Connectivity is two layers, both off the ParamUpdate EventBus:

* **Module ↔ cloud** — SPA ``connectedAt`` via ``on_module_connectivity`` (observe/wait).
* **Library ↔ cloud** — Socket.IO session via ``on_cloud_session`` (detect + self-heal).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from typing import Any, Literal, Protocol

from .api import BragerOneApiClient, RealtimeManager, ServerConfig
from .api.client import ApiError, format_expected_failure_reason, is_expected_upstream_unavailable
from .models.api.modules import Module
from .models.events import (
    MODULE_CONNECTION_STATUS_CHANGED,
    MODULE_MEMORY_UPDATED,
    CloudSessionConnectivity,
    EventBus,
    ModuleConnectivity,
    ParamUpdate,
)

LOG = logging.getLogger(__name__)

# Default REST poll interval for module connectedAt refresh (seconds).
_DEFAULT_CONNECTIVITY_POLL_INTERVAL_S = 60.0
# REST-prime when no ParamUpdate has been published for this long while WS claims up.
_DEFAULT_STALE_PRIME_AFTER_S = 180.0
# After this many consecutive zombie REST-primes, force a hard WS restart (SPA-style
# reconnect → modules.connect + REST parameters). ``0`` disables hard restart.
_DEFAULT_ZOMBIE_HARD_RESTART_AFTER = 2
# After this many hard restarts without live WS ``ParamUpdate`` traffic, drop and
# reopen the Socket.IO session (full disconnect → connect → resubscribe). ``0`` disables.
_DEFAULT_ZOMBIE_FULL_RECYCLE_AFTER = 3

ConnectivitySource = Literal["rest", "ws", "derived"]
CloudSessionSource = Literal["connect", "disconnect", "stop"]

# Callback signatures
ParametersCb = Callable[[str, dict[str, Any]], Awaitable[None] | None]  # (event_name, payload)
SnapshotCb = Callable[[dict[str, Any]], Awaitable[None] | None]
GenericCb = Callable[[str, Any], Awaitable[None] | None]
ModuleConnectivityCb = Callable[[ModuleConnectivity], Awaitable[None] | None]
CloudSessionCb = Callable[[CloudSessionConnectivity], Awaitable[None] | None]


def module_connected_at_means_online(connected_at: int) -> bool:
    """Return whether a ``connectedAt`` value means the module is online.

    Mirrors the SPA ternary ``connectedAt ? 'connected' : 'notConnected'``.
    Upstream uses ``0`` as the offline sentinel (see fixtures and live payloads).
    """
    return int(connected_at) != 0


def _parse_connected_at(raw: Any) -> int | None:
    """Parse a connectedAt value; return ``None`` when missing/unusable."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _gateway_as_dict(gateway_obj: Any) -> dict[str, Any] | None:
    """Normalize a Module.gateway / WS gateway blob to a plain dict."""
    if gateway_obj is None:
        return None
    dump = getattr(gateway_obj, "model_dump", None)
    if callable(dump):
        raw = dump(mode="json")
        return dict(raw) if isinstance(raw, dict) else None
    if isinstance(gateway_obj, dict):
        return dict(gateway_obj)
    return None


def _is_http_timeout_error(err: Exception) -> bool:
    """Return whether *err* is an HTTP timeout surfaced by httpx/httpcore."""
    module = getattr(type(err), "__module__", "")
    if not (module.startswith("httpx") or module.startswith("httpcore")):
        return False
    return err.__class__.__name__ in {
        "TimeoutException",
        "ReadTimeout",
        "ConnectTimeout",
        "WriteTimeout",
        "PoolTimeout",
    }


def _is_api_dispatch_timeout(err: Exception) -> bool:
    """Return whether *err* is an upstream API timeout response."""
    if not isinstance(err, ApiError) or err.status != 408:
        return False
    data = err.data
    if not isinstance(data, dict):
        return False
    status = data.get("status")
    return isinstance(status, str) and status == "E_DISPATCH_EVENT_TIMEOUT"


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
        raise NotImplementedError

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
        raise NotImplementedError

    def sid(self) -> str | None:  # noqa: D102
        raise NotImplementedError

    def engine_sid(self) -> str | None:  # noqa: D102
        raise NotImplementedError

    async def subscribe(self, modules: list[str]) -> None:  # noqa: D102
        raise NotImplementedError

    async def force_reconnect(self) -> None:  # noqa: D102
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
        """
        self.object_id = int(object_id)
        self.modules = sorted(set(modules))

        self.api: ApiClient = api
        self.ws: RealtimeManagerClient | None = ws
        self.bus = EventBus()

        self._owns_api = owns_api
        self._connectivity_poll_interval = float(connectivity_poll_interval)
        self._stale_prime_after_s = float(stale_prime_after_s)
        self._zombie_hard_restart_after = int(zombie_hard_restart_after)
        self._zombie_full_recycle_after = int(zombie_full_recycle_after)
        self._zombie_prime_streak = 0
        self._zombie_hard_restart_streak = 0
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

        # Module↔cloud (REST/WS connectedAt) vs library↔cloud (Socket.IO session).
        # The session bit never forces module offline (SPA parity).
        self._ws_session_up = False
        self._ws_hooks_registered = False
        self._connectivity_generation = 0
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

    def _zombie_param_update_age_s(self) -> float | None:
        """Age used for zombie-session detection.

        After the first live WS publish, REST-only snapshots no longer mask a dead
        push stream. Before any live traffic, fall back to any published update age.
        """
        live_age = self.last_live_param_update_age_s()
        if live_age is not None:
            return live_age
        return self.last_param_update_age_s()

    def _any_subscribed_module_online(self) -> bool:
        """Return whether recovery should run (unknown connectivity counts as online)."""
        known = [self._module_online.get(devid) for devid in self.modules if devid in self._module_online]
        if not known:
            return True
        return any(known)

    def _touch_param_publish(self, count: int, *, live: bool = False) -> None:
        """Record that ``count`` parameter events were published.

        Args:
            count: Number of ``ParamUpdate`` events published.
            live: When ``True`` (WS snapshot / parameters:change), clear zombie recovery
                streaks. REST primes update the overall age for diagnostics but must not
                mask a silent WS push stream once live traffic has been observed.
        """
        if count <= 0:
            return
        now = time.monotonic()
        self._last_param_publish_monotonic = now
        if live:
            self._last_live_param_publish_monotonic = now
            self._zombie_prime_streak = 0
            self._zombie_hard_restart_streak = 0

    async def refresh_module_connectivity(self) -> None:
        """Refresh module↔cloud connectivity from REST ``get_modules``."""
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

    async def _fresh_ws_token(self) -> str:
        """Return a valid token for a WS (re)connect, re-authenticating if expired."""
        api = self.api
        if not isinstance(api, BragerOneApiClient):
            return api.access_token
        await api.ensure_auth()
        return api.access_token

    async def _set_ws_session_up(self, up: bool, *, source: CloudSessionSource) -> None:
        """Update library↔cloud session cache and notify listeners on flips."""
        previous = self._ws_session_up
        self._ws_session_up = up
        changed = previous is not up
        if not changed:
            return
        event = CloudSessionConnectivity(up=up, source=source, changed=True)
        LOG.info("Cloud session: up=%s source=%s", up, source)
        if self._on_cloud_session:
            await self._invoke_list(self._on_cloud_session, event)

    async def _on_ws_connected(self) -> None:
        """Re-bind modules after WS reconnect, then refresh connectedAt from REST."""
        if not self._started:
            return
        await self._set_ws_session_up(True, source="connect")
        generation = self._connectivity_generation
        try:
            await self.resubscribe()
        except Exception:
            LOG.exception("WS resubscribe failed after reconnect")
        finally:
            if self._started and generation == self._connectivity_generation:
                await self._refresh_module_connectivity(source="rest")

    async def _on_ws_disconnected(self) -> None:
        """Mark library↔cloud Socket.IO down without forcing module offline.

        During :meth:`stop` (``_started`` already cleared) leave the session bit
        for the ``source="stop"`` notification so consumers still see a down event.
        """
        if not self._started:
            return
        if not self._ws_session_up:
            return
        # Bump generation so any stale disconnect work cannot clobber a reconnect.
        self._connectivity_generation += 1
        # Keep last connectedAt; REST poll / reconnect refresh remains authoritative.
        await self._set_ws_session_up(False, source="disconnect")

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
            try:
                await self._refresh_module_connectivity(source="rest")
            except Exception:
                LOG.exception("Connectivity poll tick failed")
            # ParamUpdates are WS deltas. REST-prime when the socket is down, or when
            # the session still reports up but no parameter events have arrived (zombie
            # Engine.IO abort that skipped the Socket.IO disconnect callback). After
            # several consecutive zombie primes, force a hard WS restart — the SPA
            # recovers via Socket.IO reconnect then ModulesService.connect + REST
            # parameters; our supervisor only reconnects when ``connected`` looks down.
            if not self._started:
                continue
            age = self._zombie_param_update_age_s()
            stale_after = self._stale_prime_after_s
            session_up = self._ws_session_up
            if session_up:
                if stale_after <= 0 or age is None or age < stale_after:
                    continue
                if not self._any_subscribed_module_online():
                    LOG.debug(
                        "Skipping zombie WS recovery while all subscribed modules are offline (age=%.0fs)",
                        age,
                    )
                else:
                    self._zombie_prime_streak += 1
                    LOG.warning(
                        "No live ParamUpdate for %.0fs while Socket.IO reports up; REST-priming (zombie_streak=%s)",
                        age,
                        self._zombie_prime_streak,
                    )
                    hard_after = self._zombie_hard_restart_after
                    if hard_after > 0 and self._zombie_prime_streak >= hard_after:
                        streak = self._zombie_prime_streak
                        self._zombie_prime_streak = 0
                        await self._recover_zombie_session(streak)
            try:
                await self._prime_with_retry()
            except Exception as err:
                if _is_http_timeout_error(err) or _is_api_dispatch_timeout(err) or is_expected_upstream_unavailable(err):
                    LOG.warning(
                        "REST re-prime failed due to expected upstream outage/timeout; will retry (reason=%s)",
                        format_expected_failure_reason(err),
                    )
                else:
                    LOG.exception("REST re-prime (socket down or stale ParamUpdates) failed")

    async def _recover_zombie_session(self, rest_prime_streak: int) -> None:
        """Escalate zombie-session recovery: hard reconnect, then full recycle."""
        ws = self.ws
        if ws is None:
            LOG.warning(
                "Zombie session persists after %s REST-primes; no WS client, REST-priming only",
                rest_prime_streak,
            )
            return

        full_recycle_after = self._zombie_full_recycle_after
        if full_recycle_after > 0 and self._zombie_hard_restart_streak >= full_recycle_after:
            await self._recycle_realtime_session(rest_prime_streak)
            return

        self._zombie_hard_restart_streak += 1
        LOG.warning(
            "Zombie session persists after %s REST-primes; forcing WS hard reconnect (hard_streak=%s)",
            rest_prime_streak,
            self._zombie_hard_restart_streak,
        )
        try:
            await ws.force_reconnect()
            # ``force_reconnect`` may spawn ``on_connected`` work; await resubscribe so
            # ``modules.connect`` + subscribe + prime finish before the next poll tick.
            await self.resubscribe()
        except Exception:
            LOG.exception("WS hard reconnect (zombie session) failed")

    async def _recycle_realtime_session(self, rest_prime_streak: int) -> None:
        """Drop and reopen Socket.IO after repeated failed hard reconnects."""
        ws = self.ws
        if ws is None or not self._is_running():
            return
        LOG.warning(
            "Zombie session persists after %s REST-primes and %s hard reconnect(s) "
            "without live ParamUpdates; recycling realtime session",
            rest_prime_streak,
            self._zombie_hard_restart_streak,
        )
        self._zombie_hard_restart_streak = 0
        self._zombie_prime_streak = 0
        try:
            await ws.disconnect()
        except Exception:
            LOG.exception("WS disconnect during realtime recycle failed")
        if not self._is_running():
            return
        try:
            await ws.connect()
            await self.resubscribe()
        except Exception:
            LOG.exception("WS recycle (connect/resubscribe) failed")

    async def _refresh_module_connectivity(self, *, source: ConnectivitySource) -> None:
        """Pull ``get_modules`` and apply online state for subscribed devids.

        A failed or empty fetch does **not** mark every module offline — that would
        turn HTTP errors / empty payloads into false plant-wide outages.
        """
        if not self._started:
            return
        try:
            rows = await self.api.get_modules(self.object_id)
        except Exception as err:
            if _is_http_timeout_error(err) or _is_api_dispatch_timeout(err) or is_expected_upstream_unavailable(err):
                # Upstream hiccups are expected from time to time; keep last known
                # module states and avoid flooding logs with traceback noise.
                LOG.warning(
                    "get_modules unavailable/timeout during connectivity refresh; "
                    "keeping previous module state (source=%s, reason=%s)",
                    source,
                    format_expected_failure_reason(err),
                )
            else:
                LOG.exception("get_modules failed during connectivity refresh")
            return

        rows_list = list(rows)
        wanted = set(self.modules)
        seen: set[str] = set()
        for row in rows_list:
            devid = str(getattr(row, "devid", "") or "")
            if not devid or devid not in wanted:
                continue
            connected_at = _parse_connected_at(getattr(row, "connectedAt", None))
            if connected_at is None:
                LOG.warning("Skipping connectivity row with unusable connectedAt for devid=%s", devid)
                continue
            seen.add(devid)
            await self._apply_connectivity(
                devid=devid,
                online=module_connected_at_means_online(connected_at),
                source=source,
                connected_at=connected_at,
                gateway=_gateway_as_dict(getattr(row, "gateway", None)),
            )

        # Only derive offline for missing devids when the listing contained at least
        # one recognised subscribed module (avoids treating [] / odd shapes as wipe).
        if not seen:
            if wanted:
                LOG.warning(
                    "get_modules returned no recognised subscribed modules (wanted=%s); skipping derived offline",
                    sorted(wanted),
                )
            return

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
        """Update cache and notify listeners when online or metadata changes."""
        previous_online = self._module_online.get(devid)
        previous_connected_at = self._module_connected_at.get(devid)
        previous_gateway = self._module_gateway.get(devid)

        if connected_at is not None:
            self._module_connected_at[devid] = int(connected_at)
        if gateway is not None:
            self._module_gateway[devid] = dict(gateway)

        online_changed = previous_online is not online
        metadata_changed = (connected_at is not None and connected_at != previous_connected_at) or (
            gateway is not None and gateway != previous_gateway
        )
        if not online_changed and not metadata_changed:
            return

        self._module_online[devid] = online
        event = ModuleConnectivity(
            devid=devid,
            online=online,
            source=source,
            connected_at=self._module_connected_at.get(devid),
            gateway=self.module_gateway(devid),
            online_changed=online_changed,
            metadata_changed=metadata_changed,
        )
        LOG.info(
            "Module connectivity: devid=%s online=%s source=%s connectedAt=%s online_changed=%s metadata_changed=%s",
            devid,
            online,
            source,
            event.connected_at,
            online_changed,
            metadata_changed,
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
        self._touch_param_publish(len(pairs))

        async def _pub_all() -> None:
            for upd in pairs:
                await self.bus.publish(upd)

        await _pub_all()

    async def _prime_devids(self, devids: list[str]) -> bool:
        """REST-prime parameters for a subset of subscribed modules (SPA memory-updated)."""
        subscribed = set(self.modules)
        wanted = sorted({devid for devid in devids if devid in subscribed})
        if not wanted:
            return False
        res = await self.api.modules_parameters_prime(wanted, return_data=True)
        if isinstance(res, tuple) and len(res) == 2:
            status, data = res
            if status in (200, 204) and isinstance(data, dict):
                await self.ingest_prime_parameters(data)
                return True
        return False

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

    async def _ingest_module_connection_status(self, payload: dict[str, Any]) -> None:
        """Apply SPA ``app:module:connection:status:changed`` payloads per devid."""
        if not self._started:
            return
        wanted = set(self.modules)
        for raw_devid, body in payload.items():
            devid = str(raw_devid or "")
            if not devid or devid not in wanted or not isinstance(body, dict):
                continue
            gateway = _gateway_as_dict(body.get("gateway"))
            has_connected_at = "connectedAt" in body or "connected_at" in body
            if not has_connected_at:
                # Gateway-only update: refresh metadata without inventing an offline bit.
                if gateway is None:
                    continue
                previous_online = self._module_online.get(devid)
                if previous_online is None:
                    continue
                await self._apply_connectivity(
                    devid=devid,
                    online=previous_online,
                    source="ws",
                    connected_at=None,
                    gateway=gateway,
                )
                continue
            connected_at = _parse_connected_at(body.get("connectedAt", body.get("connected_at")))
            if connected_at is None:
                LOG.warning("Ignoring connection status event with bad connectedAt for devid=%s", devid)
                continue
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
