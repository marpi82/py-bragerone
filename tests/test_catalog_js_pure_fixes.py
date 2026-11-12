"""Coverage + regressions for pure JS parser parity fixes (#489 / #355)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from pybragerone.models.catalog import LiveAssetsCatalog
from pybragerone.models.catalog_js_pure import (
    _array_map_method,
    _Parser,
    _public_token_from_helper_args,
    extract_root_export,
    extract_root_object,
    make_object_factory,
    string_value,
)


def test_string_value_template_interpolates_and_keeps_unknown() -> None:
    """Backtick bodies substitute known idents and leave unknown ``${…}`` intact."""
    assert string_value("`parameters.STATUS_P5_${n}`", bindings={"n": 10}) == "parameters.STATUS_P5_10"
    assert string_value("`x_${missing}`", bindings={"n": 1}) == "x_${missing}"
    assert string_value("plain") == "plain"
    assert string_value("") == ""


def test_public_token_from_helper_args_shapes() -> None:
    """Obfuscated helper collapse covers 1-arg / 2-arg success and reject paths."""
    assert _public_token_from_helper_args("_0xabc", ["PARAM_1"]) == "PARAM_1"
    assert _public_token_from_helper_args("_0xabc", ["WRITE", "PARAM_45"]) == "PARAM_45"
    assert _public_token_from_helper_args("readable", ["PARAM_1"]) is None
    assert _public_token_from_helper_args("_0xabc", ["not-a-token"]) is None
    assert _public_token_from_helper_args("_0xabc", []) is None
    assert _public_token_from_helper_args("_0xabc", ["NOPE", "PARAM_1"]) is None
    assert _public_token_from_helper_args("_0xabc", ["WRITE", 12]) is None


def test_array_map_method_success_failure_and_non_callable() -> None:
    """``array['map']`` keeps receiver tokens when the callback is unusable."""
    mapped = _array_map_method(["PARAM_1", "PARAM_2"])

    assert mapped(lambda item: {"parameter": item}) == [
        {"parameter": "PARAM_1"},
        {"parameter": "PARAM_2"},
    ]

    def _boom(_item: Any) -> Any:
        raise RuntimeError("nope")

    assert mapped(_boom) == ["PARAM_1", "PARAM_2"]
    assert mapped("not-callable") == ["PARAM_1", "PARAM_2"]
    assert mapped(list) == ["PARAM_1", "PARAM_2"]


def test_skip_one_value_span_covers_shapes() -> None:
    """Depth-limit skip path advances past objects, strings, numbers, idents, and junk."""
    cases = [
        ('{"a":1}', 7),
        ("[1,2]", 5),
        ("(1)", 3),
        ('"hi"', 4),
        ("`x`", 3),
        ("-12", 3),
        ("0x10", 4),
        ("fooBar", 6),
        ("@", 1),
        ("!", 1),
    ]
    for source, _expected_min in cases:
        parser = _Parser(source)
        start = parser.i
        parser._skip_one_value_span()
        assert parser.i > start, source

    # Empty input: ``if ch:`` false branch (no advance).
    empty = _Parser("")
    empty._skip_one_value_span()
    assert empty.i == 0


def test_parse_value_depth_limit_degrades() -> None:
    """Explicit depth ceiling degrades without raising."""
    parser = _Parser("[1]")
    parser._depth = 10_000
    assert parser.parse_value() is None


def test_non_string_callee_call_does_not_collapse_helper() -> None:
    """Numeric callees take the non-string leftover branch (branch coverage)."""
    parser = _Parser("1('WRITE','PARAM_9')")
    assert parser.parse_value() == "('WRITE','PARAM_9')"


def test_extract_root_recursion_guards_are_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Outer RecursionError guards stay defensive even when depth limit is bypassed."""

    def _boom(_code: bytes) -> Any:
        raise RecursionError

    monkeypatch.setattr("pybragerone.models.catalog_js_pure.collect_bindings", _boom)
    assert extract_root_export(b"export default {}") is None

    def _boom_export(_code: bytes) -> Any:
        raise RecursionError

    monkeypatch.setattr("pybragerone.models.catalog_js_pure.extract_root_export", _boom_export)
    assert extract_root_object(b"export default {}") is None


def test_pure_optional_chain_or_fallback_fills_minmax_paths() -> None:
    """Production pure path: ``_0x?.['minValue']||[{…}]`` must become paths.min/max (#329)."""
    code = b"""
    export default {
      PARAM_TEST: {
        value: [{group: 'P6', number: 1, use: 'v'}],
        minValue: _0x39dd22?.['minValue']||[{group: 'P6', number: 42, use: 'n'}],
        maxValue: _0x39dd22?.['maxValue']||[{group: 'P6', number: 42, use: 'x'}],
      }
    };
    """
    root = extract_root_export(code)
    assert isinstance(root, dict)
    param_obj = root["PARAM_TEST"]
    assert isinstance(param_obj, dict)
    assert param_obj["minValue"] == [{"group": "P6", "number": 42, "use": "n"}]
    assert param_obj["maxValue"] == [{"group": "P6", "number": 42, "use": "x"}]

    catalog = LiveAssetsCatalog(AsyncMock())
    built = catalog._build_param_map_from_obj(param_obj, "PARAM_TEST", "test")
    assert built is not None
    assert built.paths["min"] == [{"group": "P6", "number": 42, "use": "n"}]
    assert built.paths["max"] == [{"group": "P6", "number": 42, "use": "x"}]


def test_pure_optional_chain_nullish_and_missing_key() -> None:
    """``obj?.['missing']`` / unbound ``_0x?.['key']`` are undefined on the pure path."""
    assert _Parser("_0x39dd22?.['minValue']").parse_value() is None
    assert _Parser("obj?.['MISSING']", bindings={"obj": {"OTHER": 1}}).parse_value() is None
    assert _Parser("obj?.['present']", bindings={"obj": {"present": 7}}).parse_value() == 7
    assert _Parser("obj?.present", bindings={"obj": {"present": 7}}).parse_value() == 7
    assert _Parser("obj?.missing", bindings={"obj": {"present": 7}}).parse_value() is None
    assert _Parser("_0xabc?.foo").parse_value() is None
    assert _Parser("plainIdent?.foo").parse_value() is None
    assert _Parser("1?.foo").parse_value() is None
    assert _Parser("obj?.").parse_value() is None
    assert _Parser("1?.['x']").parse_value() is None
    assert _Parser("plainIdent?.['x']").parse_value() is None


def test_typeof_and_bitwise_ops_consume_spa_arrows() -> None:
    """``typeof`` / ``>>`` / ``&`` keep factory call args intact (#495)."""
    assert _Parser("typeof 1").parse_value() == "number"
    assert _Parser("typeof true").parse_value() == "boolean"
    assert _Parser("typeof null").parse_value() == "undefined"
    assert _Parser("typeof 'x'").parse_value() == "string"
    assert _Parser("typeof []").parse_value() == "object"
    assert _Parser("typeof {}").parse_value() == "object"
    assert _Parser("typeof undefined").parse_value() == "undefined"
    assert _Parser("typeof _0xabc").parse_value() == "undefined"
    assert _Parser("typeof fn", bindings={"fn": lambda: None}).parse_value() == "function"
    assert _Parser("typeof T", bindings={"T": int}).parse_value() == "function"
    # Non-callable objects fall through to undefined (SPA only needs cursor advance).
    assert _Parser("typeof x", bindings={"x": object()}).parse_value() == "undefined"
    assert _Parser("5>>1").parse_value() == 2
    assert _Parser("5<<1").parse_value() == 10
    assert _Parser("5&1").parse_value() == 1
    assert _Parser("5|2").parse_value() == 7
    assert _Parser("5^1").parse_value() == 4
    assert _Parser("8>>>1").parse_value() == 4
    assert _Parser("2*3").parse_value() == 6
    assert _Parser("8/2").parse_value() == 4.0
    assert _Parser("7%4").parse_value() == 3
    # Non-int operands keep source-like leftovers (still advance the cursor).
    assert _Parser("'a'>>1").parse_value() == "a>>1"
    assert _Parser("'a'<<1").parse_value() == "a<<1"
    assert _Parser("'a'>>>1").parse_value() == "a>>>1"
    assert _Parser("'a'&1").parse_value() == "a&1"
    assert _Parser("'a'|1").parse_value() == "a|1"
    assert _Parser("'a'^1").parse_value() == "a^1"
    # Logical ops must not be eaten by bitwise parsers.
    assert _Parser("0||7").parse_value() == 7
    assert _Parser("0&&7").parse_value() == 0
    # JavaScript equality binds tighter than bitwise; bool equality coerces like ToInt32.
    assert _Parser("1===1&0").parse_value() == 0
    assert _Parser("1===0|1").parse_value() == 1
    assert _Parser("1===1^0").parse_value() == 1
    assert _Parser("true<<1").parse_value() == 2
    assert _Parser("2.0>>1").parse_value() == 1
    assert _Parser("1.5&1").parse_value() == "1.5&1"


def test_factory_call_valuecallback_typeof_does_not_clobber_number() -> None:
    """Live index shape: ``valueCallback`` typeof/ternary/bit-filter must not rewrite ``number`` (#495)."""
    params = "{id:_0x408650,number:_0x9ae4b2,name:_0x29396b,valueCallback:valueCallback=void 0x0}"
    body = (
        "{const o={'id':_0x408650,'name':_0x29396b,"
        "'value':[{'group':'P100','number':_0x9ae4b2,'use':'v'}],"
        "'valueCallback':valueCallback};return o;}"
    )
    factory = make_object_factory(params, body, {})
    call = (
        "basicParameterBuilder_P100({'id':0x126d571b0af6,'number':0x1,"
        "'name':'parameters.INFOSCREEN_KOTLY_W_UZYCIU',"
        "'valueCallback':_0x499c0b=>typeof _0x499c0b==='number'"
        "?[0x0,0x1,0x2,0x3]['filter'](_0x3d459d=>_0x499c0b>>_0x3d459d&0x1)['length']"
        ":_0x499c0b})"
    )
    out = _Parser(call, bindings={"basicParameterBuilder_P100": factory}).parse_value()
    assert isinstance(out, dict)
    assert out["value"] == [{"group": "P100", "number": 1, "use": "v"}]
    assert set(out) >= {"id", "name", "value"}
    # Argument object must not grow operator-character junk keys from a truncated arrow.
    assert "&" not in out
    assert ">" not in out
