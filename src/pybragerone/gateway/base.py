"""Shared typed state and cross-mixin method surface for BragerOneGateway."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Literal

from ..models.events import CloudOutageReason, EventBus, ModuleOutageReason
from .helpers import (
    AlarmQuantityCb,
    CloudSessionCb,
    CloudSessionSource,
    ConnectivitySource,
    GenericCb,
    LivePushCb,
    ModuleConnectivityCb,
    ParametersCb,
    SnapshotCb,
)
from .protocols import ApiClient, RealtimeManagerClient


class GatewayMixinBase:
    """Attribute declarations and sibling-method stubs shared by gateway mixins.

    Mixins inherit this base so mypy --strict can resolve ``self.*`` without
    per-module overrides. Concrete implementations live on the mixins / facade.
    """

    object_id: int
    modules: list[str]
    api: ApiClient
    ws: RealtimeManagerClient | None
    bus: EventBus
    _owns_ws: bool
    _owns_api: bool
    _connectivity_poll_interval: float
    _stale_prime_after_s: float
    _zombie_hard_restart_after: int
    _zombie_full_recycle_after: int
    _zombie_rebuild_after: int
    _zombie_recovery_cooldown_s: float
    _zombie_quarantine_after: int
    _zombie_quarantine_s: float
    _zombie_prime_streak: int
    _zombie_hard_restart_streak: int
    _zombie_recycle_streak: int
    _zombie_rebuild_count: int
    _zombie_recovery_cooldown_until: float | None
    _zombie_quarantine_until: float | None
    _zombie_module_online_recovery_inflight: bool
    _zombie_last_module_online_recovery_monotonic: float | None
    _resubscribe_lock: asyncio.Lock
    _bound_ns_sid: str | None
    _last_param_publish_monotonic: float | None
    _last_live_param_publish_monotonic: float | None
    _live_push_healthy: bool | None
    _last_live_resumed_after_s: float | None
    _tasks: set[asyncio.Task[Any]]
    _started: bool
    _prime_done: asyncio.Event
    _prime_seq: int | None
    _first_snapshot: asyncio.Event
    _on_parameters_change: list[ParametersCb]
    _on_snapshot: list[SnapshotCb]
    _on_any: list[GenericCb]
    _on_module_connectivity: list[ModuleConnectivityCb]
    _on_cloud_session: list[CloudSessionCb]
    _on_alarm_quantity: list[AlarmQuantityCb]
    _on_live_push: list[LivePushCb]
    _ws_session_up: bool
    _ws_hooks_registered: bool
    _connectivity_generation: int
    _module_connected_at: dict[str, int]
    _module_online: dict[str, bool]
    _module_gateway: dict[str, dict[str, Any]]
    _cloud_down_since_mono: float | None
    _cloud_down_since_wall: float | None
    _cloud_down_reason: CloudOutageReason | None
    _cloud_last_down_for_s: float | None
    _cloud_last_reason: CloudOutageReason | None
    _module_down_since_mono: dict[str, float]
    _module_down_since_wall: dict[str, float]
    _module_down_reason: dict[str, ModuleOutageReason]
    _module_last_down_for_s: dict[str, float]
    _module_last_reason: dict[str, ModuleOutageReason]
    _alarm_quantity_cache: dict[str, int | None]
    _alarm_quantity_ws_rev: dict[str, int]
    _alarm_quantity_ingest_lock: asyncio.Lock
    _alarm_quantity_rest_seq: int
    _alarm_quantity_rest_applied_seq: int
    _alarm_quantity_rest_seq_lock: asyncio.Lock

    def _is_running(self) -> bool:
        raise NotImplementedError

    def last_param_update_age_s(self) -> float | None:
        raise NotImplementedError

    def last_live_param_update_age_s(self) -> float | None:
        raise NotImplementedError

    def live_push_health(self) -> dict[str, float | bool | None]:
        raise NotImplementedError

    def _compute_live_push_health(self) -> tuple[bool | None, float | None]:
        raise NotImplementedError

    def _publish_live_push_health(self, *, force_notify: bool = False) -> None:
        raise NotImplementedError

    def module_gateway(self, devid: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def cloud_session_outage(self) -> dict[str, float | str | None]:
        raise NotImplementedError

    def module_outage(self, devid: str) -> dict[str, float | str | None]:
        raise NotImplementedError

    def _cloud_outage_snapshot(self) -> dict[str, float | str | None]:
        raise NotImplementedError

    def _module_outage_snapshot(self, devid: str) -> dict[str, float | str | None]:
        raise NotImplementedError

    def _finalize_cloud_outage_at_stop(self) -> None:
        raise NotImplementedError

    def _clear_active_cloud_outage(self) -> None:
        raise NotImplementedError

    def _zombie_param_update_age_s(self) -> float | None:
        raise NotImplementedError

    def _any_subscribed_module_online(self) -> bool:
        raise NotImplementedError

    def _zombie_recovery_in_cooldown(self) -> bool:
        raise NotImplementedError

    def _zombie_recovery_in_quarantine(self) -> bool:
        raise NotImplementedError

    def _arm_zombie_quarantine(self) -> None:
        raise NotImplementedError

    def _arm_zombie_recovery_cooldown(self) -> None:
        raise NotImplementedError

    def _make_realtime_manager(self) -> Any:
        raise NotImplementedError

    def _touch_param_publish(self, count: int, *, live: bool = False) -> None:
        raise NotImplementedError

    def _spawn(self, coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> asyncio.Task[Any]:
        raise NotImplementedError

    def _ws_dispatch(self, event_name: str, payload: Any) -> Awaitable[None] | None:
        raise NotImplementedError

    async def refresh_module_connectivity(self) -> None:
        raise NotImplementedError

    async def _set_ws_session_up(self, up: bool, *, source: CloudSessionSource) -> None:
        raise NotImplementedError

    async def _on_ws_connected(self) -> None:
        raise NotImplementedError

    async def _on_ws_disconnected(self) -> None:
        raise NotImplementedError

    async def _connectivity_poll_loop(self) -> None:
        raise NotImplementedError

    async def _refresh_module_connectivity(self, *, source: ConnectivitySource = "rest") -> None:
        raise NotImplementedError

    async def _apply_connectivity(
        self,
        *,
        devid: str,
        online: bool,
        source: ConnectivitySource,
        connected_at: int | None,
        gateway: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError

    async def _ingest_module_connection_status(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    async def resubscribe(self) -> bool:
        raise NotImplementedError

    async def _resubscribe_unlocked(self) -> bool:
        raise NotImplementedError

    async def _wait_for_ws_sid(self, ws: RealtimeManagerClient, *, timeout_s: float = 2.0) -> str | None:
        raise NotImplementedError

    async def wait_for_prime(self, timeout: float | None = None) -> bool:
        raise NotImplementedError

    async def _prime_alarm_quantity(self) -> None:
        raise NotImplementedError

    async def _prime(self) -> tuple[bool, bool]:
        raise NotImplementedError

    async def _prime_with_retry(self, tries: int = 3) -> tuple[bool, bool]:
        raise NotImplementedError

    async def _prime_devids(self, devids: list[str]) -> bool:
        raise NotImplementedError

    async def _fresh_ws_token(self) -> str:
        raise NotImplementedError

    async def _force_fresh_auth(self) -> bool:
        raise NotImplementedError

    async def _recover_zombie_session(self, rest_prime_streak: int) -> None:
        raise NotImplementedError

    async def _recycle_realtime_session(self, rest_prime_streak: int) -> None:
        raise NotImplementedError

    async def _rebuild_realtime_manager(self, rest_prime_streak: int) -> None:
        raise NotImplementedError

    async def _maybe_recover_after_module_online(self, devid: str) -> None:
        raise NotImplementedError

    async def _invoke_list(self, cbs: list[Callable[..., Any]], *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    async def ingest_prime_parameters(self, data: dict[str, Any]) -> None:
        raise NotImplementedError

    async def ingest_activity_quantity(self, data: dict[str, Any] | None) -> None:
        raise NotImplementedError

    async def ingest_alarm_quantity(
        self,
        data: dict[str, Any] | None,
        *,
        source: Literal["rest", "ws"] = "rest",
        ws_floor: dict[str, int] | None = None,
        rest_seq: int | None = None,
    ) -> None:
        raise NotImplementedError
