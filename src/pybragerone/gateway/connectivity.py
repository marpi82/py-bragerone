"""Module and cloud-session connectivity tracking for BragerOneGateway."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ..api.client import format_expected_failure_reason, is_expected_upstream_unavailable
from ..models.events import CloudSessionConnectivity, ModuleConnectivity
from .helpers import (
    CloudSessionSource,
    ConnectivitySource,
    _as_cloud_outage_reason,
    _as_module_outage_reason,
    _cloud_outage_reason_from_source,
    _gateway_as_dict,
    _is_api_dispatch_timeout,
    _is_http_timeout_error,
    _parse_connected_at,
    module_connected_at_means_online,
)

LOG = logging.getLogger(__name__)


class ConnectivityMixin:
    """Mixin providing connectivity behavior for BragerOneGateway."""

    # Attributes owned by BragerOneGateway.__init__
    _bound_ns_sid: str | None
    _cloud_down_reason: Any
    _cloud_down_since_mono: float | None
    _cloud_down_since_wall: float | None
    _cloud_last_down_for_s: float | None
    _cloud_last_reason: Any
    _connectivity_generation: int
    _connectivity_poll_interval: float
    _module_connected_at: dict[str, int]
    _module_down_reason: dict[str, Any]
    _module_down_since_mono: dict[str, float]
    _module_down_since_wall: dict[str, float]
    _module_gateway: dict[str, dict[str, Any]]
    _module_last_down_for_s: dict[str, float]
    _module_last_reason: dict[str, Any]
    _module_online: dict[str, bool]
    _on_cloud_session: list[Any]
    _on_module_connectivity: list[Any]
    _stale_prime_after_s: float
    _started: bool
    _ws_session_up: bool
    _zombie_hard_restart_after: int
    _zombie_prime_streak: int
    api: Any
    modules: list[str]
    object_id: int

    def cloud_session_outage(self) -> dict[str, float | str | None]:
        """Return cloud-session outage snapshot for diagnostics / HA attributes.

        Keys: ``down_since``, ``down_for_s``, ``reason``, ``last_down_for_s``,
        ``last_reason``. ``reason`` is the client observation source
        (``disconnect`` / ``stop``), not plant hardware diagnostics.
        """
        return self._cloud_outage_snapshot()

    def module_outage(self, devid: str) -> dict[str, float | str | None]:
        """Return module↔cloud outage snapshot for *devid*.

        Same keys as :meth:`cloud_session_outage`. ``reason`` is the observation
        ``source`` (``rest`` / ``ws`` / ``derived``).
        """
        return self._module_outage_snapshot(devid)

    async def refresh_module_connectivity(self) -> None:
        """Refresh module↔cloud connectivity from REST ``get_modules``."""
        await self._refresh_module_connectivity(source="rest")

    def _finalize_cloud_outage_at_stop(self) -> None:
        """Close an active cloud outage into ``last_*`` without a restore log.

        Used when ``stop()`` runs while the session is already down so a later
        ``start()``→connect does not report downtime that includes intentional stop.
        """
        if self._cloud_down_since_mono is None:
            return
        duration = max(0.0, time.monotonic() - self._cloud_down_since_mono)
        self._cloud_last_down_for_s = duration
        self._cloud_last_reason = self._cloud_down_reason or "stop"
        self._cloud_down_since_mono = None
        self._cloud_down_since_wall = None
        self._cloud_down_reason = None

    def _clear_active_cloud_outage(self) -> None:
        """Drop a live outage window without updating ``last_*``."""
        self._cloud_down_since_mono = None
        self._cloud_down_since_wall = None
        self._cloud_down_reason = None

    async def _set_ws_session_up(self, up: bool, *, source: CloudSessionSource) -> None:
        """Update library↔cloud session cache and notify listeners on flips."""
        previous = self._ws_session_up
        self._ws_session_up = up
        changed = previous is not up
        if not changed:
            # stop() while already down: close the active window at the stop boundary.
            if source == "stop" and not up:
                self._finalize_cloud_outage_at_stop()
            return
        if not up:
            self._cloud_down_since_mono = time.monotonic()
            self._cloud_down_since_wall = time.time()
            self._cloud_down_reason = _cloud_outage_reason_from_source(source)
        elif self._cloud_down_since_mono is not None:
            duration = max(0.0, time.monotonic() - self._cloud_down_since_mono)
            ended_reason = self._cloud_down_reason or _cloud_outage_reason_from_source(source)
            self._cloud_last_down_for_s = duration
            self._cloud_last_reason = ended_reason
            LOG.warning(
                "Cloud session restored after %.1fs (reason=%s, source=%s)",
                duration,
                ended_reason,
                source,
            )
            self._cloud_down_since_mono = None
            self._cloud_down_since_wall = None
            self._cloud_down_reason = None
        snapshot = self._cloud_outage_snapshot()
        event = CloudSessionConnectivity(
            up=up,
            source=source,
            changed=True,
            down_since=snapshot["down_since"] if isinstance(snapshot["down_since"], float) else None,
            down_for_s=snapshot["down_for_s"] if isinstance(snapshot["down_for_s"], float) else None,
            reason=_as_cloud_outage_reason(snapshot["reason"]),
            last_down_for_s=snapshot["last_down_for_s"] if isinstance(snapshot["last_down_for_s"], float) else None,
            last_reason=_as_cloud_outage_reason(snapshot["last_reason"]),
        )
        LOG.info("Cloud session: up=%s source=%s", up, source)
        if self._on_cloud_session:
            await self._invoke_list(self._on_cloud_session, event)
        # up→stop: notify with a momentary down snapshot, then drop the live window
        # so restart cannot inherit it (do not clobber prior-cycle last_* with ~0s).
        if source == "stop" and not up:
            self._clear_active_cloud_outage()

    def _cloud_outage_snapshot(self) -> dict[str, float | str | None]:
        """Build the current cloud-session outage attribute dict."""
        down_since = self._cloud_down_since_wall
        down_for_s: float | None = None
        reason = self._cloud_down_reason
        if self._cloud_down_since_mono is not None:
            down_for_s = max(0.0, time.monotonic() - self._cloud_down_since_mono)
        return {
            "down_since": down_since,
            "down_for_s": down_for_s,
            "reason": reason,
            "last_down_for_s": self._cloud_last_down_for_s,
            "last_reason": self._cloud_last_reason,
        }

    def _module_outage_snapshot(self, devid: str) -> dict[str, float | str | None]:
        """Build the current module outage attribute dict for *devid*."""
        down_since = self._module_down_since_wall.get(devid)
        down_for_s: float | None = None
        mono = self._module_down_since_mono.get(devid)
        if mono is not None:
            down_for_s = max(0.0, time.monotonic() - mono)
        return {
            "down_since": down_since,
            "down_for_s": down_for_s,
            "reason": self._module_down_reason.get(devid),
            "last_down_for_s": self._module_last_down_for_s.get(devid),
            "last_reason": self._module_last_reason.get(devid),
        }

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
        self._bound_ns_sid = None
        if not self._started:
            return
        if not self._ws_session_up:
            return
        # Bump generation so any stale disconnect work cannot clobber a reconnect.
        self._connectivity_generation += 1
        # Keep last connectedAt; REST poll / reconnect refresh remains authoritative.
        await self._set_ws_session_up(False, source="disconnect")

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
                elif self._zombie_recovery_in_quarantine():
                    LOG.debug(
                        "No live ParamUpdate for %.0fs while Socket.IO reports up; REST-priming during zombie quarantine",
                        age,
                    )
                elif self._zombie_recovery_in_cooldown():
                    # REST-prime only: do not grow the escalation streak or WARN-spam.
                    # Field logs showed streak climbing through cooldown so the first
                    # post-cooldown tick immediately hard-reconnected.
                    LOG.debug(
                        "No live ParamUpdate for %.0fs while Socket.IO reports up; REST-priming during zombie recovery cooldown",
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
        if online_changed:
            if not online:
                self._module_down_since_mono[devid] = time.monotonic()
                self._module_down_since_wall[devid] = time.time()
                self._module_down_reason[devid] = source
            elif devid in self._module_down_since_mono:
                duration = max(0.0, time.monotonic() - self._module_down_since_mono[devid])
                ended_reason = self._module_down_reason.get(devid, source)
                self._module_last_down_for_s[devid] = duration
                self._module_last_reason[devid] = ended_reason
                LOG.warning(
                    "Module connectivity restored after %.1fs (devid=%s reason=%s source=%s)",
                    duration,
                    devid,
                    ended_reason,
                    source,
                )
                self._module_down_since_mono.pop(devid, None)
                self._module_down_since_wall.pop(devid, None)
                self._module_down_reason.pop(devid, None)
        snapshot = self._module_outage_snapshot(devid)
        event = ModuleConnectivity(
            devid=devid,
            online=online,
            source=source,
            connected_at=self._module_connected_at.get(devid),
            gateway=self.module_gateway(devid),
            online_changed=online_changed,
            metadata_changed=metadata_changed,
            down_since=snapshot["down_since"] if isinstance(snapshot["down_since"], float) else None,
            down_for_s=snapshot["down_for_s"] if isinstance(snapshot["down_for_s"], float) else None,
            reason=_as_module_outage_reason(snapshot["reason"]),
            last_down_for_s=snapshot["last_down_for_s"] if isinstance(snapshot["last_down_for_s"], float) else None,
            last_reason=_as_module_outage_reason(snapshot["last_reason"]),
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
        if online_changed and online and devid in self.modules:
            await self._maybe_recover_after_module_online(devid)

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
