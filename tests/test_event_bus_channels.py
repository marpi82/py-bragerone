"""Typed multi-event EventBus channel tests (#408 / #409)."""

from __future__ import annotations

import asyncio

import pytest

from pybragerone.models.events import (
    ActivityFeedInvalidate,
    AlarmFeedInvalidate,
    AlarmQuantityChanged,
    BusChannel,
    CloudSessionConnectivity,
    EventBus,
    LivePushHealth,
    ModuleConnectivity,
    ParamUpdate,
    channel_for_event,
)


async def test_subscribe_remains_param_update_only() -> None:
    """``subscribe()`` yields ParamUpdate and ignores other channels."""
    bus = EventBus()
    agen = bus.subscribe()
    task = asyncio.create_task(agen.__anext__())
    await asyncio.sleep(0)

    await bus.publish_event(ModuleConnectivity(devid="D1", online=True, source="ws"))
    await bus.publish(ParamUpdate(devid="D1", pool="P4", chan="v", idx=1, value=1.0))

    upd = await asyncio.wait_for(task, timeout=1.0)
    assert isinstance(upd, ParamUpdate)
    assert upd.value == 1.0
    assert upd.seq == 0
    await agen.aclose()


async def test_subscribe_channel_receives_connectivity_and_invalidate() -> None:
    """Channel subscribers receive non-Param events without ParamUpdate flood."""
    bus = EventBus()
    agen = bus.subscribe_channel(
        BusChannel.MODULE_CONNECTIVITY,
        BusChannel.ALARM_FEED,
        BusChannel.ACTIVITY_FEED,
    )
    waiter = asyncio.create_task(_collect_n(agen, 3))
    await asyncio.sleep(0)

    await bus.publish(ParamUpdate(devid="D1", pool="P4", chan="v", idx=1, value=9.0))
    await bus.publish_event(ModuleConnectivity(devid="D1", online=False, source="rest"))
    await bus.publish_event(AlarmFeedInvalidate(devid="D1", reason="change"))
    await bus.publish_event(ActivityFeedInvalidate(devid="D1", reason="task"))

    events = await asyncio.wait_for(waiter, timeout=1.0)
    assert [type(e) for e in events] == [
        ModuleConnectivity,
        AlarmFeedInvalidate,
        ActivityFeedInvalidate,
    ]
    await agen.aclose()


async def test_subscribe_channel_param_gets_param_updates() -> None:
    """Including PARAM in subscribe_channel delivers ParamUpdate with seq."""
    bus = EventBus()
    agen = bus.subscribe_channel(BusChannel.PARAM)
    task = asyncio.create_task(agen.__anext__())
    await asyncio.sleep(0)
    await bus.publish(ParamUpdate(devid="D1", pool="P4", chan="v", idx=2, value=3.0))
    event = await asyncio.wait_for(task, timeout=1.0)
    assert isinstance(event, ParamUpdate)
    assert event.seq == 0
    assert event.idx == 2
    await agen.aclose()


async def test_subscribe_channel_requires_channels() -> None:
    """Empty subscribe_channel raises ValueError."""
    bus = EventBus()
    with pytest.raises(ValueError, match="at least one"):
        agen = bus.subscribe_channel()
        await agen.__anext__()


async def test_unsubscribe_stops_delivery() -> None:
    """Closing a channel subscription removes its queue."""
    bus = EventBus()
    agen = bus.subscribe_channel(BusChannel.CLOUD_SESSION)
    await asyncio.sleep(0)
    await agen.aclose()

    await bus.publish_event(CloudSessionConnectivity(up=False, source="disconnect"))
    agen2 = bus.subscribe_channel(BusChannel.CLOUD_SESSION)
    task = asyncio.create_task(agen2.__anext__())
    await asyncio.sleep(0)
    await bus.publish_event(CloudSessionConnectivity(up=True, source="connect"))
    event = await asyncio.wait_for(task, timeout=1.0)
    assert isinstance(event, CloudSessionConnectivity)
    assert event.up is True
    await agen2.aclose()


async def test_publish_event_routes_all_known_types() -> None:
    """Each GatewayEvent type maps to the expected BusChannel."""
    samples: list[tuple[object, BusChannel]] = [
        (ParamUpdate(devid="D1", pool="P4", chan="v", idx=1, value=1), BusChannel.PARAM),
        (ModuleConnectivity(devid="D1", online=True, source="ws"), BusChannel.MODULE_CONNECTIVITY),
        (CloudSessionConnectivity(up=True, source="connect"), BusChannel.CLOUD_SESSION),
        (LivePushHealth(healthy=True), BusChannel.LIVE_PUSH),
        (AlarmQuantityChanged(devid="D1", quantity=2, source="ws"), BusChannel.ALARM_QUANTITY),
        (AlarmFeedInvalidate(devid="D1", reason="received"), BusChannel.ALARM_FEED),
        (ActivityFeedInvalidate(devid="D1", reason="quantity"), BusChannel.ACTIVITY_FEED),
    ]
    for event, expected in samples:
        assert channel_for_event(event) == expected  # type: ignore[arg-type]


async def test_channel_for_event_rejects_unknown() -> None:
    """Unsupported types raise TypeError."""
    with pytest.raises(TypeError, match="Unsupported"):
        channel_for_event(object())  # type: ignore[arg-type]


async def _collect_n(agen: object, n: int) -> list[object]:
    """Collect *n* items from an async generator."""
    out: list[object] = []
    anext = agen.__anext__  # type: ignore[attr-defined]
    for _ in range(n):
        out.append(await anext())
    return out
