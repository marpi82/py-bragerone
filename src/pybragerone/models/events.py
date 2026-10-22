"""Event bus and event classes for pybragerone."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

ModuleOutageReason = Literal["rest", "ws", "derived"]
CloudOutageReason = Literal[
    "disconnect",
    "stop",
    "handshake_503",
    "connect_error",
    "empty_queue",
    "server_stop",
    "eio_close",
    "reconnect_error",
    "supervisor_stale",
    "force_reconnect",
    "hard_reset",
]
ConnectivityEpisodeLayer = Literal["cloud", "module", "live_stale"]


class BusChannel(StrEnum):
    """Typed EventBus channels for additive multi-event fan-out (#408 / #409)."""

    PARAM = "param"
    MODULE_CONNECTIVITY = "module_connectivity"
    CLOUD_SESSION = "cloud_session"
    LIVE_PUSH = "live_push"
    ALARM_QUANTITY = "alarm_quantity"
    ALARM_FEED = "alarm_feed"
    ACTIVITY_FEED = "activity_feed"


@dataclass(frozen=True)
class FeatureChanged:
    """Feature changed event representing a change in device feature state."""

    devid: str
    #: Device identifier.
    feature: str
    #: Name of the feature that changed.
    value: bool
    #: New boolean value of the feature.


@dataclass(frozen=True)
class ModuleConnectivity:
    """Module ↔ Brager cloud connectivity (SPA ``connectedAt``).

    Published on :class:`EventBus` channel :attr:`BusChannel.MODULE_CONNECTIVITY`
    and via ``BragerOneGateway.on_module_connectivity`` (compat). Poll
    :meth:`BragerOneGateway.module_online` when a snapshot is enough.

    Mirrors the SPA module card / connection modal: online iff ``connectedAt`` is
    truthy (upstream uses ``0`` as offline). Live updates arrive on Socket.IO
    ``app:module:connection:status:changed`` with ``{devid: {connectedAt, gateway}}``.

    When the module is offline there is nothing the client can repair — observe and
    wait. The library's own Socket.IO session is a **separate** layer
    (:class:`CloudSessionConnectivity`) and must never be folded into ``online``.
    """

    devid: str
    #: Device identifier.
    online: bool
    #: ``True`` when upstream ``connectedAt`` is truthy (SPA parity).
    source: Literal["rest", "ws", "derived"]
    #: Where the observation came from (REST poll, WS push, or derived absence).
    connected_at: int | None = None
    #: Raw ``connectedAt`` epoch seconds when known (``0`` means offline upstream).
    gateway: dict[str, Any] | None = None
    #: Optional gateway blob from REST/WS (``address``, ``interface``, ``version``).
    online_changed: bool = True
    #: ``True`` when the online bit flipped versus the previous cache.
    metadata_changed: bool = False
    #: ``True`` when ``connected_at`` and/or ``gateway`` changed without an online flip.
    ts: float = field(default_factory=time.time)
    #: Timestamp when this signal was produced.
    down_since: float | None = None
    #: Wall-clock ``time.time()`` when the current offline outage started (``None`` if online).
    down_for_s: float | None = None
    #: Seconds offline so far while ``online`` is false; ``None`` when online.
    reason: ModuleOutageReason | None = None
    #: Client-side observation source for the current outage (``rest`` / ``ws`` / ``derived``).
    last_down_for_s: float | None = None
    #: Duration of the most recently completed offline outage.
    last_reason: ModuleOutageReason | None = None
    #: Observation source of the most recently completed offline outage.


@dataclass(frozen=True)
class AlarmQuantityChanged:
    """Per-module alarm count changed (REST prime or Socket.IO push)."""

    devid: str
    #: Device identifier.
    quantity: int | None
    #: New alarm count when known.
    source: Literal["rest", "ws"]
    #: Where the observation came from.
    changed: bool = True
    #: ``True`` when the quantity differs from the previous cache.
    ts: float = field(default_factory=time.time)
    #: Timestamp when this signal was produced.


@dataclass(frozen=True)
class AlarmFeedInvalidate:
    """Signal that module alarm lists should be re-fetched from REST.

    SPA Alarms UI listens to ``app:module:alarms:change`` / ``…:received`` and
    reloads lists — it does **not** push row payloads on the Socket.IO event.
    """

    devid: str
    #: Device identifier whose alarm feeds should refresh.
    reason: Literal["change", "received"]
    #: Which Socket.IO alarm signal triggered the invalidate.
    source: Literal["ws"] = "ws"
    #: Always ``ws`` for these invalidate signals.
    ts: float = field(default_factory=time.time)
    #: Timestamp when this signal was produced.


@dataclass(frozen=True)
class ActivityFeedInvalidate:
    """Signal that module activity lists should be re-fetched from REST.

    Activity rows stay on REST; Socket.IO only indicates that the feed may have
    changed (quantity badge or task lifecycle events the SPA Activity page watches).
    """

    devid: str
    #: Device identifier whose activity feed should refresh.
    reason: Literal["quantity", "task"]
    #: Which upstream signal triggered the invalidate.
    source: Literal["ws"] = "ws"
    #: Always ``ws`` for these invalidate signals.
    ts: float = field(default_factory=time.time)
    #: Timestamp when this signal was produced.


@dataclass(frozen=True)
class CloudSessionConnectivity:
    """Library ↔ Brager cloud Socket.IO session (client transport health).

    Distinct from :class:`ModuleConnectivity` (module ↔ cloud ``connectedAt``).
    When this session drops the gateway **self-heals**: Engine.IO reset on connect
    timeout, supervisor reconnect, resubscribe + REST prime, REST re-prime on
    the connectivity poll while the socket is still down, and after repeated
    stale-ParamUpdate cycles a hard WS restart (SPA parity: ``connect`` →
    ``ModulesService.connect`` + REST parameters). Published on
    :attr:`BusChannel.CLOUD_SESSION` and via ``BragerOneGateway.on_cloud_session``
    (compat); poll :meth:`BragerOneGateway.ws_session_up` for a snapshot.
    """

    up: bool
    #: ``True`` while this gateway's Socket.IO client session is connected.
    source: Literal["connect", "disconnect", "stop"]
    #: Why the session bit was updated.
    changed: bool = True
    #: ``True`` when ``up`` flipped versus the previous cache.
    ts: float = field(default_factory=time.time)
    #: Timestamp when this signal was produced.
    down_since: float | None = None
    #: Wall-clock ``time.time()`` when the current session-down outage started (``None`` if up).
    down_for_s: float | None = None
    #: Seconds down so far while ``up`` is false; ``None`` when up.
    reason: CloudOutageReason | None = None
    #: Client-side reason for the current down (coarse ``disconnect`` / ``stop`` or
    #: finer WS tokens such as ``handshake_503`` / ``eio_close``); not plant diagnostics.
    last_down_for_s: float | None = None
    #: Duration of the most recently completed session-down outage.
    last_reason: CloudOutageReason | None = None
    #: Reason of the most recently completed session-down outage.


@dataclass(frozen=True)
class ConnectivityEpisode:
    """One completed connectivity outage episode for diagnostics history (#379)."""

    layer: ConnectivityEpisodeLayer
    #: Which connectivity layer this episode belongs to.
    started_at: float
    #: Wall-clock ``time.time()`` when the outage started.
    ended_at: float
    #: Wall-clock ``time.time()`` when the outage ended.
    down_for_s: float
    #: Duration of the outage in seconds.
    reason: str | None = None
    #: Observation/source reason (cloud WS tokens, module source, or ``live_stale``).
    devid: str | None = None
    #: Module id when ``layer`` is ``module``; otherwise ``None``.
    episode_id: str | None = None
    #: Opaque id for correlating logs with diagnostics.


@dataclass(frozen=True)
class LivePushHealth:
    """Live ``ParamUpdate`` push health while the Socket.IO session is up.

    Distinct from :class:`CloudSessionConnectivity` (transport up/down) and
    :class:`ModuleConnectivity` (module ``connectedAt``). A zombie session is
    ``up=True`` with ``healthy=False`` / ``live_stale_for_s`` set.
    """

    healthy: bool | None
    #: ``True`` when live push is fresh; ``False`` when stale; ``None`` when N/A
    #: (session down) or unknown (session up but no live ``ParamUpdate`` yet).
    live_stale_for_s: float | None = None
    #: Seconds since the last live ``ParamUpdate`` while push is unhealthy.
    last_resumed_after_s: float | None = None
    #: Duration of the most recently completed live-stale episode (after resume).
    changed: bool = True
    #: ``True`` when ``healthy`` flipped versus the previous cache.
    ts: float = field(default_factory=time.time)
    #: Timestamp when this signal was produced.


# Official SPA Layout / ObjectsLayout event name.
MODULE_CONNECTION_STATUS_CHANGED = "app:module:connection:status:changed"
# SPA EventChannel.SIGMA_NETWORK_EVENT_MODULE_MEMORY_UPDATED (0x16). Payload ``{devid}``;
# Layout/ObjectsLayout respond with REST ``POST /modules/parameters`` for that module.
MODULE_MEMORY_UPDATED = "22"
# SPA Alarms UI: ``APP_MODULE_ALARMS_CHANGE`` / ``APP_MODULE_ALARMS_RECEIVED`` → REST reload.
MODULE_ALARMS_CHANGE = "app:module:alarms:change"
MODULE_ALARMS_RECEIVED = "app:module:alarms:received"
# Quantity badge pushes after ``…:quantity:listen`` subscribe emits.
MODULES_ALARMS_QUANTITY_CHANGE = "app:modules:alarms:quantity:change"
MODULES_ACTIVITY_QUANTITY_CHANGE = "app:modules:activity:quantity:change"


@dataclass(frozen=True)
class ParamUpdate:
    """Parameter update event carrying value and metadata updates."""

    devid: str
    #: Device identifier.
    pool: str
    #: Parameter pool name.
    chan: str
    #: Channel identifier (``v``, ``s``, ``u`` ...).
    idx: int
    #: Parameter index.
    value: Any | None
    #: New parameter value, can be ``None`` for meta-only updates.
    meta: dict[str, Any] = field(default_factory=dict)
    #: Additional metadata dictionary.
    ts: float = field(default_factory=time.time)
    #: Timestamp when the update occurred.
    seq: int = 0
    #: Sequence number assigned by :class:`EventBus`.


GatewayEvent = (
    ParamUpdate
    | ModuleConnectivity
    | CloudSessionConnectivity
    | LivePushHealth
    | AlarmQuantityChanged
    | AlarmFeedInvalidate
    | ActivityFeedInvalidate
)

_EVENT_TO_CHANNEL: dict[type[Any], BusChannel] = {
    ParamUpdate: BusChannel.PARAM,
    ModuleConnectivity: BusChannel.MODULE_CONNECTIVITY,
    CloudSessionConnectivity: BusChannel.CLOUD_SESSION,
    LivePushHealth: BusChannel.LIVE_PUSH,
    AlarmQuantityChanged: BusChannel.ALARM_QUANTITY,
    AlarmFeedInvalidate: BusChannel.ALARM_FEED,
    ActivityFeedInvalidate: BusChannel.ACTIVITY_FEED,
}


def channel_for_event(event: GatewayEvent) -> BusChannel:
    """Return the :class:`BusChannel` for a typed gateway event.

    Args:
        event: Event instance to route.

    Returns:
        Matching bus channel.

    Raises:
        TypeError: If *event* is not a known :data:`GatewayEvent` type.
    """
    channel = _EVENT_TO_CHANNEL.get(type(event))
    if channel is None:
        msg = f"Unsupported gateway event type: {type(event)!r}"
        raise TypeError(msg)
    return channel


class EventBus:
    """Multicast bus: ``subscribe()`` is ParamUpdate-only; channels are additive.

    ``subscribe()`` stays typed to :class:`ParamUpdate` so ParamStore / HA parameter
    loops stay unbroken. Non-parameter signals are available via
    :meth:`subscribe_channel` (and still via gateway ``on_*`` callbacks for compat).
    Alarm/activity **row lists** are never on the bus — REST remains source of truth.
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._param_subs: list[asyncio.Queue[ParamUpdate]] = []
        self._channel_subs: dict[BusChannel, list[asyncio.Queue[GatewayEvent]]] = {channel: [] for channel in BusChannel}
        self._seq = 0
        self._lock = asyncio.Lock()

    def last_seq(self) -> int:
        """Get the last sequence number.

        Returns:
            The last sequence number that was assigned, or -1 if no events have been published.
        """
        return max(self._seq - 1, -1)

    async def publish(self, upd: ParamUpdate) -> None:
        """Publish a :class:`ParamUpdate` to ``subscribe()`` and ``PARAM`` channel subscribers.

        Args:
            upd: The parameter update event to publish.
        """
        await self.publish_event(upd)

    async def publish_event(self, event: GatewayEvent) -> None:
        """Publish a typed event to the matching channel (and ParamUpdate subscribers).

        Args:
            event: Gateway event dataclass to fan out.
        """
        channel = channel_for_event(event)
        async with self._lock:
            param_targets: tuple[asyncio.Queue[ParamUpdate], ...]
            if isinstance(event, ParamUpdate):
                event.__dict__["seq"] = self._seq  # safe, despite frozen dataclass
                self._seq += 1
                param_targets = tuple(self._param_subs)
                param_event: ParamUpdate | None = event
            else:
                param_targets = ()
                param_event = None
            channel_targets: tuple[asyncio.Queue[GatewayEvent], ...] = tuple(self._channel_subs[channel])
        if param_event is not None:
            for param_q in param_targets:
                await param_q.put(param_event)
        for channel_q in channel_targets:
            await channel_q.put(event)

    async def subscribe(self) -> AsyncGenerator[ParamUpdate]:
        """Subscribe to :class:`ParamUpdate` events only.

        Returns:
            An async iterator that yields parameter update events.
        """
        q: asyncio.Queue[ParamUpdate] = asyncio.Queue()
        async with self._lock:
            self._param_subs.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            async with self._lock:
                with suppress(ValueError):
                    self._param_subs.remove(q)

    async def subscribe_channel(self, *channels: BusChannel | str) -> AsyncGenerator[GatewayEvent]:
        """Subscribe to one or more typed channels.

        Args:
            *channels: Channels to receive (:class:`BusChannel` or matching string values).
                At least one is required. Duplicates are ignored.

        Yields:
            Events published on any of the selected channels (FIFO per subscriber).

        Raises:
            ValueError: If no channels are provided or a name is not a known channel.
        """
        if not channels:
            msg = "subscribe_channel requires at least one BusChannel"
            raise ValueError(msg)
        wanted: list[BusChannel] = []
        seen: set[BusChannel] = set()
        for raw in channels:
            channel = BusChannel(raw) if not isinstance(raw, BusChannel) else raw
            if channel in seen:
                continue
            seen.add(channel)
            wanted.append(channel)
        q: asyncio.Queue[GatewayEvent] = asyncio.Queue()
        async with self._lock:
            for channel in wanted:
                self._channel_subs[channel].append(q)
        try:
            while True:
                yield await q.get()
        finally:
            async with self._lock:
                for channel in wanted:
                    with suppress(ValueError):
                        self._channel_subs[channel].remove(q)
