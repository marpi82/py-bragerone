"""Runtime-light parameter store.

This module intentionally contains *only* the minimal structures and logic
needed to store and update raw parameter values (e.g. ``P5.s0``).

All asset-driven behavior (mappings, menu grouping, i18n, computed STATUS rule
evaluation, and rich "describe" helpers) is implemented in
:class:`pybragerone.models.param_resolver.ParamResolver`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .events import EventBus


class ParamFamilyModel(BaseModel):
    """One parameter "family" (e.g., P4 index 1) collecting channels: v/s/u/n/x..."""

    pool: str
    idx: int
    channels: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    def set(self, chan: str, value: Any) -> None:
        """Set raw channel value."""
        self.channels[chan] = value

    def get(self, chan: str, default: Any = None) -> Any:
        """Get raw channel value, or default if not present."""
        return self.channels.get(chan, default)

    @property
    def value(self) -> Any:
        """Raw value channel, if any."""
        return self.channels.get("v")

    @property
    def unit_code(self) -> Any:
        """Raw unit code channel, if any."""
        return self.channels.get("u")

    @property
    def status_raw(self) -> Any:
        """Raw status channel, if any."""
        return self.channels.get("s")


class ParamStore(BaseModel):
    """Store of live parameter values.

    Notes:
        Keys use the BragerOne addressing format: ``P<n>.<chan><idx>``
        (e.g. ``P5.s0``, ``P4.v1``, ``P4.u1``).

        This class is designed to be safe and fast for HA runtime.
    """

    families: dict[str, ParamFamilyModel] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    async def run_with_bus(self, bus: EventBus) -> None:
        """Consume ParamUpdate events from EventBus and upsert into ParamStore."""
        async for upd in bus.subscribe():
            if getattr(upd, "value", None) is None:
                continue
            await self.upsert_async(f"{upd.pool}.{upd.chan}{upd.idx}", upd.value)

    def _fid(self, pool: str, idx: int) -> str:
        """Unique family ID for (pool, idx), e.g. 'P4:1'."""
        return f"{pool}:{idx}"

    def upsert(self, key: str, value: Any) -> ParamFamilyModel | None:
        """Upsert a single parameter value by full key, e.g. ``P4.v1``."""
        try:
            pool, rest = key.split(".", 1)
            chan = rest[0]
            idx = int(rest[1:])
        except Exception:
            return None

        fid = self._fid(pool, idx)
        fam = self.families.get(fid)
        if fam is None:
            fam = ParamFamilyModel(pool=pool, idx=idx)
            self.families[fid] = fam
        fam.set(chan, value)
        return fam

    async def upsert_async(self, key: str, value: Any) -> ParamFamilyModel | None:
        """Async upsert wrapper for convenience in async code."""
        return self.upsert(key, value)

    def get_family(self, pool: str, idx: int) -> ParamFamilyModel | None:
        """Get ParamFamilyModel by (pool, idx) address, or None if not found."""
        return self.families.get(self._fid(pool, idx))

    def flatten(self) -> dict[str, Any]:
        """Flattened view of all parameters as ``{ 'P4.v1': value, ... }``."""
        return {f"{fam.pool}.{ch}{fam.idx}": val for fam in self.families.values() for ch, val in fam.channels.items()}

    def ingest_prime_payload(self, payload: Mapping[str, Any]) -> None:
        """Ingest REST prime payload (modules/parameters) into the store."""
        for pools in payload.values():
            if not isinstance(pools, Mapping):
                continue
            for pool, entries in pools.items():
                if not isinstance(pool, str) or not isinstance(entries, Mapping):
                    continue
                for chan_idx, body in entries.items():
                    if not isinstance(chan_idx, str) or len(chan_idx) < 2:
                        continue
                    chan = chan_idx[0]
                    try:
                        idx = int(chan_idx[1:])
                    except ValueError:
                        continue
                    chan_key = f"{pool}.{chan}{idx}"
                    if isinstance(body, Mapping):
                        fam: ParamFamilyModel | None
                        if "value" in body:
                            fam = self.upsert(chan_key, body["value"])
                        else:
                            fam = self.get_family(pool, idx)
                            if fam is None:
                                fam = self.upsert(chan_key, None)
                        if fam is not None:
                            meta_keys = (
                                "storable",
                                "createdAt",
                                "previousCreatedAt",
                                "updatedAt",
                                "updatedAtClient",
                                "expire",
                                "average",
                            )
                            for meta_key in meta_keys:
                                if meta_key in body:
                                    fam.set(meta_key, body[meta_key])
                    else:
                        self.upsert(chan_key, body)
