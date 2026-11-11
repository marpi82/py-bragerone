"""CLI DATE_TIME write preparation (unit meta + raw bounds)."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from pybragerone.cli import _prepare_symbol_write_value
from pybragerone.models.date_time import DATE_TIME_UNSET_RAW
from pybragerone.models.param_resolver import ParamResolver


def _resolver() -> ParamResolver:
    return cast(ParamResolver, MagicMock(spec=ParamResolver))


@pytest.mark.asyncio
async def test_prepare_date_time_via_unit_code() -> None:
    """Named unit code encodes display → wire."""
    ok, prepared, err = await _prepare_symbol_write_value(
        resolver=_resolver(),
        desc={"unit_code": "DATE_TIME"},
        requested_value="2025/03/11 14:30",
    )
    assert ok is True
    assert prepared == "2503111430"
    assert err is None


@pytest.mark.asyncio
async def test_prepare_date_time_via_parse_only_unit_meta() -> None:
    """Parse-only mapping meta is enough when unit_code is absent."""
    desc: dict[str, Any] = {
        "mapping": {
            "units_source": {"parse": "e=>DateTime.fromFormat(e,serverDateFormat)"},
        },
    }
    ok, prepared, err = await _prepare_symbol_write_value(
        resolver=_resolver(),
        desc=desc,
        requested_value="2025/03/11 14:30",
    )
    assert ok is True
    assert prepared == "2503111430"
    assert err is None


@pytest.mark.asyncio
async def test_prepare_date_time_rejects_invalid() -> None:
    """Garbage input stays a validation error (does not fall through to numeric)."""
    ok, prepared, err = await _prepare_symbol_write_value(
        resolver=_resolver(),
        desc={"unit": 9999},
        requested_value="not-a-date",
    )
    assert ok is False
    assert prepared == "not-a-date"
    assert err is not None
    assert "invalid DATE_TIME" in err


@pytest.mark.asyncio
async def test_prepare_date_time_applies_raw_min_max() -> None:
    """Encoded wire is checked against DATE_TIME-shaped min/max chronologically."""
    ok, prepared, err = await _prepare_symbol_write_value(
        resolver=_resolver(),
        desc={"unit_code": 9999, "min": "2501010000", "max": "2502010000"},
        requested_value="2025/03/11 14:30",
    )
    assert ok is False
    assert prepared == "2503111430"
    assert err is not None
    assert "out of range" in err


@pytest.mark.asyncio
async def test_prepare_date_time_bounds_cross_luxon_century() -> None:
    """Chronological bounds beat numeric wire order across yy 61-99 vs 00-60."""
    # Numerically ``65…`` (1965) > ``25…`` (2025), but 2025 is inside [1965, 2060].
    ok, prepared, err = await _prepare_symbol_write_value(
        resolver=_resolver(),
        desc={"unit_code": "DATE_TIME", "min": "6501010000", "max": "6001010000"},
        requested_value="2025/03/11 14:30",
    )
    assert ok is True
    assert prepared == "2503111430"
    assert err is None


@pytest.mark.asyncio
async def test_prepare_date_time_numeric_bounds_fallback() -> None:
    """Non-date numeric bounds still gate via float compare of the wire digits."""
    ok, prepared, err = await _prepare_symbol_write_value(
        resolver=_resolver(),
        desc={"unit_code": 9999, "min": 0, "max": 1000},
        requested_value="2025/03/11 14:30",
    )
    assert ok is False
    assert prepared == "2503111430"
    assert err is not None
    assert "out of range" in err


@pytest.mark.asyncio
async def test_prepare_date_time_unset_bypasses_bounds() -> None:
    """Clearing the register with the unset sentinel is always allowed."""
    ok, prepared, err = await _prepare_symbol_write_value(
        resolver=_resolver(),
        desc={"unit_code": "DATE_TIME", "min": "2501010000", "max": "6001010000"},
        requested_value="2000/01/01 12:00",
    )
    assert ok is True
    assert prepared == DATE_TIME_UNSET_RAW
    assert err is None


@pytest.mark.asyncio
async def test_prepare_date_time_within_bounds() -> None:
    """In-range wire passes after encode."""
    ok, prepared, err = await _prepare_symbol_write_value(
        resolver=_resolver(),
        desc={"unit_code": "DATE_TIME", "min": "2001010000", "max": "6001010000"},
        requested_value="2025/03/11 14:30",
    )
    assert ok is True
    assert prepared == "2503111430"
    assert err is None
