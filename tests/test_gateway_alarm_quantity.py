"""Gateway alarm-quantity listen and callback tests."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from pybragerone.gateway import BragerOneGateway


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


@pytest.mark.asyncio
async def test_ingest_alarm_quantity_notifies_on_change() -> None:
    """REST/WS ingest fires on_alarm_quantity when count changes."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []

    def _on_event(event: Any) -> None:
        seen.append(event)

    gateway.on_alarm_quantity(_on_event)

    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": 2}}, source="rest")
    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": 2}}, source="rest")
    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": 3}}, source="ws")

    assert len(seen) == 2
    assert seen[0].devid == "D1"
    assert seen[0].quantity == 2
    assert seen[0].source == "rest"
    assert seen[1].quantity == 3
    assert seen[1].source == "ws"


@pytest.mark.asyncio
async def test_ws_dispatch_routes_alarms_quantity_change() -> None:
    """_ws_dispatch ingests app:modules:alarms:quantity:change payloads."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []
    gateway.on_alarm_quantity(lambda event: seen.append(event))

    coro = gateway._ws_dispatch(
        "app:modules:alarms:quantity:change",
        {"alarmsQuantity": {"D1": 5}},
    )
    assert coro is None
    await asyncio.sleep(0)

    assert len(seen) == 1
    assert seen[0].quantity == 5
    assert seen[0].source == "ws"


@pytest.mark.asyncio
async def test_ingest_alarm_quantity_ignores_unknown_devids() -> None:
    """Counts for unsubscribed modules are ignored."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []
    gateway.on_alarm_quantity(lambda event: seen.append(event))

    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"OTHER": 1}}, source="rest")

    assert seen == []
