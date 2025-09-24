"""Module src/pybragerone/events.py."""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParamUpdate:
    """ParamUpdate class.

    Attributes:
    TODO.
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
    """Multicast: każda subskrypcja ma własną kolejkę.
    publish() wrzuca ten sam event do wszystkich kolejek.
    """
    def __init__(self) -> None:
        """Init  .
    
        Returns:
        TODO.
        """
        self._subs: list[asyncio.Queue[ParamUpdate]] = []
        self._seq = 0
        self._lock = asyncio.Lock()

    def last_seq(self) -> int:
        """Last seq.
    
        Returns:
        TODO.
        """
        return max(self._seq - 1, -1)

    async def publish(self, upd: ParamUpdate) -> None:
        """Publish.
    
        Args:
        upd: TODO.

        Returns:
        TODO.
        """
        async with self._lock:
            upd.__dict__["seq"] = self._seq  # bezpiecznie, mimo frozen dataclass
            self._seq += 1
            # snapshot listy subów, żeby nie trzymać locka przy put()
            targets: tuple[asyncio.Queue[ParamUpdate], ...] = tuple(self._subs)
        # rozgłoś poza lockiem
        for q in targets:
            await q.put(upd)

    async def subscribe(self) -> AsyncIterator[ParamUpdate]:
        """Subscribe.
    
        Returns:
        TODO.
        """
        q: asyncio.Queue[ParamUpdate] = asyncio.Queue()
        async with self._lock:
            self._subs.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            # odpinanie subskrybenta
            async with self._lock:
                try:
                    self._subs.remove(q)
                except ValueError:
                    pass
