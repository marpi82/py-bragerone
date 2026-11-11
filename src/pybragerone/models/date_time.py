"""SPA ``DATE_TIME`` unit codec (``yyMMddHHmm`` ↔ display / datetime).

BragerOne's web app stores vacation-style timestamps as a 10-digit string in
``serverDateFormat`` (``yyMMddHHmm``) and displays them via Luxon as
``yyyy/MM/dd HH:mm``. Custom unit code ``0x270f`` / ``9999`` / ``DATE_TIME``.

Wire and display values are **naive local wall-clock**. Callers (e.g. Home
Assistant) must convert aware datetimes to the controller's local wall time
before encode; aware inputs are rejected rather than silently dropping ``tzinfo``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final

# SPA ``serverDateFormat`` / ``defaultDateFormat``.
SERVER_DATE_TIME_FORMAT: Final = "%y%m%d%H%M"
DISPLAY_DATE_TIME_FORMAT: Final = "%Y/%m/%d %H:%M"

# ``CustomUnit.DATE_TIME = 0x270f``.
DATE_TIME_UNIT_CODE: Final = "9999"
DATE_TIME_UNIT_NAME: Final = "DATE_TIME"
DATE_TIME_UNIT_KEYS: Final = frozenset({DATE_TIME_UNIT_CODE, DATE_TIME_UNIT_NAME, "0x270f", "0X270F"})

# Common "unset" sentinel observed on controllers (2000-01-01 12:00).
DATE_TIME_UNSET_RAW: Final = "0001011200"


def normalize_date_time_unit_key(unit_code: Any) -> str | None:
    """Return a canonical DATE_TIME key when *unit_code* names that custom unit."""
    if unit_code is None:
        return None
    if isinstance(unit_code, bool):
        return None
    if isinstance(unit_code, int):
        return DATE_TIME_UNIT_CODE if unit_code == 0x270F else None
    if isinstance(unit_code, float):
        if unit_code.is_integer() and int(unit_code) == 0x270F:
            return DATE_TIME_UNIT_CODE
        return None
    text = str(unit_code).strip()
    if not text:
        return None
    if text in DATE_TIME_UNIT_KEYS or text.upper() == DATE_TIME_UNIT_NAME:
        return DATE_TIME_UNIT_CODE if text != DATE_TIME_UNIT_NAME else DATE_TIME_UNIT_NAME
    # Hex literals as strings (covers forms not already listed in DATE_TIME_UNIT_KEYS).
    lowered = text.lower()
    if lowered.startswith("0x"):
        try:
            if int(text, 0) == 0x270F:
                return DATE_TIME_UNIT_CODE
        except ValueError:
            return None
    return None


def unit_meta_looks_like_date_time(unit_meta: Any) -> bool:
    """Return True when a units-table entry is the SPA DATE_TIME ``parse`` codec."""
    if not isinstance(unit_meta, Mapping):
        return False
    parse_expr = unit_meta.get("parse")
    if parse_expr is None:
        return False
    if callable(parse_expr):
        # Tree-sitter may materialize the arrow as a callable; presence of ``parse``
        # alone is not enough — require no competing measurement keys.
        return unit_meta.get("text") is None and unit_meta.get("options") is None
    if not isinstance(parse_expr, str):
        return False
    lowered = parse_expr.lower()
    return "fromformat" in lowered or "serverdateformat" in lowered or "yymmddhhmm" in lowered


def is_date_time_unit(*, unit_code: Any = None, unit_meta: Any = None) -> bool:
    """Return True when unit code and/or descriptor meta identify DATE_TIME."""
    if normalize_date_time_unit_key(unit_code) is not None:
        return True
    return unit_meta_looks_like_date_time(unit_meta)


def _digits_wire_text(raw: int | float) -> str | None:
    """Normalize a JSON number into a 10-digit ``yyMMddHHmm`` string, or ``None``."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, float):
        if not raw.is_integer():
            return None
        raw = int(raw)
    if raw < 0:
        return None
    text = str(raw)
    if not text.isdigit() or len(text) > 10:
        return None
    # JSON numbers drop leading zeros (year 00-09 / unset sentinel as int).
    return text.zfill(10)


def parse_server_date_time(raw: Any) -> datetime | None:
    """Parse a Brager wire value into a naive wall-clock ``datetime``.

    Returns:
        Parsed naive datetime, or ``None`` for missing / unset sentinel / invalid /
        timezone-aware input (callers must convert to local wall time first).
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, datetime):
        # Reject aware values — stripping tzinfo would shift the wall clock.
        if raw.tzinfo is not None:
            return None
        return raw
    if isinstance(raw, int | float):
        text = _digits_wire_text(raw)
        if text is None:
            return None
    else:
        text = str(raw).strip()
    if not text or text == DATE_TIME_UNSET_RAW:
        return None
    if text.isdigit():
        # ``yyMMddHHmm`` is always 10 digits (after int zero-pad above).
        if len(text) != 10:
            return None
        try:
            return datetime.strptime(text, SERVER_DATE_TIME_FORMAT)
        except ValueError:
            return None
    # SPA display form.
    try:
        return datetime.strptime(text, DISPLAY_DATE_TIME_FORMAT)
    except ValueError:
        return None


def format_server_date_time(value: Any) -> str | None:
    """Encode a naive datetime / display string to the Brager ``yyMMddHHmm`` wire string."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text == DATE_TIME_UNSET_RAW:
            return DATE_TIME_UNSET_RAW
        if text.isdigit() and len(text) == 10:
            # Already wire-shaped; validate by round-trip.
            return text if parse_server_date_time(text) is not None or text == DATE_TIME_UNSET_RAW else None
        parsed = parse_server_date_time(text)
        if parsed is None:
            return None
        return parsed.strftime(SERVER_DATE_TIME_FORMAT)
    if isinstance(value, int | float):
        # Preserve the unset sentinel when JSON delivered it as a number.
        digits = _digits_wire_text(value)
        if digits == DATE_TIME_UNSET_RAW:
            return DATE_TIME_UNSET_RAW
    parsed = parse_server_date_time(value)
    if parsed is None:
        return None
    return parsed.strftime(SERVER_DATE_TIME_FORMAT)


def format_display_date_time(value: Any) -> str | None:
    """Format a wire / datetime value as SPA ``yyyy/MM/dd HH:mm`` (or ``None`` if unset)."""
    parsed = parse_server_date_time(value)
    if parsed is None:
        return None
    return parsed.strftime(DISPLAY_DATE_TIME_FORMAT)
