"""Runtime-light parameter store.

This module intentionally contains *only* the minimal structures and logic
needed to store and update raw parameter values (e.g. ``P5.s0``).

All asset-driven behavior (mappings, menu grouping, i18n, computed STATUS rule
evaluation, and rich "describe" helpers) is implemented in
:class:`pybragerone.models.param_resolver.ParamResolver`.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

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

        When ``devid`` is supplied, values are scoped per module so multi-module
        setups with overlapping addresses do not bleed. :meth:`flatten_for_devid`
        reads one module snapshot; :meth:`flatten` merges all scoped modules
        (last write wins per address).

        This class is designed to be safe and fast for HA runtime.
    """

    families: dict[str, ParamFamilyModel] = Field(default_factory=dict)
    _devid_families: dict[str, dict[str, ParamFamilyModel]] = PrivateAttr(default_factory=dict)
    _last_write: dict[str, tuple[str | None, str, str]] = PrivateAttr(default_factory=dict)
    _last_fid_devid: dict[str, str | None] = PrivateAttr(default_factory=dict)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    async def run_with_bus(self, bus: EventBus) -> None:
        """Consume ParamUpdate events from EventBus and upsert into ParamStore."""
        async for upd in bus.subscribe():
            if getattr(upd, "value", None) is None:
                continue
            await self.upsert_async(f"{upd.pool}.{upd.chan}{upd.idx}", upd.value, devid=upd.devid)

    def _fid(self, pool: str, idx: int) -> str:
        """Unique family ID for (pool, idx), e.g. 'P4:1'."""
        return f"{pool}:{idx}"

    def _families_bucket(self, devid: str | None) -> dict[str, ParamFamilyModel]:
        if devid is None:
            return self.families
        bucket = self._devid_families.get(devid)
        if bucket is None:
            bucket = {}
            self._devid_families[devid] = bucket
        return bucket

    def upsert(self, key: str, value: Any, *, devid: str | None = None) -> ParamFamilyModel | None:
        """Upsert a single parameter value by full key, e.g. ``P4.v1``."""
        with self._lock:
            return self._upsert_locked(key, value, devid=devid)

    def _upsert_locked(self, key: str, value: Any, *, devid: str | None = None) -> ParamFamilyModel | None:
        try:
            pool, rest = key.split(".", 1)
            chan = rest[0]
            idx = int(rest[1:])
        except Exception:
            return None

        fid = self._fid(pool, idx)
        fam_dict = self._families_bucket(devid)
        fam = fam_dict.get(fid)
        if fam is None:
            fam = ParamFamilyModel(pool=pool, idx=idx)
            fam_dict[fid] = fam
        fam.set(chan, value)
        full_key = f"{pool}.{chan}{idx}"
        self._last_write[full_key] = (devid, fid, chan)
        self._last_fid_devid[fid] = devid
        return fam

    async def upsert_async(self, key: str, value: Any, *, devid: str | None = None) -> ParamFamilyModel | None:
        """Async upsert wrapper for convenience in async code."""
        return self.upsert(key, value, devid=devid)

    def get_family(self, pool: str, idx: int, *, devid: str | None = None) -> ParamFamilyModel | None:
        """Get ParamFamilyModel by (pool, idx) address, or None if not found."""
        with self._lock:
            return self._get_family_locked(pool, idx, devid=devid)

    def _get_family_locked(self, pool: str, idx: int, *, devid: str | None = None) -> ParamFamilyModel | None:
        fid = self._fid(pool, idx)
        if devid is not None:
            bucket = self._devid_families.get(devid)
            if bucket is None:
                return None
            return bucket.get(fid)
        if fid in self._last_fid_devid:
            last_devid = self._last_fid_devid[fid]
            if last_devid is not None:
                bucket = self._devid_families.get(last_devid)
                if bucket is not None:
                    found = bucket.get(fid)
                    if found is not None:
                        return found
            else:
                legacy = self.families.get(fid)
                if legacy is not None:
                    return legacy
        legacy = self.families.get(fid)
        if legacy is not None:
            return legacy
        for bucket in self._devid_families.values():
            found = bucket.get(fid)
            if found is not None:
                return found
        return None

    @staticmethod
    def _flatten_bucket(fam_dict: Mapping[str, ParamFamilyModel]) -> dict[str, Any]:
        return {f"{fam.pool}.{ch}{fam.idx}": val for fam in fam_dict.values() for ch, val in fam.channels.items()}

    def flatten_for_devid(self, devid: str) -> dict[str, Any]:
        """Flattened parameter snapshot for one module (prime + scoped deltas)."""
        with self._lock:
            bucket = self._devid_families.get(devid)
            if bucket is None:
                return {}
            return self._flatten_bucket(bucket)

    def flatten(self) -> dict[str, Any]:
        """Flattened view of all parameters as ``{ 'P4.v1': value, ... }``.

        Returns the most recently upserted value per address across all modules
        (true last-write-wins), regardless of ``devid`` bucket insertion order.
        """
        with self._lock:
            merged: dict[str, Any] = {}
            for bucket in self._devid_families.values():
                merged.update(self._flatten_bucket(bucket))
            merged.update(self._flatten_bucket(self.families))
            for full_key, (devid, fid, chan) in self._last_write.items():
                fam = self._families_bucket(devid).get(fid)
                if fam is not None and chan in fam.channels:
                    merged[full_key] = fam.channels[chan]
            return merged

    def ingest_prime_payload(self, payload: Mapping[str, Any]) -> None:
        """Ingest REST prime payload (modules/parameters) into the store."""
        for devid, pools in payload.items():
            if not isinstance(pools, Mapping):
                continue
            devid_key = str(devid)
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
                        meta_keys = (
                            "storable",
                            "createdAt",
                            "previousCreatedAt",
                            "updatedAt",
                            "updatedAtClient",
                            "expire",
                            "average",
                        )
                        with self._lock:
                            fam: ParamFamilyModel | None
                            if "value" in body:
                                fam = self._upsert_locked(chan_key, body["value"], devid=devid_key)
                            else:
                                fam = self._get_family_locked(pool, idx, devid=devid_key)
                                if fam is None:
                                    fam = self._upsert_locked(chan_key, None, devid=devid_key)
                            if fam is not None:
                                for meta_key in meta_keys:
                                    if meta_key in body:
                                        fam.set(meta_key, body[meta_key])
                    else:
                        self.upsert(chan_key, body, devid=devid_key)
