"""Zombie recovery ladder, cooldown, and quarantine for BragerOneGateway."""

from __future__ import annotations

import logging
import time
from typing import Any

from ..api import BragerOneApiClient

LOG = logging.getLogger(__name__)


# Cap for exponential recovery cooldown.
_MAX_ZOMBIE_RECOVERY_COOLDOWN_S = 1800.0
# Debounce module-online → zombie recovery so one get_modules pass cannot rebuild twice.
# Strictly above the default connectivity poll interval (60s).
_MODULE_ONLINE_RECOVERY_DEBOUNCE_S = 90.0


class RecoveryMixin:
    """Mixin providing recovery behavior for BragerOneGateway."""

    # Attributes owned by BragerOneGateway.__init__
    _last_live_param_publish_monotonic: float | None
    _last_param_publish_monotonic: float | None
    _module_online: dict[str, bool]
    _owns_ws: bool
    _stale_prime_after_s: float
    _ws_hooks_registered: bool
    _ws_session_up: bool
    _zombie_full_recycle_after: int
    _zombie_hard_restart_streak: int
    _zombie_last_module_online_recovery_monotonic: float | None
    _zombie_module_online_recovery_inflight: bool
    _zombie_prime_streak: int
    _zombie_quarantine_after: int
    _zombie_quarantine_s: float
    _zombie_quarantine_until: float | None
    _zombie_rebuild_after: int
    _zombie_rebuild_count: int
    _zombie_recovery_cooldown_s: float
    _zombie_recovery_cooldown_until: float | None
    _zombie_recycle_streak: int
    api: Any
    modules: list[str]
    ws: Any

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
            self._zombie_recycle_streak = 0
            self._zombie_rebuild_count = 0
            self._zombie_recovery_cooldown_until = None
            self._zombie_quarantine_until = None
            self._zombie_last_module_online_recovery_monotonic = None

    def _make_realtime_manager(self) -> Any:
        """Build a new Socket.IO client bound to the current API session.

        Resolves ``RealtimeManager`` via the package so tests can monkeypatch
        ``pybragerone.gateway.RealtimeManager``.
        """
        from pybragerone import gateway as gateway_pkg

        manager_cls = gateway_pkg.RealtimeManager
        if isinstance(self.api, BragerOneApiClient):
            return manager_cls(
                token=self.api.access_token,
                token_provider=self._fresh_ws_token,
                origin=self.api.one_base,
                referer=f"{self.api.one_base}/",
                io_base=self.api.io_base,
            )
        return manager_cls(token=self.api.access_token)

    async def _fresh_ws_token(self) -> str:
        """Return a valid token for a WS (re)connect, re-authenticating if expired."""
        api = self.api
        if not isinstance(api, BragerOneApiClient):
            return api.access_token
        await api.ensure_auth()
        return api.access_token

    async def _force_fresh_auth(self) -> bool:
        """Force a full re-login so WS recovery does not reuse a wedged cloud session.

        Delegates to ``BragerOneApiClient.invalidate_and_reauth``, which preflights
        credentials before clearing state. Without email/password (args or
        ``creds_provider``), the client keeps a usable token rather than wiping it
        and leaving reconnect unauthenticated.

        Returns:
            ``True`` when a usable access token is available after the attempt.
        """
        api = self.api
        try:
            if isinstance(api, BragerOneApiClient):
                tok = await api.invalidate_and_reauth()
                return bool(tok.access_token)
            access_token = await self._fresh_ws_token()
            return bool(access_token)
        except Exception:
            LOG.exception("Forced fresh auth failed")
            return False

    def _zombie_recovery_in_cooldown(self) -> bool:
        """Return whether WS recovery should pause after a recent recycle/rebuild."""
        until = self._zombie_recovery_cooldown_until
        return until is not None and time.monotonic() < until

    def _zombie_recovery_in_quarantine(self) -> bool:
        """Return whether WS recovery is paused for a long REST-only quarantine."""
        until = self._zombie_quarantine_until
        return until is not None and time.monotonic() < until

    def _arm_zombie_quarantine(self) -> None:
        """Pause WS recovery after repeated rebuilds without live ParamUpdates."""
        self._zombie_prime_streak = 0
        self._zombie_hard_restart_streak = 0
        duration = max(0.0, self._zombie_quarantine_s)
        if duration <= 0:
            self._zombie_quarantine_until = None
            return
        self._zombie_quarantine_until = time.monotonic() + duration
        LOG.warning(
            "Zombie WS recovery quarantined for %.0fs after %s rebuild(s) without live ParamUpdates; REST-priming only",
            duration,
            self._zombie_rebuild_count,
        )

    def _arm_zombie_recovery_cooldown(self) -> None:
        """Exponential backoff after recycle/rebuild so recovery does not thrash."""
        # Reset short-cycle streaks so cooldown expiry starts a fresh escalate ladder
        # instead of an immediate hard reconnect from primes counted during cooldown.
        self._zombie_prime_streak = 0
        self._zombie_hard_restart_streak = 0
        base = max(0.0, self._zombie_recovery_cooldown_s)
        if base <= 0:
            self._zombie_recovery_cooldown_until = None
            return
        exponent = max(0, self._zombie_recycle_streak - 1)
        cooldown = min(base * (2**exponent), _MAX_ZOMBIE_RECOVERY_COOLDOWN_S)
        self._zombie_recovery_cooldown_until = time.monotonic() + cooldown
        LOG.warning("Zombie WS recovery cooldown armed for %.0fs", cooldown)

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
        # Soft reconnect alone left wedged cloud push sessions in field logs;
        # force a fresh login before reconnecting (same as recycle/rebuild).
        # ``_force_fresh_auth`` never raises — failures return ``False``.
        if not await self._force_fresh_auth():
            LOG.warning("Aborting WS hard reconnect: no usable token after forced re-login")
            self._arm_zombie_recovery_cooldown()
            return
        try:
            await ws.force_reconnect()
            # ``force_reconnect`` may spawn ``on_connected`` work; await resubscribe so
            # ``modules.connect`` + subscribe + prime finish before the next poll tick.
            rebound = await self.resubscribe()
            LOG.warning(
                "WS hard reconnect resubscribe %s (ns_sid=%s engine_sid=%s)",
                "ok" if rebound else "failed",
                ws.sid(),
                ws.engine_sid(),
            )
        except Exception:
            LOG.exception("WS hard reconnect (zombie session) failed")

    async def _recycle_realtime_session(self, rest_prime_streak: int) -> None:
        """Escalate beyond hard reconnect: transport hard-reset, then rebuild."""
        ws = self.ws
        if ws is None or not self._is_running():
            return
        self._zombie_recycle_streak += 1
        rebuild_after = self._zombie_rebuild_after
        if rebuild_after > 0 and self._zombie_recycle_streak >= rebuild_after and self._owns_ws:
            await self._rebuild_realtime_manager(rest_prime_streak)
            return

        LOG.warning(
            "Zombie session persists after %s REST-primes and %s hard reconnect(s) "
            "without live ParamUpdates; recycling realtime transport (recycle_streak=%s)",
            rest_prime_streak,
            self._zombie_hard_restart_streak,
            self._zombie_recycle_streak,
        )
        self._zombie_hard_restart_streak = 0
        self._zombie_prime_streak = 0
        if not await self._force_fresh_auth():
            LOG.warning("Aborting realtime recycle: no usable token after forced re-login")
            self._arm_zombie_recovery_cooldown()
            return
        if not self._is_running():
            return
        try:
            hard_reset = getattr(ws, "hard_reset", None)
            if callable(hard_reset):
                await hard_reset()
            else:
                await ws.disconnect()
                if not self._is_running():
                    return
                await ws.connect()
            if not self._is_running():
                return
            await self.resubscribe()
        except Exception:
            LOG.exception("WS recycle (hard_reset/connect/resubscribe) failed")
        self._arm_zombie_recovery_cooldown()

    async def _rebuild_realtime_manager(self, rest_prime_streak: int) -> None:
        """Replace ``RealtimeManager`` entirely (HA-restart-style recovery)."""
        if not self._is_running() or not self._owns_ws:
            return
        LOG.warning(
            "Zombie session persists after %s REST-primes and %s recycle(s) without live "
            "ParamUpdates; rebuilding RealtimeManager",
            rest_prime_streak,
            self._zombie_recycle_streak,
        )
        self._zombie_hard_restart_streak = 0
        self._zombie_prime_streak = 0
        self._zombie_rebuild_count += 1
        if not await self._force_fresh_auth():
            LOG.warning("Aborting RealtimeManager rebuild: no usable token after forced re-login")
            self._arm_zombie_recovery_cooldown()
            return
        if not self._is_running():
            return
        old = self.ws
        self._ws_hooks_registered = False
        try:
            if old is not None:
                await old.disconnect()
        except Exception:
            LOG.exception("WS disconnect during RealtimeManager rebuild failed")
        if not self._is_running():
            return
        try:
            # Bind lifecycle hooks *before* connect so a failed handshake still leaves
            # a recoverable client (supervisor reconnect → on_connected → resubscribe).
            new_ws = self._make_realtime_manager()
            new_ws.on_event(self._ws_dispatch)
            new_ws.add_on_connected(self._on_ws_connected)
            new_ws.add_on_disconnected(self._on_ws_disconnected)
            self.ws = new_ws
            self._ws_hooks_registered = True
            await new_ws.connect()
            await self._set_ws_session_up(True, source="connect")
            await self.resubscribe()
        except Exception:
            LOG.exception("RealtimeManager rebuild (connect/resubscribe) failed")
        quarantine_after = self._zombie_quarantine_after
        if quarantine_after > 0 and self._zombie_rebuild_count >= quarantine_after:
            self._arm_zombie_quarantine()
            return
        self._arm_zombie_recovery_cooldown()

    async def _maybe_recover_after_module_online(self, devid: str) -> None:
        """Clear cooldown and escalate recovery when a module returns during a zombie.

        Today's field logs show rebuild+cooldown leaving the push stream dead while the
        module flaps offline→online; waiting out the cooldown misses that window.
        """
        if self._zombie_module_online_recovery_inflight or not self._is_running():
            return
        if not self._ws_session_up:
            return
        last = self._zombie_last_module_online_recovery_monotonic
        if last is not None and (time.monotonic() - last) < _MODULE_ONLINE_RECOVERY_DEBOUNCE_S:
            return
        age = self._zombie_param_update_age_s()
        stale_after = self._stale_prime_after_s
        if stale_after <= 0 or age is None or age < stale_after:
            return

        was_cooling = self._zombie_recovery_in_cooldown()
        was_quarantined = self._zombie_recovery_in_quarantine()
        self._zombie_module_online_recovery_inflight = True
        self._zombie_last_module_online_recovery_monotonic = time.monotonic()
        try:
            if was_cooling or was_quarantined:
                self._zombie_recovery_cooldown_until = None
                self._zombie_quarantine_until = None
                LOG.warning(
                    "Module %s came online while zombie (age=%.0fs, cleared %s); resubscribing",
                    devid,
                    age,
                    "quarantine" if was_quarantined else "cooldown",
                )
                if not await self._force_fresh_auth():
                    LOG.warning("Module-online recovery skipped: no usable token after forced re-login")
                    self._arm_zombie_recovery_cooldown()
                    return
                try:
                    rebound = await self.resubscribe()
                except Exception:
                    self._arm_zombie_recovery_cooldown()
                    raise
                if not rebound:
                    LOG.warning("Module-online recovery incomplete: resubscribe did not re-bind modules")
                    self._arm_zombie_recovery_cooldown()
                    return
                return

            LOG.warning(
                "Module %s came online while zombie (age=%.0fs); escalating zombie recovery",
                devid,
                age,
            )
            await self._recover_zombie_session(max(1, self._zombie_prime_streak))
        except Exception:
            LOG.exception("Zombie recovery after module online failed")
        finally:
            self._zombie_module_online_recovery_inflight = False
