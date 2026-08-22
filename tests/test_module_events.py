"""Tests for AlarmName parsing and alarm/activity REST helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from pytest_httpx import HTTPXMock

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models import Token
from pybragerone.models.alarm_names import parse_alarm_name_enum, resolve_alarm_label
from pybragerone.models.api import ModuleActivity, ModuleAlarm

API = "https://io.brager.pl"


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


def _status_payload(result: object) -> tuple[int, object]:
    assert isinstance(result, tuple) and len(result) == 2
    status, data = result
    assert isinstance(status, int)
    return status, data


def test_parse_alarm_name_enum_bidirectional() -> None:
    """Accept both ``id: ERROR_*`` and ``ERROR_*: id`` pairs from SPA chunks."""
    source = """
    const AlarmName = {
      0: "ERROR_TEMPERATURA_KOTLA",
      ERROR_BRAK_PALIWA: 38,
      "ERROR_QUOTED_KEY": 12,
      54: 'ERROR_PELLET_NIEUDANE_ROZPALANIE',
    };
    """
    names = parse_alarm_name_enum(source)
    assert names[0] == "ERROR_TEMPERATURA_KOTLA"
    assert names[38] == "ERROR_BRAK_PALIWA"
    assert names[12] == "ERROR_QUOTED_KEY"
    assert names[54] == "ERROR_PELLET_NIEUDANE_ROZPALANIE"


def test_parse_alarm_name_enum_accepts_bytes_source() -> None:
    """Bytes chunks decode before regex extraction."""
    assert parse_alarm_name_enum(b'7:"ERROR_FROM_BYTES"') == {7: "ERROR_FROM_BYTES"}


def test_parse_alarm_name_enum_accepts_bytearray_source() -> None:
    """Bytearray chunks decode like bytes before regex extraction."""
    assert parse_alarm_name_enum(bytearray(b'8:"ERROR_FROM_BYTEARRAY"')) == {8: "ERROR_FROM_BYTEARRAY"}


def test_parse_alarm_name_enum_name_a_and_name_b_patterns() -> None:
    """Each regex alternative is exercised in isolation."""
    assert parse_alarm_name_enum("ERROR_LEFT: 11") == {11: "ERROR_LEFT"}
    assert parse_alarm_name_enum('12: "ERROR_RIGHT"') == {12: "ERROR_RIGHT"}


def test_parse_alarm_name_enum_obfuscated_bracket_assignments() -> None:
    """Obfuscated SPA chunks use ``obj['ERROR_*']=0xNN`` enum assignments."""
    source = """
    _0xabc=>{return _0xabc[_0xabc['ERROR_TEMPERATURA_KOTLA']=0x0]='ERROR_TEMPERATURA_KOTLA',
    _0xabc['ERROR_BRAK_PALIWA']=0x26,
    _0xabc["ERROR_PELLET_NIEUDANE_ROZPALANIE"]=54]}
    """
    names = parse_alarm_name_enum(source)
    assert names[0] == "ERROR_TEMPERATURA_KOTLA"
    assert names[0x26] == "ERROR_BRAK_PALIWA"
    assert names[54] == "ERROR_PELLET_NIEUDANE_ROZPALANIE"


def test_resolve_alarm_label_after_obfuscated_enum_parse() -> None:
    """Bracket-parsed ``ERROR_*`` keys resolve via ``errors.*`` i18n — never shown raw."""
    source = "_0xabc['ERROR_BRAK_PALIWA']=0x26,_0xabc['ERROR_PELLET_NIEUDANE_ROZPALANIE']=54"
    names = parse_alarm_name_enum(source)
    errors = {
        "ERROR_BRAK_PALIWA": "Brak paliwa",
        "ERROR_PELLET_NIEUDANE_ROZPALANIE": "Nieudane rozpalanie",
    }
    assert resolve_alarm_label(38, alarm_names=names, errors_i18n=errors) == "Brak paliwa"
    assert resolve_alarm_label(54, alarm_names=names, errors_i18n=errors) == "Nieudane rozpalanie"


def test_resolve_alarm_label_uses_errors_i18n() -> None:
    """Labels come from ``errors.*``; missing keys stay unresolved."""
    names = {38: "ERROR_BRAK_PALIWA"}
    assert resolve_alarm_label(38, alarm_names=names, errors_i18n={"ERROR_BRAK_PALIWA": "Brak paliwa"}) == "Brak paliwa"
    assert resolve_alarm_label(38, alarm_names=names, errors_i18n={}) is None
    assert resolve_alarm_label(99, alarm_names=names, errors_i18n={"ERROR_BRAK_PALIWA": "Brak paliwa"}) is None
    assert resolve_alarm_label(38, alarm_names=names, errors_i18n={"ERROR_BRAK_PALIWA": "  "}) is None
    assert resolve_alarm_label(38, alarm_names=names, errors_i18n={"ERROR_BRAK_PALIWA": 42}) is None


def test_module_alarm_activity_dto_aliases() -> None:
    """DTOs accept SPA field aliases without dropping extras."""
    alarm = ModuleAlarm.model_validate({"id": 38, "devid": "D1", "created_at": "t0", "extra": 1})
    assert alarm.id == 38
    assert alarm.model_extra is not None
    activity = ModuleActivity.model_validate(
        {"id": 1, "name": "parameters.PARAM_1", "prevValue": 2, "state": "success", "user": "u"}
    )
    assert activity.prev_value == 2
    assert activity.user == "u"


@pytest.mark.asyncio
async def test_modules_alarms_and_activity_list_helpers(api_client: BragerOneApiClient, httpx_mock: HTTPXMock) -> None:
    """List/quantity helpers POST the SPA payload shape and honor return_data."""
    alarms_url = f"{API}/v1/modules/alarms"
    history_url = f"{API}/v1/modules/alarms/history"
    alarms_qty_url = f"{API}/v1/modules/alarms/quantity"
    activity_url = f"{API}/v1/modules/activity"

    httpx_mock.add_response(method="POST", url=alarms_url, json={"status": True, "alarms": [{"id": 38, "devid": "D1"}]})
    status, data = _status_payload(await api_client.modules_alarms(["D1"], page=1, limit=20, return_data=True))
    assert status == 200
    assert isinstance(data, dict)
    assert data["alarms"][0]["id"] == 38
    request = httpx_mock.get_request(url=alarms_url)
    assert request is not None
    assert b'"page":1' in request.content
    assert b'"limit":20' in request.content

    httpx_mock.add_response(
        method="POST",
        url=history_url,
        json={"status": True, "alarms": {"data": [{"id": 1, "devid": "D1", "finished_at": "t1"}]}},
    )
    assert await api_client.modules_alarms_history(["D1"]) is True

    httpx_mock.add_response(method="POST", url=alarms_qty_url, json={"alarmsQuantity": {"D1": 2}})
    qty_status, qty_data = _status_payload(await api_client.modules_alarms_quantity(["D1"], return_data=True))
    assert qty_status == 200
    assert qty_data == {"alarmsQuantity": {"D1": 2}}

    httpx_mock.add_response(
        method="POST",
        url=activity_url,
        json={"status": True, "activities": {"data": [{"id": 9, "name": "parameters.PARAM_1", "state": "success"}]}},
    )
    act_status, act_data = _status_payload(await api_client.modules_activity(["D1"], return_data=True))
    assert act_status == 200
    assert isinstance(act_data, dict)
