"""Event bus and event classes for pybragerone."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Literal


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
    """Per-module cloud connectivity signal for gateway consumers.

    This is **not** published on :class:`EventBus` (which stays ``ParamUpdate``-only
    for Home Assistant compatibility). Consumers register
    ``BragerOneGateway.on_module_connectivity`` or poll
    :meth:`BragerOneGateway.module_online`.

    Mirrors the SPA module card / connection modal: online iff ``connectedAt`` is
    truthy (upstream uses ``0`` as offline). Live updates arrive on Socket.IO
    ``app:module:connection:status:changed`` with ``{devid: {connectedAt, gateway}}``.

    The client's own Socket.IO session is **not** folded into ``online`` — a local
    transport blip must not look like the module dropped off the cloud.
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


# Official SPA Layout / ObjectsLayout event name.
MODULE_CONNECTION_STATUS_CHANGED = "app:module:connection:status:changed"


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


class EventBus:
    """Event bus for managing parameter update events.

    Provides publish-subscribe functionality for parameter updates with
    sequence numbering and thread-safe operations.
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._subs: list[asyncio.Queue[ParamUpdate]] = []
        self._seq = 0
        self._lock = asyncio.Lock()

    def last_seq(self) -> int:
        """Get the last sequence number.

        Returns:
            The last sequence number that was assigned, or -1 if no events have been published.
        """
        return max(self._seq - 1, -1)

    async def publish(self, upd: ParamUpdate) -> None:
        """Publish an event to all subscribers.

        Args:
            upd: The parameter update event to publish.
        """
        async with self._lock:
            upd.__dict__["seq"] = self._seq  # safe, despite frozen dataclass
            self._seq += 1
            # snapshot of subscriber list, so we don't hold lock during put()
            targets: tuple[asyncio.Queue[ParamUpdate], ...] = tuple(self._subs)
        # broadcast outside of lock
        for q in targets:
            await q.put(upd)

    async def subscribe(self) -> AsyncGenerator[ParamUpdate]:
        """Subscribe to events.

        Returns:
            An async iterator that yields parameter update events.
        """
        q: asyncio.Queue[ParamUpdate] = asyncio.Queue()
        async with self._lock:
            self._subs.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            # unsubscribe subscriber
            async with self._lock:
                with suppress(ValueError):
                    self._subs.remove(q)
