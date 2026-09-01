"""Gateway alarm-quantity listen and callback tests."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from pybragerone.gateway import BragerOneGateway, _parse_alarm_quantity


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
            return 200, {"alarmsQuantity": {"D1": 7}}
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


class _FailingAlarmsApi(_FakeApi):
    async def modules_alarms_quantity(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        _ = modules
        if return_data:
            return 503, {"alarmsQuantity": {"D1": 9}}
        return False


class _NonDictAlarmsApi(_FakeApi):
    async def modules_alarms_quantity(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        _ = modules
        if return_data:
            return 204, "not-a-dict"
        return True


class _RaisingAlarmsApi(_FakeApi):
    async def modules_alarms_quantity(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        _ = modules
        raise RuntimeError("alarm prime unavailable")


class _RacyAlarmsApi(_FakeApi):
    def __init__(self, gateway: BragerOneGateway) -> None:
        self._gateway = gateway

    async def modules_alarms_quantity(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        _ = modules
        await self._gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": 5}}, source="ws")
        if return_data:
            return 200, {"alarmsQuantity": {"D1": 3}}
        return True


@pytest.mark.asyncio
async def test_prime_ingests_alarm_quantity_from_rest() -> None:
    """Gateway REST prime notifies on_alarm_quantity with the primed count."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []
    gateway.on_alarm_quantity(lambda event: seen.append(event))

    ok_params, ok_act = await gateway._prime()

    assert ok_params is True
    assert ok_act is True
    assert len(seen) == 1
    assert seen[0].devid == "D1"
    assert seen[0].quantity == 7
    assert seen[0].source == "rest"


@pytest.mark.asyncio
async def test_prime_skips_alarm_ingest_on_upstream_failure() -> None:
    """Non-success alarm prime responses are ignored without breaking parameter prime."""
    gateway = BragerOneGateway(api=cast(Any, _FailingAlarmsApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []
    gateway.on_alarm_quantity(lambda event: seen.append(event))

    ok_params, ok_act = await gateway._prime()

    assert ok_params is True
    assert ok_act is True
    assert seen == []


@pytest.mark.asyncio
async def test_prime_treats_non_dict_alarm_body_as_empty() -> None:
    """204 alarm prime with a non-dict body does not notify listeners."""
    gateway = BragerOneGateway(api=cast(Any, _NonDictAlarmsApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []
    gateway.on_alarm_quantity(lambda event: seen.append(event))

    await gateway._prime()

    assert seen == []


@pytest.mark.asyncio
async def test_prime_completes_when_alarm_prime_raises() -> None:
    """Alarm quantity prime failures must not abort mandatory parameter prime."""
    gateway = BragerOneGateway(api=cast(Any, _RaisingAlarmsApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []
    gateway.on_alarm_quantity(lambda event: seen.append(event))

    ok_params, ok_act = await gateway._prime()

    assert ok_params is True
    assert ok_act is True
    assert seen == []


@pytest.mark.asyncio
async def test_rest_alarm_prime_skips_stale_counts_after_ws_update() -> None:
    """REST alarm prime must not overwrite a newer WebSocket observation."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    gateway.api = cast(Any, _RacyAlarmsApi(gateway))
    seen: list[Any] = []
    gateway.on_alarm_quantity(lambda event: seen.append(event))

    await gateway._prime_alarm_quantity()

    assert gateway._alarm_quantity_cache["D1"] == 5
    assert [event.quantity for event in seen] == [5]


def test_parse_alarm_quantity_rejects_invalid_payloads() -> None:
    """Malformed alarm counts are rejected instead of coerced."""
    assert _parse_alarm_quantity(None) is None
    assert _parse_alarm_quantity(0) == 0
    assert _parse_alarm_quantity(3) == 3
    assert _parse_alarm_quantity(2.0) == 2
    assert _parse_alarm_quantity("4") == 4
    with pytest.raises(ValueError):
        _parse_alarm_quantity(True)
    with pytest.raises(ValueError):
        _parse_alarm_quantity(1.9)
    with pytest.raises(ValueError):
        _parse_alarm_quantity(-1)
    with pytest.raises(ValueError):
        _parse_alarm_quantity("")
    with pytest.raises(ValueError):
        _parse_alarm_quantity("-3")
    with pytest.raises(ValueError):
        _parse_alarm_quantity([])


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


@pytest.mark.asyncio
async def test_ingest_alarm_quantity_skips_invalid_payload_shapes() -> None:
    """Non-dict payloads and missing alarmsQuantity maps are ignored."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []
    gateway.on_alarm_quantity(lambda event: seen.append(event))

    await gateway.ingest_alarm_quantity(None, source="rest")
    await gateway.ingest_alarm_quantity({"alarmsQuantity": "not-a-map"}, source="rest")

    assert seen == []


@pytest.mark.asyncio
async def test_ingest_alarm_quantity_handles_null_and_non_numeric_counts() -> None:
    """Null counts are accepted; junk values are dropped."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []
    gateway.on_alarm_quantity(lambda event: seen.append(event))

    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": 5}}, source="rest")
    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": None}}, source="rest")
    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": "nope"}}, source="rest")
    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": True}}, source="rest")
    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": 1.9}}, source="rest")
    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": -2}}, source="rest")

    assert len(seen) == 2
    assert seen[1].quantity is None


@pytest.mark.asyncio
async def test_ingest_alarm_quantity_updates_cache_without_callbacks() -> None:
    """Count changes update cache even when no listeners are registered."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))

    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": 4}}, source="rest")
    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": 4}}, source="rest")

    assert gateway._alarm_quantity_cache["D1"] == 4


@pytest.mark.asyncio
async def test_ingest_alarm_quantity_invokes_async_callbacks() -> None:
    """Async alarm-quantity listeners are awaited via _invoke_list."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[Any] = []

    async def _on_event(event: Any) -> None:
        seen.append(event)

    gateway.on_alarm_quantity(_on_event)
    await gateway.ingest_alarm_quantity({"alarmsQuantity": {"D1": 1}}, source="ws")

    assert len(seen) == 1
    assert seen[0].quantity == 1


@pytest.mark.asyncio
async def test_ws_alarm_quantity_ingest_serializes_overlapping_callbacks() -> None:
    """Back-to-back WS changes await callbacks in order so stale work cannot win."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    callback_order: list[int] = []
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    both_done = asyncio.Event()
    pending = 2

    async def _slow_first(event: Any) -> None:
        nonlocal pending
        if event.quantity == 1:
            first_started.set()
            await release_first.wait()
        callback_order.append(event.quantity)
        pending -= 1
        if pending == 0:
            both_done.set()

    gateway.on_alarm_quantity(_slow_first)

    gateway._ws_dispatch("app:modules:alarms:quantity:change", {"alarmsQuantity": {"D1": 1}})
    await asyncio.wait_for(first_started.wait(), timeout=1.0)
    gateway._ws_dispatch("app:modules:alarms:quantity:change", {"alarmsQuantity": {"D1": 2}})
    release_first.set()
    await asyncio.wait_for(both_done.wait(), timeout=1.0)

    assert gateway._alarm_quantity_cache["D1"] == 2
    assert callback_order == [1, 2]


@pytest.mark.asyncio
async def test_overlapping_rest_alarm_primes_discard_stale_response() -> None:
    """Concurrent REST alarm primes must not let an older in-flight response win."""
    gateway = BragerOneGateway(api=cast(Any, _FakeApi()), object_id=1, modules=["D1"], ws=cast(Any, _FakeWs()))
    seen: list[int] = []

    def _on_event(event: Any) -> None:
        if event.quantity is not None:
            seen.append(event.quantity)

    gateway.on_alarm_quantity(_on_event)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    call_count = 0

    class _OverlappingApi(_FakeApi):
        async def modules_alarms_quantity(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
            nonlocal call_count
            _ = modules
            call_count += 1
            if call_count == 1:
                first_started.set()
                await release_first.wait()
                if return_data:
                    return 200, {"alarmsQuantity": {"D1": 3}}
                return True
            if return_data:
                return 200, {"alarmsQuantity": {"D1": 7}}
            return True

    gateway.api = cast(Any, _OverlappingApi())

    slow_prime = asyncio.create_task(gateway._prime_alarm_quantity())
    await asyncio.wait_for(first_started.wait(), timeout=1.0)
    await gateway._prime_alarm_quantity()
    release_first.set()
    await slow_prime

    assert gateway._alarm_quantity_cache["D1"] == 7
    assert seen == [7]
