"""Resubscribe, SID bind, and REST prime orchestration for BragerOneGateway."""

from __future__ import annotations

import asyncio
import logging
import time

from .base import GatewayMixinBase
from .protocols import RealtimeManagerClient

LOG = logging.getLogger(__name__)

# How long ``resubscribe`` waits for a namespace SID after reconnect.
_RESUBSCRIBE_SID_WAIT_S = 2.0


class SessionMixin(GatewayMixinBase):
    """Mixin providing session behavior for BragerOneGateway."""

    async def resubscribe(self) -> bool:
        """Call after WS reconnect to re-bind modules + prime again.

        Returns:
            ``True`` when ``modules.connect`` succeeded and subscribe/prime ran;
            ``False`` when there is no WS client, no namespace SID, or connect failed.
        REST prime still runs when connect fails so the store is refreshed from
        the authoritative snapshot even without a live push binding.
        """
        async with self._resubscribe_lock:
            return await self._resubscribe_unlocked()

    async def _resubscribe_unlocked(self) -> bool:
        """Bind modules + prime; callers must hold ``_resubscribe_lock``."""
        ws = self.ws
        if ws is None:
            return False
        sid_ns = await self._wait_for_ws_sid(ws)
        sid_engine = ws.engine_sid()
        if not sid_ns:
            LOG.warning("WS resubscribe skipped: no namespace SID after reconnect")
            return False
        if sid_ns == self._bound_ns_sid:
            LOG.debug("WS resubscribe skipped: already bound ns_sid=%s", sid_ns)
            return True
        ok = await self.api.modules_connect(sid_ns, self.modules, group_id=self.object_id, engine_sid=sid_engine)
        if ok:
            LOG.info("modules.connect (resub): %s (ns_sid=%s, engine_sid=%s)", ok, sid_ns, sid_engine)
            await ws.subscribe(self.modules)
            self._bound_ns_sid = sid_ns
        else:
            LOG.warning("modules.connect (resub) failed (ns_sid=%s, engine_sid=%s)", sid_ns, sid_engine)
            self._bound_ns_sid = None
        okp, oka = await self._prime_with_retry()
        LOG.debug("prime after resubscribe: parameters=%s activity=%s", okp, oka)
        return ok

    async def _wait_for_ws_sid(self, ws: RealtimeManagerClient, *, timeout_s: float = _RESUBSCRIBE_SID_WAIT_S) -> str | None:
        """Wait briefly for a namespace SID after connect/reconnect."""
        deadline = time.monotonic() + max(0.0, timeout_s)
        while True:
            sid_ns = ws.sid()
            if sid_ns:
                return sid_ns
            if time.monotonic() >= deadline:
                return None
            await asyncio.sleep(0.05)

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

    async def _prime_alarm_quantity(self) -> None:
        """Best-effort alarm count prime; failures must not block parameter prime."""
        async with self._alarm_quantity_rest_seq_lock:
            self._alarm_quantity_rest_seq += 1
            rest_seq = self._alarm_quantity_rest_seq
            ws_floor = dict(self._alarm_quantity_ws_rev)
        try:
            res = await self.api.modules_alarms_quantity(self.modules, return_data=True)
        except Exception:
            LOG.debug("Alarm quantity prime failed", exc_info=True)
            return
        if isinstance(res, tuple) and len(res) == 2:
            st, data = res
            if st in (200, 204):
                await self.ingest_alarm_quantity(
                    data if isinstance(data, dict) else None,
                    source="rest",
                    ws_floor=ws_floor,
                    rest_seq=rest_seq,
                )

    async def _prime(self) -> tuple[bool, bool]:
        """Fetch initial state via REST (parameters, activity quantity, alarm quantity)."""
        ok_params = False
        ok_act = False

        async with asyncio.TaskGroup() as tg:
            t_params = tg.create_task(
                self.api.modules_parameters_prime(self.modules, return_data=True),
                name="gateway.api.modules_parameters_prime",
            )
            t_act = tg.create_task(
                self.api.modules_activity_quantity_prime(self.modules, return_data=True),
                name="gateway.api.modules_activity_quantity_prime",
            )
            t_alarms = tg.create_task(
                self._prime_alarm_quantity(),
                name="gateway.api.modules_alarms_quantity",
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

        t_alarms.result()

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
