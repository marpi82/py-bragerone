"""Tests for SPA DATE_TIME wire codec."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import cast

import pytest

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import LiveAssetsCatalog
from pybragerone.models.date_time import (
    DATE_TIME_UNSET_RAW,
    format_display_date_time,
    format_server_date_time,
    is_date_time_unit,
    parse_server_date_time,
)
from pybragerone.models.param_resolver import ParamResolver


class _DummyApi:
    """Minimal API stub for catalog construction."""


def test_parse_and_format_round_trip() -> None:
    """Wire ``yyMMddHHmm`` round-trips through display and datetime."""
    raw = "2503111430"
    parsed = parse_server_date_time(raw)
    assert parsed == datetime(2025, 3, 11, 14, 30)
    assert format_display_date_time(raw) == "2025/03/11 14:30"
    assert format_server_date_time(parsed) == raw
    assert format_server_date_time("2025/03/11 14:30") == raw


def test_unset_and_invalid_are_empty() -> None:
    """Unset sentinel and garbage wire values yield ``None``."""
    assert parse_server_date_time(DATE_TIME_UNSET_RAW) is None
    assert format_display_date_time(DATE_TIME_UNSET_RAW) is None
    assert parse_server_date_time("24H0H0H0?2") is None
    assert parse_server_date_time("1") is None
    assert format_server_date_time("not-a-date") is None


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
