"""Tests for BragerOneApiClient REST object/module/command surfaces."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from pytest_httpx import HTTPXMock

from pybragerone.api import BragerOneApiClient
from pybragerone.api.client import ApiError, _ModulesConnectShape
from pybragerone.models import Token

API = "https://io.brager.pl"

OBJECT_PAYLOAD = {
    "id": 1,
    "name": "Home",
    "addressCountry": "PL",
    "addressCity": "Warsaw",
}

MODULE_PAYLOAD = {
    "devid": "FTTCTBSLCE",
    "name": "Module name",
    "gateway": {
        "address": "gateway-addr",
        "interface": None,
        "version": "1.0",
    },
    "deviceMenu": 0,
    "deviceLanguageVariant": 0,
    "devices": [],
    "services": [],
    "permissions": [],
    "acceptedAt": 0,
    "connectedAt": 0,
    "moduleAlarms": 0,
    "parameterSchemas": [],
    "id": 1,
    "moduleAddress": "module-addr",
    "moduleInterface": None,
    "moduleVersion": "2.08",
    "moduleServices": [],
    "moduleTitle": "HT DasPell GL 37kW",
    "isAcceptedAt": "2026-04-06T00:00:00Z",
    "isConnectedAt": "2026-04-06T00:00:00Z",
}


def _status_payload(result: tuple[int, Any] | bool) -> tuple[int, Any]:
    """Narrow command/prime ``return_data=True`` results to a status/payload tuple."""
    assert isinstance(result, tuple)
    return result


MODULE_CARD_PAYLOAD = {
    "id": 1,
    "moduleId": 2,
    "clientFullName": "Ada Lovelace",
    "clientPhoneNumber": "123",
    "clientAddressStreetAndNumber": "1 Analytic St",
    "clientAddressPostalCode": "00-000",
    "clientAddressCity": "Warsaw",
    "createdAt": "2026-04-06T00:00:00Z",
    "updatedAt": "2026-04-06T00:00:00Z",
}


@pytest.fixture
async def api_client() -> AsyncIterator[BragerOneApiClient]:
    """Authenticated client that skips network login."""
    client = BragerOneApiClient(validate_on_start=False)
    client._token = Token(
        access_token="T1",
        refresh_token="R1",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    try:
        yield client
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_system_version_unwraps_wrapper(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """Unauthenticated ``/system/version`` unwraps ``{"version": {...}}``."""
    url = f"{API}/v1/system/version?container=BragerOne&platform=0"
    httpx_mock.add_response(
        method="GET",
        url=url,
        json={"version": {"version": "2.08", "devMode": False}},
    )
    info = await api_client.get_system_version()
    assert info.version == "2.08"
    assert info.devMode is False


@pytest.mark.asyncio
async def test_get_objects_accepts_data_objects_and_list_shapes(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """``get_objects`` tolerates ``data``, ``objects``, and bare-list payloads."""
    url = f"{API}/v1/objects"
    httpx_mock.add_response(method="GET", url=url, json={"data": [OBJECT_PAYLOAD]})
    from_data = await api_client.get_objects()
    assert from_data[0].id == 1
    assert from_data[0].name == "Home"

    httpx_mock.add_response(method="GET", url=url, json={"objects": [OBJECT_PAYLOAD]})
    from_objects = await api_client.get_objects()
    assert from_objects[0].id == 1

    httpx_mock.add_response(method="GET", url=url, json=[OBJECT_PAYLOAD])
    from_list = await api_client.get_objects()
    assert from_list[0].addressCountry == "PL"

    httpx_mock.add_response(method="GET", url=url, json={"unexpected": True})
    assert await api_client.get_objects() == []


@pytest.mark.asyncio
async def test_get_objects_returns_empty_on_non_200(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """Non-200 object list responses become an empty list rather than an error."""
    httpx_mock.add_response(method="GET", url=f"{API}/v1/objects", status_code=201, json={"data": [OBJECT_PAYLOAD]})
    assert await api_client.get_objects() == []


@pytest.mark.asyncio
async def test_get_object_success_and_payload_errors(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """``get_object`` validates details and rejects unexpected payloads."""
    url = f"{API}/v1/objects/1"
    httpx_mock.add_response(
        method="GET",
        url=url,
        json={"object": OBJECT_PAYLOAD, "status": "SUCCESS"},
    )
    details = await api_client.get_object(1)
    assert details.status == "SUCCESS"
    assert details.object.id == 1

    httpx_mock.add_response(method="GET", url=url, status_code=404, json={"message": "missing"})
    with pytest.raises(ApiError) as missing:
        await api_client.get_object(1)
    assert missing.value.status == 404

    httpx_mock.add_response(method="GET", url=url, json=[OBJECT_PAYLOAD])
    with pytest.raises(ApiError) as unexpected:
        await api_client.get_object(1)
    assert unexpected.value.status == 500


@pytest.mark.asyncio
async def test_get_user_permissions_dict_and_list(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """User permissions accept both wrapped dict and raw list payloads."""
    url = f"{API}/v1/user/permissions"
    httpx_mock.add_response(method="GET", url=url, json={"permissions": ["DISPLAY_MENU_OBJECTS"]})
    wrapped = await api_client.get_user_permissions()
    assert wrapped[0].name == "DISPLAY_MENU_OBJECTS"

    httpx_mock.add_response(method="GET", url=url, json=["DISPLAY_MENU_DHW"])
    listed = await api_client.get_user_permissions()
    assert listed[0].name == "DISPLAY_MENU_DHW"

    httpx_mock.add_response(method="GET", url=url, status_code=403, json={"message": "denied"})
    with pytest.raises(ApiError) as denied:
        await api_client.get_user_permissions()
    assert denied.value.status == 403


@pytest.mark.asyncio
async def test_get_object_permissions_dict_and_list(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """Object permissions accept both wrapped dict and raw list payloads."""
    url = f"{API}/v1/objects/7/permissions"
    httpx_mock.add_response(method="GET", url=url, json={"permissions": ["SUBMISSION_CREATE"]})
    wrapped = await api_client.get_object_permissions(7)
    assert wrapped[0].name == "SUBMISSION_CREATE"

    httpx_mock.add_response(method="GET", url=url, json=["DISPLAY_PARAMETER_LEVEL_1"])
    listed = await api_client.get_object_permissions(7)
    assert listed[0].name == "DISPLAY_PARAMETER_LEVEL_1"


@pytest.mark.asyncio
async def test_get_modules_shapes_and_non_200(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """``get_modules`` accepts ``data``/list shapes and raises on non-200."""
    url = f"{API}/v1/modules?page=1&limit=999&group_id=3"
    httpx_mock.add_response(method="GET", url=url, json={"data": [MODULE_PAYLOAD]})
    from_data = await api_client.get_modules(3)
    assert from_data[0].devid == "FTTCTBSLCE"
    assert from_data[0].moduleInterface == ""

    httpx_mock.add_response(method="GET", url=url, json=[MODULE_PAYLOAD])
    from_list = await api_client.get_modules(3)
    assert from_list[0].id == 1

    httpx_mock.add_response(method="GET", url=url, status_code=201, json={"data": [MODULE_PAYLOAD]})
    with pytest.raises(ApiError) as err:
        await api_client.get_modules(3)
    assert err.value.status == 201

    httpx_mock.add_response(method="GET", url=url, json={"unexpected": True})
    assert await api_client.get_modules(3) == []

    httpx_mock.add_response(
        method="GET",
        url=url,
        json={"data": [MODULE_PAYLOAD, {"devid": None, "not": "a-module"}, "also-bad"]},
    )
    resilient = await api_client.get_modules(3)
    assert len(resilient) == 1
    assert resilient[0].id == MODULE_PAYLOAD["id"]


@pytest.mark.asyncio
async def test_get_module_card_success_and_errors(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """``get_module_card`` validates the card and rejects bad responses."""
    url = f"{API}/v1/modules/FTTCTBSLCE/card"
    httpx_mock.add_response(method="GET", url=url, json=MODULE_CARD_PAYLOAD)
    card = await api_client.get_module_card("FTTCTBSLCE")
    assert card.clientFullName == "Ada Lovelace"
    assert card.moduleId == 2

    httpx_mock.add_response(method="GET", url=url, status_code=404, json={"message": "missing"})
    with pytest.raises(ApiError):
        await api_client.get_module_card("FTTCTBSLCE")

    httpx_mock.add_response(method="GET", url=url, json=["not", "a", "card"])
    with pytest.raises(ApiError) as unexpected:
        await api_client.get_module_card("FTTCTBSLCE")
    assert unexpected.value.status == 500


@pytest.mark.asyncio
async def test_modules_connect_empty_success_and_all_fail(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """Empty module lists succeed locally; HTTP 200 binds; all failures return False."""
    assert await api_client.modules_connect("NS", []) is True

    url = f"{API}/v1/modules/connect"
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})
    assert await api_client.modules_connect("NS", ["M1"], group_id=9, engine_sid="ENG") is True

    for _ in range(6):
        httpx_mock.add_response(method="POST", url=url, status_code=201, json={"message": "accepted-not-bound"})
    other = BragerOneApiClient(validate_on_start=False)
    other._token = api_client._token
    try:
        assert await other.modules_connect("NS", ["M2"], group_id=9, engine_sid="ENG") is False
    finally:
        await other.close()


@pytest.mark.asyncio
async def test_modules_connect_never_reposts_stale_sid(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """After a successful bind, reconnect must POST the new SID — never the cached one.

    Field zombies showed ``modules.connect`` returning 200 while still sending the
    pre-disconnect SID from ``_connect_variant``, leaving the new Socket.IO session unbound.
    """
    url = f"{API}/v1/modules/connect"
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})
    assert await api_client.modules_connect("NS-OLD", ["M1"], group_id=9, engine_sid="ENG-OLD") is True
    first = json.loads(httpx_mock.get_requests()[-1].content)
    assert first.get("wsid") == "NS-OLD" or first.get("sid") == "NS-OLD"

    before = len(httpx_mock.get_requests())
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})
    assert await api_client.modules_connect("NS-NEW", ["M1"], group_id=9, engine_sid="ENG-NEW") is True
    second_bodies = [json.loads(req.content) for req in httpx_mock.get_requests()[before:]]
    assert second_bodies, "expected at least one modules.connect attempt with the new SID"
    for body in second_bodies:
        assert body.get("wsid") not in {"NS-OLD", "ENG-OLD"}
        assert body.get("sid") not in {"NS-OLD", "ENG-OLD"}
        assert body.get("wsid") in {"NS-NEW", "ENG-NEW"} or body.get("sid") in {"NS-NEW", "ENG-NEW"}
    # Preferred shape from the first success should be tried first with the *new* namespace SID.
    assert second_bodies[0].get("wsid") == "NS-NEW" or second_bodies[0].get("sid") == "NS-NEW"


@pytest.mark.asyncio
async def test_modules_connect_shape_can_include_and_skip_group_id(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """The cached modules.connect shape must remember group_id inclusion."""
    url = f"{API}/v1/modules/connect"

    # 1) First bind: force success on the 3rd candidate (wsid+group_id body),
    # so the cached shape includes group_id.
    httpx_mock.add_response(method="POST", url=url, status_code=201, json={"message": "accepted-not-bound"})
    httpx_mock.add_response(method="POST", url=url, status_code=201, json={"message": "accepted-not-bound"})
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})
    assert await api_client.modules_connect("NS-1", ["M1"], group_id=9, engine_sid="ENG-1") is True

    # 2) Reconnect: call with group_id=None, so cached shape says "include_group_id=True"
    # but _body_from_shape must *skip* adding group_id.
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})
    assert await api_client.modules_connect("NS-2", ["M1"], group_id=None, engine_sid="ENG-2") is True

    # 3) Re-establish cached shape with "include_group_id=True".
    # The previous call succeeded with group_id=None and can reset the cached
    # shape to not include group_id. Force-bind on the 3rd candidate
    # (wsid+group_id body) so the cache is flipped back to include_group_id.
    httpx_mock.add_response(method="POST", url=url, status_code=201, json={"message": "accepted-not-bound"})
    httpx_mock.add_response(method="POST", url=url, status_code=201, json={"message": "accepted-not-bound"})
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})
    assert await api_client.modules_connect("NS-3", ["M1"], group_id=9, engine_sid="ENG-3") is True

    # 4) Now that cached shape includes group_id again, exercise the true branch
    # in `_body_from_shape` where it actually writes body["group_id"].
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})
    assert await api_client.modules_connect("NS-4", ["M1"], group_id=9, engine_sid="ENG-4") is True

    # 5) wsid_ns empty => skip the preferred-shape wsid branch and the wsid fallback.
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})
    assert await api_client.modules_connect("", ["M1"], group_id=9, engine_sid="ENG-5") is True

    # 6) engine_sid == wsid_ns => skip the engine_sid branches.
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})
    assert await api_client.modules_connect("NS-6", ["M1"], group_id=9, engine_sid="NS-6") is True


@pytest.mark.asyncio
async def test_modules_connect_filters_non_string_sid_candidates(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """Non-string SID values must be filtered out before POST retries."""
    # Provide invalid runtime types (the signature says str, but we explicitly
    # test the filtering branch that continues when body_sid is not a string).
    wsid_bad = cast(str, 123)
    engine_bad = cast(str, 456)
    result = await api_client.modules_connect(
        wsid_ns=wsid_bad,
        modules=["M1"],
        group_id=9,
        engine_sid=engine_bad,
    )
    assert result is False
    assert httpx_mock.get_requests() == []


@pytest.mark.asyncio
async def test_modules_connect_cached_shape_group_id_branch(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """Force the cached-shape group_id branch in `_body_from_shape`."""
    api_client._connect_shape = _ModulesConnectShape(sid_key="wsid", include_group_id=True)
    url = f"{API}/v1/modules/connect"
    httpx_mock.add_response(method="POST", url=url, status_code=200, json={})

    assert await api_client.modules_connect("NS", ["M1"], group_id=9, engine_sid="ENG") is True
    sent = json.loads(httpx_mock.get_requests()[-1].content)
    assert sent["group_id"] == "9"


@pytest.mark.asyncio
async def test_prime_helpers_return_bool_or_payload(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """Prime helpers return a boolean unless ``return_data`` is requested."""
    params_url = f"{API}/v1/modules/parameters"
    activity_url = f"{API}/v1/modules/activity/quantity"
    payload = {"DEV1": {"P4": {"v1": {"value": 1}}}}

    httpx_mock.add_response(method="POST", url=params_url, json=payload)
    assert await api_client.modules_parameters_prime(["M1"]) is True

    httpx_mock.add_response(method="POST", url=params_url, json=payload)
    status, data = _status_payload(await api_client.modules_parameters_prime(["M1"], return_data=True))
    assert status == 200
    assert data == payload

    httpx_mock.add_response(method="POST", url=activity_url, status_code=204)
    assert await api_client.modules_activity_quantity_prime(["M1"]) is True

    httpx_mock.add_response(method="POST", url=activity_url, json={"activityQuantity": {}})
    act_status, act_data = _status_payload(await api_client.modules_activity_quantity_prime(["M1"], return_data=True))
    assert act_status == 200
    assert act_data == {"activityQuantity": {}}


@pytest.mark.asyncio
async def test_module_command_and_raw_include_optional_fields(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """Command helpers merge optional fields and honor ``return_data``."""
    cmd_url = f"{API}/v1/module/command"
    raw_url = f"{API}/v1/module/command/raw"

    httpx_mock.add_response(method="POST", url=cmd_url, status_code=201, json={"ok": True})
    assert (
        await api_client.module_command(
            devid="DEV1",
            pool="P4",
            parameter="v8",
            value=42,
            parameter_name="PARAM_66",
            unit=1,
            extra_payload={"note": "ha"},
        )
        is True
    )
    sent = httpx_mock.get_requests()[-1]
    assert json.loads(sent.content) == {
        "devid": "DEV1",
        "pool": "P4",
        "parameter": "v8",
        "value": 42,
        "parameterName": "PARAM_66",
        "unit": 1,
        "note": "ha",
    }

    httpx_mock.add_response(method="POST", url=cmd_url, json={"echo": 1})
    status, data = _status_payload(
        await api_client.module_command(
            devid="DEV1",
            pool="P4",
            parameter="v8",
            value=1,
            return_data=True,
        )
    )
    assert status == 200
    assert data == {"echo": 1}

    httpx_mock.add_response(method="POST", url=raw_url, status_code=202, json={})
    assert (
        await api_client.module_command_raw(
            devid="DEV1",
            command="MODULE_RESTART",
            value="ONLINE",
            extra_payload={"force": True},
        )
        is True
    )
    raw_sent = httpx_mock.get_requests()[-1]
    assert json.loads(raw_sent.content) == {
        "devid": "DEV1",
        "command": "MODULE_RESTART",
        "value": "ONLINE",
        "force": True,
    }

    httpx_mock.add_response(method="POST", url=raw_url, json={"queued": True})
    raw_status, raw_data = _status_payload(
        await api_client.module_command_raw(
            devid="DEV1",
            command="MODULE_RESTART",
            return_data=True,
        )
    )
    assert raw_status == 200
    assert raw_data == {"queued": True}


@pytest.mark.asyncio
async def test_module_command_auto_routes_and_rejects_ambiguous(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """``module_command_auto`` picks a route and rejects mixed or incomplete payloads."""
    with pytest.raises(ValueError, match="Ambiguous"):
        await api_client.module_command_auto(devid="DEV1", command="RESTART", pool="P4", parameter="v1")

    with pytest.raises(ValueError, match="Missing command route"):
        await api_client.module_command_auto(devid="DEV1", value=1)

    httpx_mock.add_response(method="POST", url=f"{API}/v1/module/command/raw", status_code=204)
    assert await api_client.module_command_auto(devid="DEV1", command="MODULE_RESTART") is True

    httpx_mock.add_response(method="POST", url=f"{API}/v1/module/command", status_code=200, json={})
    assert await api_client.module_command_auto(devid="DEV1", pool="P4", parameter="v8", value=3) is True


def test_is_duplicate_token_error_detects_known_messages() -> None:
    """Duplicate-token helper recognizes known backend messages."""
    assert BragerOneApiClient._is_duplicate_token_error({"message": "Duplicate entry for key"})
    assert BragerOneApiClient._is_duplicate_token_error({"message": "ER_DUP_ENTRY"})
    assert not BragerOneApiClient._is_duplicate_token_error({"message": "unrelated"})
    assert not BragerOneApiClient._is_duplicate_token_error("not-a-dict")
