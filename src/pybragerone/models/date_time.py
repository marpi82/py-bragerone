"""SPA ``DATE_TIME`` unit codec (``yyMMddHHmm`` ↔ display / datetime).

BragerOne's web app stores vacation-style timestamps as a 10-digit string in
``serverDateFormat`` (``yyMMddHHmm``) and displays them via Luxon as
``yyyy/MM/dd HH:mm``. Custom unit code ``0x270f`` / ``9999`` / ``DATE_TIME``.

Two-digit years follow Luxon's default ``twoDigitCutoffYear`` (60): ``00-60`` ->
``2000-2060``, ``61-99`` -> ``1961-1999``. Years outside that window cannot be
encoded losslessly and are rejected.

Wire and display values are **naive local wall-clock** at minute resolution.
Callers (e.g. Home Assistant) must convert aware datetimes to the controller's
local wall time before encode; aware inputs are rejected rather than silently
dropping ``tzinfo``. Seconds/microseconds are truncated on encode.

The controller factory default ``0001011200`` / ``2000-01-01 12:00`` is a normal
wall-clock value (not ``None``): Home Assistant has no datetime clear action, so
showing and writing that moment is how integrations represent “unset”. Encoding
that wall clock still yields the reserved wire form.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final

# SPA ``defaultDateFormat``.
DISPLAY_DATE_TIME_FORMAT: Final = "%Y/%m/%d %H:%M"

# Luxon ``Settings.twoDigitCutoffYear`` default — keep SPA display parity.
LUXON_TWO_DIGIT_CUTOFF_YEAR: Final = 60

# ``CustomUnit.DATE_TIME = 0x270f``.
DATE_TIME_UNIT_CODE: Final = "9999"
DATE_TIME_UNIT_NAME: Final = "DATE_TIME"
DATE_TIME_UNIT_KEYS: Final = frozenset({DATE_TIME_UNIT_CODE, DATE_TIME_UNIT_NAME, "0x270f", "0X270F"})

# Controller factory-default / clear wire form (still a real wall-clock on read).
DATE_TIME_UNSET_RAW: Final = "0001011200"
DATE_TIME_UNSET_DT: Final = datetime(2000, 1, 1, 12, 0)


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


def _year_from_yy(yy: int) -> int:
    """Map a two-digit year with Luxon's default cutoff (not Python ``%y``)."""
    if yy <= LUXON_TWO_DIGIT_CUTOFF_YEAR:
        return 2000 + yy
    return 1900 + yy


def _yy_from_year(year: int) -> int | None:
    """Return ``yy`` for *year* when it is uniquely representable under Luxon rules."""
    if 2000 <= year <= 2000 + LUXON_TWO_DIGIT_CUTOFF_YEAR:
        return year - 2000
    if 1900 + LUXON_TWO_DIGIT_CUTOFF_YEAR + 1 <= year <= 1999:
        return year - 1900
    return None


def _digits_wire_text(raw: int | float | str) -> str | None:
    """Normalize a JSON number or digit string into 10-digit ``yyMMddHHmm``, or ``None``."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, float):
        if not raw.is_integer():
            return None
        raw = int(raw)
    if isinstance(raw, int):
        if raw < 0:
            return None
        text = str(raw)
    else:
        text = raw.strip()
    if not text.isdigit() or not (1 <= len(text) <= 10):
        return None
    # JSON numbers / short strings drop leading zeros (year 00-09 / unset sentinel).
    return text.zfill(10)


def _parse_wire_digits(text: str) -> datetime | None:
    """Parse a 10-digit Luxon-compatible ``yyMMddHHmm`` string."""
    if len(text) != 10 or not text.isdigit():
        return None
    try:
        yy = int(text[0:2])
        month = int(text[2:4])
        day = int(text[4:6])
        hour = int(text[6:8])
        minute = int(text[8:10])
        return datetime(_year_from_yy(yy), month, day, hour, minute)
    except ValueError:
        return None


def _format_wire(dt: datetime) -> str | None:
    """Format a naive datetime as ``yyMMddHHmm`` with Luxon year mapping."""
    yy = _yy_from_year(dt.year)
    if yy is None:
        return None
    return f"{yy:02d}{dt.month:02d}{dt.day:02d}{dt.hour:02d}{dt.minute:02d}"


def _as_naive_minute(dt: datetime) -> datetime | None:
    """Return minute-resolution naive datetime, or ``None`` if timezone-aware."""
    if dt.tzinfo is not None:
        return None
    return dt.replace(second=0, microsecond=0)


def parse_server_date_time(raw: Any) -> datetime | None:
    """Parse a Brager wire value into a naive wall-clock ``datetime``.

    Returns:
        Parsed naive datetime (including factory-default ``2000-01-01 12:00``), or
        ``None`` for missing / invalid / timezone-aware input (callers must convert
        to local wall time first).
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, datetime):
        return _as_naive_minute(raw)
    if isinstance(raw, int | float):
        text = _digits_wire_text(raw)
        if text is None:
            return None
    else:
        text = str(raw).strip()
        if text.isdigit():
            text_norm = _digits_wire_text(text)
            if text_norm is None:
                return None
            text = text_norm
    if not text:
        return None
    if text.isdigit():
        parsed = _parse_wire_digits(text)
        if parsed is None:
            return None
        return _as_naive_minute(parsed)
    # SPA display form.
    try:
        parsed = datetime.strptime(text, DISPLAY_DATE_TIME_FORMAT)
    except ValueError:
        return None
    return _as_naive_minute(parsed)


def format_server_date_time(value: Any) -> str | None:
    """Encode a naive datetime / display string to the Brager ``yyMMddHHmm`` wire string."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            digits = _digits_wire_text(text)
            if digits is None:
                return None
            # Already wire-shaped (after pad); validate by round-trip
            # (includes factory-default ``0001011200`` → same wire).
            return digits if parse_server_date_time(digits) is not None else None
        # SPA display form (``2000/01/01 12:00`` encodes to ``0001011200``).
        try:
            as_display = datetime.strptime(text, DISPLAY_DATE_TIME_FORMAT).replace(second=0, microsecond=0)
        except ValueError:
            return None
        return _format_wire(as_display)
    if isinstance(value, int | float):
        digits = _digits_wire_text(value)
        if digits is None:
            return None
        return digits if parse_server_date_time(digits) is not None else None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return None
        truncated = value.replace(second=0, microsecond=0)
        return _format_wire(truncated)
    return None


def format_display_date_time(value: Any) -> str | None:
    """Format a wire / datetime value as SPA ``yyyy/MM/dd HH:mm`` (or ``None`` if invalid)."""
    parsed = parse_server_date_time(value)
    if parsed is None:
        return None
    return parsed.strftime(DISPLAY_DATE_TIME_FORMAT)
