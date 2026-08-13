"""Tests for ParamStore ingest, upsert, and EventBus consumption."""

from __future__ import annotations

import asyncio
import contextlib

from pybragerone.models.events import EventBus, ParamUpdate
from pybragerone.models.param import ParamStore


def test_upsert_builds_family_and_exposes_channels() -> None:
    """Valid keys create a family; channel helpers and flatten match the store."""
    store = ParamStore()
    fam = store.upsert("P4.v1", 42.5)
    assert fam is not None
    store.upsert("P4.u1", 2)
    store.upsert("P4.s1", 8)

    assert fam.pool == "P4"
    assert fam.idx == 1
    assert fam.value == 42.5
    assert fam.unit_code == 2
    assert fam.status_raw == 8
    assert store.get_family("P4", 1) is fam
    assert store.get_family("P5", 1) is None
    assert store.flatten() == {"P4.v1": 42.5, "P4.u1": 2, "P4.s1": 8}


def test_upsert_rejects_malformed_keys() -> None:
    """Keys without ``pool.chanIdx`` shape are ignored."""
    store = ParamStore()
    assert store.upsert("noperiod", 1) is None
    assert store.upsert("P4.v", 1) is None
    assert store.upsert("", 1) is None
    assert store.families == {}


async def test_upsert_async_delegates_to_upsert() -> None:
    """Async wrapper returns the same family as the sync upsert."""
    store = ParamStore()
    fam = await store.upsert_async("P5.v0", 1)
    assert fam is not None
    assert fam.value == 1
    assert store.get_family("P5", 0) is fam


def test_ingest_prime_payload_skips_invalid_shapes_and_keeps_meta() -> None:
    """Prime ingest accepts REST-shaped bodies and ignores junk entries."""
    store = ParamStore()
    store.ingest_prime_payload(
        {
            "SKIP": "not-a-module",
            "DEV1": {
                4: {"v1": 1},
                "P5": "not-entries",
                "P4": {
                    "x": 1,
                    "vX": 1,
                    "v1": {
                        "value": 21.5,
                        "storable": True,
                        "createdAt": 10,
                        "previousCreatedAt": 9,
                        "updatedAt": 11,
                        "updatedAtClient": 12,
                        "expire": 0,
                        "average": 21.0,
                        "ignored": "nope",
                    },
                    "s1": 3,
                    "u1": {"storable": False},
                },
            },
        }
    )

    fam = store.get_family("P4", 1)
    assert fam is not None
    assert fam.value == 21.5
    assert fam.status_raw == 3
    assert fam.unit_code is None
    assert fam.get("storable") is True
    assert fam.get("createdAt") == 10
    assert fam.get("previousCreatedAt") == 9
    assert fam.get("updatedAt") == 11
    assert fam.get("updatedAtClient") == 12
    assert fam.get("expire") == 0
    assert fam.get("average") == 21.0
    assert fam.get("ignored") is None
    assert store.flatten()["P4.s1"] == 3


def test_ingest_prime_payload_attaches_meta_to_existing_family() -> None:
    """A meta-only body updates an already-created family instead of replacing it."""
    store = ParamStore()
    store.upsert("P4.v2", 7)
    store.ingest_prime_payload({"DEV1": {"P4": {"v2": {"updatedAt": 99}}}})

    fam = store.get_family("P4", 2)
    assert fam is not None
    assert fam.value == 7
    assert fam.get("updatedAt") == 99


async def test_run_with_bus_upserts_values_and_skips_none() -> None:
    """Bus consumer writes non-None values and ignores meta-only updates."""
    store = ParamStore()
    bus = EventBus()
    consumer = asyncio.create_task(store.run_with_bus(bus))
    try:
        await bus.publish(ParamUpdate(devid="M1", pool="P4", chan="v", idx=1, value=18.0))
        await bus.publish(ParamUpdate(devid="M1", pool="P4", chan="s", idx=1, value=None))
        fam = None
        for _ in range(50):
            fam = store.get_family("P4", 1)
            if fam is not None:
                break
            await asyncio.sleep(0)
        assert fam is not None
        assert fam.value == 18.0
        assert fam.status_raw is None
    finally:
        consumer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consumer
