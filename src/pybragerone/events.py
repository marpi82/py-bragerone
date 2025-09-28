"""Event bus and event classes for pybragerone."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FeatureChanged:
    """Feature changed event.

    Represents a change in a device feature state.

    Attributes:
        devid: Device identifier.
        feature: Name of the feature that changed.
        value: New boolean value of the feature.
    """
    devid: str
    feature: str
    value: bool

@dataclass(frozen=True)
class ParamUpdate:
    """Parameter update event.

    Represents an update to a device parameter value.

    Attributes:
        devid: Device identifier.
        pool: Parameter pool name.
        chan: Channel identifier.
        idx: Parameter index.
        value: New parameter value, can be None.
        meta: Additional metadata dictionary.
        ts: Timestamp when the update occurred.
        seq: Sequence number for ordering events.
    """

    devid: str
    pool: str
    chan: str
    idx: int
    value: Any | None
    meta: dict[str, Any] = field(default_factory=dict)  # NEW
    ts: float = field(default_factory=time.time)
    seq: int = 0


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

    async def subscribe(self) -> AsyncIterator[ParamUpdate]:
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
