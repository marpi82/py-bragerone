"""Gateway alarm/activity feed invalidate callback tests (#405 Phase B)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from pybragerone.gateway import BragerOneGateway
from pybragerone.gateway.helpers import _extract_module_devids
from pybragerone.models.events import (
    MODULE_ALARMS_CHANGE,
    MODULE_ALARMS_RECEIVED,
    MODULES_ACTIVITY_QUANTITY_CHANGE,
    ActivityFeedInvalidate,
    AlarmFeedInvalidate,
)


class _FakeApi:
    async def modules_parameters_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        _ = modules
        if return_data:
            return 200, {}
        return True

    async def modules_activity_quantity_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        _ = modules
        if return_data:
            return 200, {"activityQuantity": {}}
        return True

    async def modules_alarms_quantity(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        _ = modules
        if return_data:
            return 200, {"alarmsQuantity": {}}
        return True


class _FakeWs:
    def __init__(self) -> None:
        self.on_event_cb: Any = None

    def on_event(self, cb: Any) -> None:
        self.on_event_cb = cb

    async def connect(self) -> None:
        return None

    async def subscribe(self, modules: list[str]) -> None:
        _ = modules

    async def resubscribe(self) -> None:
        return None


def _gateway(*, modules: list[str] | None = None) -> BragerOneGateway:
    return BragerOneGateway(
        api=_FakeApi(),  # type: ignore[arg-type]
        object_id=1,
        modules=modules or ["D1", "D2"],
        ws=_FakeWs(),  # type: ignore[arg-type]
        connectivity_poll_interval=0,
    )


def test_extract_module_devids_shapes() -> None:
    """Extract devid from flat, nested, and quantity-map payloads."""
    assert _extract_module_devids({"devid": "A1"}) == ["A1"]
    assert _extract_module_devids({"devId": "B1"}) == ["B1"]
    assert _extract_module_devids({"module": {"devid": "C1"}}) == ["C1"]
    assert _extract_module_devids({"alarmsQuantity": {"D1": 2, "D2": 0}}) == ["D1", "D2"]
    assert _extract_module_devids({"activityQuantity": {"E1": 1}}) == ["E1"]
    assert _extract_module_devids({}, fallback=["F1", "F2"]) == ["F1", "F2"]
    assert _extract_module_devids("not-a-dict", fallback=["G1"]) == ["G1"]
    assert _extract_module_devids({}) == []


async def test_ws_dispatch_alarm_change_and_received() -> None:
    """alarms:change / received notify on_alarm_feed_invalidate (not EventBus)."""
    gateway = _gateway()
    seen: list[AlarmFeedInvalidate] = []
    gateway.on_alarm_feed_invalidate(lambda event: seen.append(event))

    change = gateway._ws_dispatch(MODULE_ALARMS_CHANGE, {"devid": "D1"})
    received = gateway._ws_dispatch(MODULE_ALARMS_RECEIVED, {"devId": "D2"})
    assert change is None
    assert received is None
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert [(e.devid, e.reason, e.source) for e in seen] == [
        ("D1", "change", "ws"),
        ("D2", "received", "ws"),
    ]


async def test_ws_dispatch_alarm_invalidate_falls_back_to_subscribed_modules() -> None:
    """Broadcast alarm invalidate without devid refreshes all subscribed modules."""
    gateway = _gateway(modules=["D1", "D2"])
    seen: list[str] = []
    gateway.on_alarm_feed_invalidate(lambda event: seen.append(event.devid))

    gateway._ws_dispatch(MODULE_ALARMS_CHANGE, {})
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert seen == ["D1", "D2"]


async def test_ws_dispatch_alarm_invalidate_skips_unsubscribed() -> None:
    """Alarm invalidate for foreign devid is ignored."""
    gateway = _gateway(modules=["D1"])
    seen: list[AlarmFeedInvalidate] = []
    gateway.on_alarm_feed_invalidate(lambda event: seen.append(event))

    gateway._ws_dispatch(MODULE_ALARMS_CHANGE, {"devid": "OTHER"})
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert seen == []


async def test_ws_dispatch_activity_quantity_and_task() -> None:
    """Activity quantity + task lifecycle notify on_activity_feed_invalidate."""
    gateway = _gateway()
    seen: list[ActivityFeedInvalidate] = []
    gateway.on_activity_feed_invalidate(lambda event: seen.append(event))

    gateway._ws_dispatch(MODULES_ACTIVITY_QUANTITY_CHANGE, {"activityQuantity": {"D1": 3}})
    gateway._ws_dispatch("app:module:task:created", {"devid": "D2"})
    gateway._ws_dispatch("app:module:task:status:changed", {"module": {"devId": "D1"}})
    gateway._ws_dispatch("app:module:task:completed", {"devid": "D2"})
    for _ in range(8):
        await asyncio.sleep(0)

    assert [(e.devid, e.reason) for e in seen] == [
        ("D1", "quantity"),
        ("D2", "task"),
        ("D1", "task"),
        ("D2", "task"),
    ]


async def test_feed_invalidate_callback_error_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Callback exceptions on feed invalidate do not abort dispatch."""
    gateway = _gateway()

    def _boom(_event: AlarmFeedInvalidate) -> None:
        raise RuntimeError("invalidate boom")

    gateway.on_alarm_feed_invalidate(_boom)
    with caplog.at_level(logging.ERROR):
        gateway._ws_dispatch(MODULE_ALARMS_CHANGE, {"devid": "D1"})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    assert "Callback error" in caplog.text
