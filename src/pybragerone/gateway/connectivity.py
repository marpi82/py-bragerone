"""Module and cloud-session connectivity tracking for BragerOneGateway."""

from __future__ import annotations

import asyncio
import logging
import time
import types
import uuid
from dataclasses import replace
from typing import Any

from ..api.client import format_expected_failure_reason, is_expected_upstream_unavailable
from ..models.events import (
    CloudOutageReason,
    CloudSessionConnectivity,
    ConnectivityEpisodeLayer,
    ModuleConnectivity,
)
from .base import GatewayMixinBase
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


class ConnectivityMixin(GatewayMixinBase):
    """Mixin providing connectivity behavior for BragerOneGateway."""

    def _is_started(self) -> bool:
        """Return whether the gateway is running (avoids mypy attribute narrowing across awaits)."""
        return self._started

    def cloud_session_outage(self) -> dict[str, float | str | None]:
        """Return cloud-session outage snapshot for diagnostics / HA attributes.

        Keys: ``down_since``, ``down_for_s``, ``reason``, ``last_down_for_s``,
        ``last_reason``. ``reason`` is a client observation token (coarse
        ``disconnect`` / ``stop`` or finer WS tokens such as ``handshake_503``),
        not plant hardware diagnostics.
        """
        return self._cloud_outage_snapshot()

    def module_outage(self, devid: str) -> dict[str, float | str | None]:
        """Return module↔cloud outage snapshot for *devid*.

        Same keys as :meth:`cloud_session_outage`. ``reason`` is the observation
        ``source`` (``rest`` / ``ws`` / ``derived``).
        """
        return self._module_outage_snapshot(devid)

    def connectivity_episodes(self) -> list[dict[str, float | str | None]]:
        """Return recent completed connectivity episodes (oldest → newest).

        Each dict has ``layer`` (``cloud`` / ``module`` / ``live_stale``),
        ``started_at`` / ``ended_at`` (wall-clock), ``down_for_s``, ``reason``,
        optional ``devid``, and ``episode_id``. No credentials.
        """
        return [dict(item) for item in self._connectivity_episodes]

    def _record_connectivity_episode(
        self,
        *,
        layer: ConnectivityEpisodeLayer,
        started_at: float,
        ended_at: float,
        down_for_s: float,
        reason: str | None,
        devid: str | None = None,
    ) -> None:
        """Append one completed outage episode to the ring buffer."""
        if self._connectivity_episode_limit <= 0:
            return
        self._connectivity_episodes.append(
            {
                "layer": layer,
                "started_at": float(started_at),
                "ended_at": float(ended_at),
                "down_for_s": float(down_for_s),
                "reason": reason,
                "devid": devid,
                "episode_id": f"{layer}-{uuid.uuid4().hex[:8]}",
            }
        )

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
        ended_at = time.time()
        started_at = self._cloud_down_since_wall if self._cloud_down_since_wall is not None else ended_at - duration
        reason = self._cloud_down_reason or "stop"
        self._cloud_last_down_for_s = duration
        self._cloud_last_reason = reason
        self._record_connectivity_episode(
            layer="cloud",
            started_at=started_at,
            ended_at=ended_at,
            down_for_s=duration,
            reason=reason,
        )
        self._cloud_down_since_mono = None
        self._cloud_down_since_wall = None
        self._cloud_down_reason = None

    def _clear_active_cloud_outage(self) -> None:
        """Drop a live outage window without updating ``last_*``."""
        self._cloud_down_since_mono = None
        self._cloud_down_since_wall = None
        self._cloud_down_reason = None

    async def _set_ws_session_up(
        self,
        up: bool,
        *,
        source: CloudSessionSource,
        reason: CloudOutageReason | None = None,
    ) -> None:
        """Update library↔cloud session cache and notify listeners on flips."""
        previous = self._ws_session_up
        self._ws_session_up = up
        changed = previous is not up
        if not changed:
            # stop() while already down: close the active window at the stop boundary.
            if source == "stop" and not up:
                self._finalize_cloud_outage_at_stop()
            return
        if up:
            self._ws_session_up_since_mono = time.monotonic()
        else:
            self._ws_session_up_since_mono = None
        if not up:
            self._cloud_down_since_mono = time.monotonic()
            self._cloud_down_since_wall = time.time()
            self._cloud_down_reason = reason or _cloud_outage_reason_from_source(source)
        elif self._cloud_down_since_mono is not None:
            duration = max(0.0, time.monotonic() - self._cloud_down_since_mono)
            ended_reason = self._cloud_down_reason or reason or _cloud_outage_reason_from_source(source)
            ended_at = time.time()
            started_at = self._cloud_down_since_wall if self._cloud_down_since_wall is not None else ended_at - duration
            self._cloud_last_down_for_s = duration
            self._cloud_last_reason = ended_reason
            self._record_connectivity_episode(
                layer="cloud",
                started_at=started_at,
                ended_at=ended_at,
                down_for_s=duration,
                reason=ended_reason,
            )
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
        self._publish_live_push_health()

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
        ws_reason: CloudOutageReason | None = None
        ws = self.ws
        if ws is not None:
            getter = getattr(ws, "last_disconnect_reason", None)
            if callable(getter):
                raw = getter()
                ws_reason = _as_cloud_outage_reason(raw)
        await self._set_ws_session_up(False, source="disconnect", reason=ws_reason)

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
                self._publish_live_push_health()
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

    async def _refresh_module_connectivity(self, *, source: ConnectivitySource = "rest") -> None:
        """Pull ``get_modules`` and apply online state for subscribed devids.

        Unusable fetches (HTTP errors or empty/unrecognised listings) keep the
        previous module online cache — transport loss must not look like the
        plant went offline. Authoritative ``online=False`` still comes from a
        successful row with ``connectedAt=0``, a derived-missing sibling when
        other subscribed rows were seen, or WS ``connection:status``. Refreshes
        are serialized so overlapping poll/reconnect completions cannot rebuild
        the diagnostic fail streak after a newer success. In-flight HTTP
        completions after ``stop()`` (lifecycle generation bump) are discarded;
        ordinary WS disconnect bumps only the session generation and must not
        drop a concurrent ``get_modules`` failure from the streak.
        """
        if not self._started:
            return
        lifecycle_generation = self._lifecycle_generation
        pending: list[tuple[int, ModuleConnectivity]] = []
        async with self._get_modules_refresh_lock:
            if not self._started or lifecycle_generation != self._lifecycle_generation:
                return
            await self._refresh_module_connectivity_locked(
                source=source,
                pending=pending,
                lifecycle_generation=lifecycle_generation,
            )
        if not self._is_started():
            return
        # Notify outside the lock so an async listener that re-enters refresh cannot deadlock.
        # Per-devid online-state sequence numbers drop events superseded by a nested
        # online/offline flip (metadata-only applies do not bump that sequence).
        # Abort the batch only on stop() (``_started``). Ordinary WS disconnect bumps
        # ``_connectivity_generation`` only; REST commits already under the lock must
        # still be delivered — otherwise consumers stay stale until a later poll
        # happens to change state again.
        for seq, event in pending:
            if not self._is_started():
                return
            await self._emit_module_connectivity(event, seq=seq)

    async def _refresh_module_connectivity_locked(
        self,
        *,
        source: ConnectivitySource,
        pending: list[tuple[int, ModuleConnectivity]],
        lifecycle_generation: int,
    ) -> None:
        """Apply one ``get_modules`` refresh while ``_get_modules_refresh_lock`` is held."""
        try:
            rows = await self.api.get_modules(self.object_id)
        except Exception as err:
            if not self._started or lifecycle_generation != self._lifecycle_generation:
                return
            await self._note_get_modules_failure(err, source=source)
            return

        if not self._started or lifecycle_generation != self._lifecycle_generation:
            return

        rows_list = list(rows)
        wanted = set(self.modules)
        seen: set[str] = set()
        for row in rows_list:
            devid = str(getattr(row, "devid", "") or "")
            if not devid or devid not in wanted:
                continue
            raw_connected_at = getattr(row, "connectedAt", None)
            connected_at = _parse_connected_at(raw_connected_at)
            if connected_at is None:
                if raw_connected_at is None:
                    # Parity with ``Module`` validation: upstream null means disconnected.
                    connected_at = 0
                else:
                    # Non-numeric junk mirrors ``get_modules`` dropping invalid rows.
                    LOG.warning("Skipping connectivity row with unusable connectedAt for devid=%s", devid)
                    continue
            seen.add(devid)
            await self._apply_connectivity(
                devid=devid,
                online=module_connected_at_means_online(connected_at),
                source=source,
                connected_at=connected_at,
                gateway=_gateway_as_dict(getattr(row, "gateway", None)),
                pending=pending,
            )

        # Only derive offline / clear the fail streak when the listing contained at
        # least one recognised subscribed module. Empty or odd shapes keep the
        # previous online cache and advance the diagnostic streak (never invent
        # plant-offline from an unusable observation).
        if not seen:
            if wanted:
                await self._advance_get_modules_fail_streak(
                    source=source,
                    detail="no recognised subscribed modules",
                )
            return

        self._get_modules_fail_streak = 0
        self._get_modules_fail_since_mono = None

        for devid in wanted - seen:
            await self._apply_connectivity(
                devid=devid,
                online=False,
                source="derived",
                connected_at=self._module_connected_at.get(devid, 0),
                pending=pending,
            )

    async def _note_get_modules_failure(
        self,
        err: Exception,
        *,
        source: ConnectivitySource,
    ) -> None:
        """Record a failed ``get_modules`` poll; keep last-known module online state."""
        expected = _is_http_timeout_error(err) or _is_api_dispatch_timeout(err) or is_expected_upstream_unavailable(err)
        if expected:
            await self._advance_get_modules_fail_streak(
                source=source,
                detail=format_expected_failure_reason(err),
                level="warning",
            )
        else:
            await self._advance_get_modules_fail_streak(
                source=source,
                detail=f"{type(err).__name__}: {err}",
                level="exception",
                exc=err,
            )

    async def _advance_get_modules_fail_streak(
        self,
        *,
        source: ConnectivitySource,
        detail: str,
        level: str = "warning",
        exc: Exception | None = None,
    ) -> None:
        """Bump the diagnostic fail streak without marking modules offline.

        Library↔cloud transport loss must not be reported as module↔cloud
        offline. Authoritative plant offline still arrives via ``connectedAt``
        on a usable listing or WS ``connection:status``.

        Warning/error logs fire once per outage window (streak == 1); later
        polls in the same window stay at DEBUG to avoid poll-interval spam.
        """
        now = time.monotonic()
        self._get_modules_fail_streak += 1
        if self._get_modules_fail_since_mono is None:
            self._get_modules_fail_since_mono = now
        streak = self._get_modules_fail_streak
        log_once = streak == 1
        # ``exc_info`` needs True/False or (type, value, tb) — not an Exception instance.
        exc_info: tuple[type[BaseException], BaseException, types.TracebackType | None] | None
        exc_info = (type(exc), exc, exc.__traceback__) if exc is not None else None
        if level == "exception":
            if log_once:
                LOG.error(
                    "get_modules failed during connectivity refresh (fail_streak=%s, source=%s, detail=%s); "
                    "keeping last-known module online state",
                    streak,
                    source,
                    detail,
                    exc_info=exc_info,
                )
            else:
                LOG.debug(
                    "get_modules still failing (fail_streak=%s, source=%s, detail=%s)",
                    streak,
                    source,
                    detail,
                    exc_info=exc_info,
                )
        elif log_once:
            LOG.warning(
                "get_modules unavailable during connectivity refresh; fail_streak=%s "
                "(source=%s, detail=%s); keeping last-known module online state",
                streak,
                source,
                detail,
            )
        else:
            LOG.debug(
                "get_modules still unavailable (fail_streak=%s, source=%s, detail=%s)",
                streak,
                source,
                detail,
            )

    def _bump_module_online_seq(self, devid: str) -> int:
        """Advance the per-module online-state sequence and return the new value."""
        nxt = self._module_online_seq.get(devid, 0) + 1
        self._module_online_seq[devid] = nxt
        return nxt

    def _bump_module_observation_seq(self, devid: str) -> int:
        """Advance the per-module observation revision (any successful apply)."""
        nxt = self._module_observation_seq.get(devid, 0) + 1
        self._module_observation_seq[devid] = nxt
        return nxt

    def _coalesce_module_connectivity_event(self, event: ModuleConnectivity) -> ModuleConnectivity:
        """Overlay current cache metadata onto *event*, preserving ``online_changed``.

        Lets later listeners observe an in-flight online flip while still seeing the
        latest ``connected_at`` / ``gateway`` if a nested metadata apply raced ahead.
        """
        devid = event.devid
        snapshot = self._module_outage_snapshot(devid)
        return replace(
            event,
            online=self._module_online.get(devid, event.online),
            connected_at=self._module_connected_at.get(devid, event.connected_at),
            gateway=self.module_gateway(devid),
            down_since=snapshot["down_since"] if isinstance(snapshot["down_since"], float) else None,
            down_for_s=snapshot["down_for_s"] if isinstance(snapshot["down_for_s"], float) else None,
            reason=_as_module_outage_reason(snapshot["reason"]),
            last_down_for_s=snapshot["last_down_for_s"] if isinstance(snapshot["last_down_for_s"], float) else None,
            last_reason=_as_module_outage_reason(snapshot["last_reason"]),
        )

    async def _emit_module_connectivity(self, event: ModuleConnectivity, *, seq: int) -> None:
        """Dispatch one module-connectivity event and optional online recovery.

        *seq* tracks online-state revisions only (not metadata-only applies). A
        nested gateway blob update must not suppress delivery of an in-flight
        offline→online flip to later listeners; coalescing refreshes metadata on
        the way out. If this event was an offline→online flip and the module is
        still online, still run recovery even when a later online-state revision
        superseded listener delivery.
        """
        if self._module_online_seq.get(event.devid) == seq:
            for cb in list(self._on_module_connectivity):
                if self._module_online_seq.get(event.devid) != seq:
                    break
                try:
                    res = cb(self._coalesce_module_connectivity_event(event))
                    if asyncio.iscoroutine(res):
                        # Bind the discarded None so CodeQL does not treat bare ``await`` as ineffectual.
                        _ = await res
                except Exception:
                    LOG.exception("Module connectivity callback error")
        if not (event.online_changed and event.online and event.devid in self.modules):
            return
        if self._module_online.get(event.devid) is not True:
            return
        await self._maybe_recover_after_module_online(event.devid)

    async def _apply_connectivity(
        self,
        *,
        devid: str,
        online: bool,
        source: ConnectivitySource,
        connected_at: int | None,
        gateway: dict[str, Any] | None = None,
        pending: list[tuple[int, ModuleConnectivity]] | None = None,
    ) -> None:
        """Update cache and notify listeners when online or metadata changes.

        When *pending* is provided, queue ``(seq, event)`` for the caller to emit after
        releasing ``_get_modules_refresh_lock`` (avoids callback re-entrancy deadlock).
        """
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
        # Confirming repeats (same connectedAt / gateway) still advance the observation
        # revision so a concurrent REST fail-close cannot overwrite a WS reaffirmation.
        self._bump_module_observation_seq(devid)
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
                ended_at = time.time()
                started_at = self._module_down_since_wall.get(devid, ended_at - duration)
                self._module_last_down_for_s[devid] = duration
                self._module_last_reason[devid] = ended_reason
                self._record_connectivity_episode(
                    layer="module",
                    started_at=started_at,
                    ended_at=ended_at,
                    down_for_s=duration,
                    reason=ended_reason,
                    devid=devid,
                )
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
        seq = self._bump_module_online_seq(devid) if online_changed else self._module_online_seq.get(devid, 0)
        if pending is not None:
            pending.append((seq, event))
            return
        await self._emit_module_connectivity(event, seq=seq)

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
