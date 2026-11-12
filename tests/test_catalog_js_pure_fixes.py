"""Coverage + regressions for pure JS parser parity fixes (#489 / #355)."""

from __future__ import annotations

from typing import Any

import pytest

from pybragerone.models.catalog_js_pure import (
    _array_map_method,
    _Parser,
    _public_token_from_helper_args,
    extract_root_export,
    extract_root_object,
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
