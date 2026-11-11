"""SPA ``DATE_TIME`` unit codec (``yyMMddHHmm`` ↔ display / datetime).

BragerOne's web app stores vacation-style timestamps as a 10-digit string in
``serverDateFormat`` (``yyMMddHHmm``) and displays them via Luxon as
``yyyy/MM/dd HH:mm``. Custom unit code ``0x270f`` / ``9999`` / ``DATE_TIME``.
"""

from __future__ import annotations

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
    # Hex literals as strings.
    lowered = text.lower()
    if lowered.startswith("0x"):
        try:
            if int(text, 0) == 0x270F:
                return DATE_TIME_UNIT_CODE
        except ValueError:
            return None
    if text.isdigit() and text == DATE_TIME_UNIT_CODE:
        return DATE_TIME_UNIT_CODE
    return None


def unit_meta_looks_like_date_time(unit_meta: Any) -> bool:
    """Return True when a units-table entry is the SPA DATE_TIME ``parse`` codec."""
    if not isinstance(unit_meta, dict):
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


def parse_server_date_time(raw: Any) -> datetime | None:
    """Parse a Brager wire value into a naive ``datetime``.

    Returns:
        Parsed datetime, or ``None`` for missing / unset sentinel / invalid input.
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo is not None else raw
    text = str(raw).strip()
    if not text or text == DATE_TIME_UNSET_RAW:
        return None
    # Digits-only wire form (allow int-like floats that stringify with .0).
    if isinstance(raw, float) and raw.is_integer():
        text = str(int(raw))
    elif isinstance(raw, int):
        text = str(raw)
    if text.isdigit():
        # ``yyMMddHHmm`` is always 10 digits.
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
    """Encode a datetime / display string to the Brager ``yyMMddHHmm`` wire string."""
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
