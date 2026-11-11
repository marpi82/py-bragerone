"""Tests for SPA DATE_TIME wire codec."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import LiveAssetsCatalog, ParamMap
from pybragerone.models.date_time import (
    DATE_TIME_UNSET_RAW,
    _digits_wire_text,
    format_display_date_time,
    format_server_date_time,
    is_date_time_unit,
    normalize_date_time_unit_key,
    parse_server_date_time,
    unit_meta_looks_like_date_time,
)
from pybragerone.models.param import ParamStore
from pybragerone.models.param_resolver import AssetsProtocol, ParamResolver


class _DummyApi:
    """Minimal API stub for catalog construction."""


class _DateTimeAssets:
    """Assets stub that returns a DATE_TIME unit descriptor and one mapping."""

    def __init__(self, mapping: ParamMap, *, unit_meta: dict[str, Any] | None = None) -> None:
        self.mapping = mapping
        self.unit_meta = unit_meta or {"parse": "e=>DateTime.fromFormat(e,serverDateFormat)"}

    async def get_param_mapping(self, tokens: Any) -> dict[str, ParamMap]:
        return {token: self.mapping for token in tokens if token == self.mapping.key}

    async def get_module_menu(
        self,
        device_menu: int,
        permissions: Any = None,
        *,
        debug_mode: bool = False,
        devices: Any = None,
    ) -> Any:
        raise NotImplementedError

    async def list_symbols_for_permissions(
        self,
        device_menu: int,
        permissions: Any,
        *,
        devices: Any = None,
    ) -> set[str]:
        return set()

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        return {}

    async def get_unit_descriptor(self, unit_code: Any) -> dict[str, Any] | None:
        return dict(self.unit_meta)


def test_parse_and_format_round_trip() -> None:
    """Wire ``yyMMddHHmm`` round-trips through display and datetime."""
    raw = "2503111430"
    parsed = parse_server_date_time(raw)
    assert parsed == datetime(2025, 3, 11, 14, 30)
    assert format_display_date_time(raw) == "2025/03/11 14:30"
    assert format_server_date_time(parsed) == raw
    assert format_server_date_time("2025/03/11 14:30") == raw
    assert format_server_date_time(2503111430) == raw
    assert format_server_date_time(2503111430.0) == raw
    assert parse_server_date_time(parsed) == parsed


def test_json_number_zero_pads_leading_year_digits() -> None:
    """JSON numbers drop leading zeros; restore 10-digit ``yyMMddHHmm``."""
    # Year 2005-03-11 14:30 as a JSON number (leading 0 dropped).
    assert parse_server_date_time(503111430) == datetime(2005, 3, 11, 14, 30)
    assert format_display_date_time(503111430) == "2005/03/11 14:30"
    assert format_server_date_time(503111430) == "0503111430"
    # Unset sentinel ``0001011200`` as a JSON number.
    assert parse_server_date_time(1011200) is None
    assert format_display_date_time(1011200) is None
    assert format_server_date_time(1011200) == DATE_TIME_UNSET_RAW
    assert parse_server_date_time(1011200.0) is None
    assert format_server_date_time(1011200.0) == DATE_TIME_UNSET_RAW
    # Too many digits / non-integral float stay invalid.
    assert parse_server_date_time(12345678901) is None
    assert parse_server_date_time(2503111430.5) is None
    assert parse_server_date_time(-2503111430) is None
    # ``bool`` is an ``int`` subclass — helper must reject it explicitly.
    assert _digits_wire_text(True) is None
    assert _digits_wire_text(False) is None


def test_aware_datetime_rejected() -> None:
    """Timezone-aware values must not silently drop tzinfo (wrong wall clock)."""
    aware = datetime(2025, 3, 11, 13, 30, tzinfo=UTC)
    assert parse_server_date_time(aware) is None
    assert format_server_date_time(aware) is None
    assert format_display_date_time(aware) is None


def test_calendar_edge_cases() -> None:
    """Leap day accepted; hour 24 / minute 60 / non-leap Feb 29 rejected."""
    assert parse_server_date_time("2402291200") == datetime(2024, 2, 29, 12, 0)
    assert parse_server_date_time("2502291200") is None
    assert parse_server_date_time("2503112400") is None
    assert parse_server_date_time("2503111460") is None


def test_unset_and_invalid_are_empty() -> None:
    """Unset sentinel and garbage wire values yield ``None``."""
    assert parse_server_date_time(DATE_TIME_UNSET_RAW) is None
    assert format_display_date_time(DATE_TIME_UNSET_RAW) is None
    assert parse_server_date_time("24H0H0H0?2") is None
    assert parse_server_date_time("1") is None
    assert parse_server_date_time(None) is None
    assert parse_server_date_time(True) is None
    assert parse_server_date_time("") is None
    assert parse_server_date_time("2513139999") is None  # invalid month/day/time
    assert format_server_date_time("not-a-date") is None
    assert format_server_date_time(None) is None
    assert format_server_date_time(True) is None
    assert format_server_date_time("") is None
    assert format_server_date_time("   ") is None
    assert format_server_date_time(DATE_TIME_UNSET_RAW) == DATE_TIME_UNSET_RAW
    assert format_server_date_time("2503111430") == "2503111430"
    assert format_server_date_time("2513139999") is None
    assert format_server_date_time(object()) is None


def test_normalize_date_time_unit_key_variants() -> None:
    """Accept SPA named/numeric/hex keys; reject empty and non-DATE_TIME values."""
    assert normalize_date_time_unit_key(None) is None
    assert normalize_date_time_unit_key(True) is None
    assert normalize_date_time_unit_key(52) is None
    assert normalize_date_time_unit_key(9999.5) is None
    assert normalize_date_time_unit_key(9999.0) == "9999"
    assert normalize_date_time_unit_key("   ") is None
    assert normalize_date_time_unit_key("DATE_TIME") == "DATE_TIME"
    assert normalize_date_time_unit_key("date_time") == "9999"
    assert normalize_date_time_unit_key("9999") == "9999"
    assert normalize_date_time_unit_key("0x270f") == "9999"
    assert normalize_date_time_unit_key("0X270F") == "9999"
    assert normalize_date_time_unit_key("0x0000270f") == "9999"
    assert normalize_date_time_unit_key("0x") is None
    assert normalize_date_time_unit_key("0xZZZZ") is None
    assert normalize_date_time_unit_key("0x1234") is None
    assert normalize_date_time_unit_key("52") is None


def test_unit_meta_looks_like_date_time_variants() -> None:
    """Detect DATE_TIME parse meta including callable tree-sitter materializations."""
    assert unit_meta_looks_like_date_time("not-a-dict") is False
    assert unit_meta_looks_like_date_time({}) is False
    assert unit_meta_looks_like_date_time({"parse": 123}) is False
    assert unit_meta_looks_like_date_time({"parse": lambda e: e}) is True
    assert unit_meta_looks_like_date_time({"parse": lambda e: e, "text": "units.1"}) is False
    assert unit_meta_looks_like_date_time({"parse": "yyMMddHHmm"}) is True
    assert unit_meta_looks_like_date_time({"parse": "plain"}) is False
    # Non-dict Mapping (e.g. catalog copies) still counts.
    from types import MappingProxyType

    assert unit_meta_looks_like_date_time(MappingProxyType({"parse": "yyMMddHHmm"})) is True


def test_is_date_time_unit_keys() -> None:
    """Named and numeric CustomUnit codes identify DATE_TIME."""
    assert is_date_time_unit(unit_code="DATE_TIME")
    assert is_date_time_unit(unit_code=9999)
    assert is_date_time_unit(unit_code=0x270F)
    assert is_date_time_unit(unit_meta={"parse": "e=>DateTime.fromFormat(e,serverDateFormat)"})
    assert not is_date_time_unit(unit_code=52)
    assert not is_date_time_unit(unit_meta={"text": "units.1"})


def test_apply_unit_display_value_date_time() -> None:
    """Resolver display helper uses the DATE_TIME codec before numeric transforms."""
    assert ParamResolver._apply_unit_display_value("2501011200", unit_code="DATE_TIME") == "2025/01/01 12:00"
    assert ParamResolver._apply_unit_display_value(DATE_TIME_UNSET_RAW, unit_code=9999) is None
    parse_only = {"parse": "e=>DateTime.fromFormat(e,serverDateFormat)"}
    assert ParamResolver._apply_unit_display_value("2503111430", unit_meta=parse_only) == "2025/03/11 14:30"
    assert ParamResolver._unit_options_map(parse_only) is None


@pytest.mark.asyncio
async def test_unit_display_value_parse_only_is_none() -> None:
    """Parse-only DATE_TIME meta must not become ``ResolvedValue.unit`` options."""
    resolver = ParamResolver.__new__(ParamResolver)
    parse_only = {"parse": "e=>DateTime.fromFormat(e,serverDateFormat)"}
    assert await resolver._unit_display_value(parse_only) is None
    assert await resolver._unit_display_value({"value": "e=>e*0.1"}) is None


@pytest.mark.asyncio
async def test_resolve_value_date_time_display_and_unit_none() -> None:
    """End-to-end: DATE_TIME wire formats to SPA display; unit stays unlabeled."""
    mapping = ParamMap(
        key="CZAS_ZAKONCZENIA_TRYBU_URLOP_WRITE",
        group="P9",
        paths={"value": [{"group": "P9", "number": 1, "use": "v"}]},
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={"name": "parameters.CZAS_ZAKONCZENIA_TRYBU_URLOP_WRITE", "value": [{"group": "P9", "number": 1, "use": "v"}]},
    )
    store = ParamStore()
    store.upsert("P9.v1", "2503111430")
    store.upsert("P9.u1", 9999)
    resolver = ParamResolver(
        store=store,
        assets=cast(AssetsProtocol, _DateTimeAssets(mapping)),
        lang="en",
    )
    resolved = await resolver.resolve_value("CZAS_ZAKONCZENIA_TRYBU_URLOP_WRITE")
    assert resolved.value == "2025/03/11 14:30"
    assert resolved.unit is None
    assert resolved.address == "P9.v1"

    # Address known but family absent: cover the ``fam is None`` branch beside the apply call.
    empty = ParamResolver(
        store=ParamStore(),
        assets=cast(AssetsProtocol, _DateTimeAssets(mapping)),
        lang="en",
    )
    missing = await empty.resolve_value("CZAS_ZAKONCZENIA_TRYBU_URLOP_WRITE")
    assert missing.value is None
    assert missing.unit is None
    assert missing.address == "P9.v1"


def test_captured_index_keeps_date_time_parse_entry() -> None:
    """Captured index units table retains CustomUnit DATE_TIME ``parse`` when present."""
    index_path = Path(__file__).parent / "assets" / "index" / "index-1TABHy-0.js"
    if not index_path.is_file() or index_path.stat().st_size == 0:
        pytest.skip("captured index asset missing")
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _DummyApi()))
    table = catalog._parse_units_descriptor_table_from_index(index_path.read_bytes())
    entry = table.get("9999")
    assert isinstance(entry, dict)
    assert "parse" in entry
