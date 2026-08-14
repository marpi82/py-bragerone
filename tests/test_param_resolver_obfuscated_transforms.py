"""Tests for numeric transforms written in obfuscated JavaScript."""

from __future__ import annotations

import pytest

from pybragerone.models.param_resolver import ParamResolver


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("x['toFixed'](0x1)", "x.toFixed(1)"),
        ('x["toFixed"](0x1)', "x.toFixed(1)"),
        ("_0x5c18a7-0x7f", "_0x5c18a7-127"),
        ("_0x201288*0x6", "_0x201288*6"),
        ("e*0b1010", "e*10"),
        ("e*0o17", "e*15"),
        ("e * .1", "e * .1"),
    ],
)
def test_normalize_js_expression_rewrites_obfuscated_syntax(raw: str, expected: str) -> None:
    """Bracket member access and radix literals collapse to their readable equivalents."""
    assert ParamResolver._normalize_js_expression(raw) == expected


def test_normalize_js_expression_preserves_mangled_identifiers() -> None:
    """`_0x4fdb4d` is an identifier, not a hex literal; the lookbehind must protect it."""
    assert ParamResolver._normalize_js_expression("_0x4fdb4d") == "_0x4fdb4d"
    assert ParamResolver._normalize_js_expression("_0x4fdb4d*0x2") == "_0x4fdb4d*2"


@pytest.mark.parametrize(
    ("expr", "raw_value", "expected"),
    [
        # The obfuscated and readable spellings of the same kW transform must agree.
        ("_0x4fdb4d=>Number(_0x4fdb4d*0.1)['toFixed'](0x1)", 53, 5.3),
        ("e => Number((e * .1).toFixed(1))", 53, 5.3),
        ("_0x201288=>_0x201288*0x6", 7, 42),
        ("_0x23f809=>_0x23f809/0x6", 12, 2),
        ("_0x5c18a7=>(_0x5c18a7-0x7f)*0.5", 255, 64),
        ("_0xac50fa=>_0xac50fa-0x7f", 255, 128),
        ("e => e - 127", 255, 128),
    ],
)
def test_apply_numeric_transform_handles_obfuscated_expressions(expr: str, raw_value: int, expected: float) -> None:
    """Values must be scaled identically whichever build shape the expression came from."""
    assert ParamResolver._apply_numeric_transform(raw_value, expr) == expected


def test_obfuscated_and_readable_transforms_parse_identically() -> None:
    """Equivalent expressions must produce the same transform, not merely similar output."""
    obfuscated = ParamResolver._parse_numeric_transform("_0x4fdb4d=>Number(_0x4fdb4d*0.1)['toFixed'](0x1)")
    readable = ParamResolver._parse_numeric_transform("e => Number((e * .1).toFixed(1))")

    assert obfuscated is not None
    assert obfuscated == readable


def test_parse_numeric_transform_still_rejects_unsupported_bodies() -> None:
    """Statement bodies that are not the unit-66 formatter stay out of the numeric parser."""
    assert ParamResolver._parse_numeric_transform("_0x1=>{return _0x1*2;}") is None
    assert ParamResolver._parse_numeric_transform("not an arrow function") is None
    assert ParamResolver._parse_numeric_transform(None) is None


_LIVE_UNIT66 = (
    "_0x528242=>{if(_0x528242===0x0)return'units.202.0';"
    "const _0x3355bc=(_0x528242-0x1)*0xa,"
    "_0x39bbda=Math['floor'](_0x3355bc/0x3c),"
    "_0x3a625e=_0x3355bc%0x3c;"
    "return _0x39bbda['toString']()['padStart'](0x2,'0')+':'"
    "+_0x3a625e['toString']()['padStart'](0x2,'0');}"
)


def test_unit66_time_transform_matches_obfuscated_and_readable_spellings() -> None:
    """Unit 66 must format HH:MM for both the readable special-case and the live bundle."""
    readable = 'e => { if(e===0)return"units.202.0"; return String((e-1)*10).padStart(2,"0"); }'
    apply = ParamResolver._apply_numeric_transform
    assert apply(0, _LIVE_UNIT66) == apply(0, readable) == "units.202.0"
    assert apply(7, _LIVE_UNIT66) == apply(7, readable) == "01:00"
    assert ParamResolver._parse_numeric_transform(_LIVE_UNIT66) is None


def test_shift_only_obfuscated_and_readable_parse_identically() -> None:
    """Unit 47 is ``x - 127``; hex ``0x7f`` must ToString to the same shift."""
    obfuscated = ParamResolver._parse_numeric_transform("_0xac50fa=>_0xac50fa-0x7f")
    readable = ParamResolver._parse_numeric_transform("e => e - 127")
    assert obfuscated is not None
    assert obfuscated == readable
    assert obfuscated.shift == -127.0
    assert obfuscated.factor == 1.0
