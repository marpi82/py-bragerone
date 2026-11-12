"""Branch/line coverage for merged pure ``catalog`` parser helpers."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models import catalog as catalog_mod
from pybragerone.models.catalog import (
    LiveAssetsCatalog,
    _eval_factory_body,
    _find_inline_param_object_spans,
    _largest_object_literal,
    _parse_destructure_params,
    _Parser,
    collapse_public_token,
    collect_bindings,
    find_language_config_object,
    is_translations_array_value,
    iter_top_level_object_assignments,
    parse_i18n_module,
    parse_js_declaration,
)


def test_collapse_public_token_branches() -> None:
    """Non-strings pass through; member/subscript tokens collapse."""
    assert collapse_public_token(7) == 7
    assert collapse_public_token("_0x['PUBLIC_TOKEN']") == "PUBLIC_TOKEN"
    assert collapse_public_token("plain['SUB']") == "SUB"


def test_parse_destructure_empty_segment_and_invalid_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip empty destructuring entries; bad defaults stay as source text."""
    specs = _parse_destructure_params("{a: x = !!!, , b: y}")
    assert ("a", "x", "!!!") in specs
    assert ("b", "y", None) in specs
    real_parse = catalog_mod._Parser.parse_value

    def boom_default(self: _Parser) -> Any:
        if "BOOM" in self.source:
            msg = "default fail"
            raise ValueError(msg)
        return real_parse(self)

    monkeypatch.setattr(catalog_mod._Parser, "parse_value", boom_default)
    specs_raise = _parse_destructure_params("(c: z = BOOM)")
    assert ("c", "z", "BOOM") in specs_raise


def test_eval_factory_body_binding_failure_and_no_return(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory bodies log binding failures and return None without ``return``."""
    real_parse = catalog_mod._Parser.parse_value

    def boom_bind(self: _Parser) -> Any:
        if "BOOM" in self.source:
            msg = "bind fail"
            raise ValueError(msg)
        return real_parse(self)

    monkeypatch.setattr(catalog_mod._Parser, "parse_value", boom_bind)
    body = "{ const broken = BOOM; return {ok: 1}; }"
    assert _eval_factory_body(body, {}) == {"ok": 1}
    body_no_ret = "{ const x = {a: 1}; }"
    assert _eval_factory_body(body_no_ret, {}) is None


def test_parser_comment_keyword_ternary_unary_edges() -> None:
    """Block comments, keyword boundaries, broken ternaries, numeric unary."""
    assert _Parser("// line\n3").parse_value() == 3
    assert _Parser("/*c*/ + 3").parse_value() == 3
    assert _Parser("trueish").parse_value() == "trueish"
    assert _Parser("1 ? 2").parse_value() == 1
    assert _Parser("-5").parse_value() == -5
    assert _Parser("+4").parse_value() == 4
    assert _Parser("+'txt'").parse_value() == "+txt"


def test_parser_callable_raises_and_primary_edge_cases() -> None:
    """Callable invoke failures, grouped objects, and empty primaries."""

    def boom(_: Any) -> Any:
        msg = "factory failed"
        raise RuntimeError(msg)

    leftover = _Parser("boom(1)", bindings={"boom": boom}).parse_value()
    assert isinstance(leftover, str) and leftover.startswith("<call:")

    empty = _Parser("")
    assert empty._parse_primary() is None
    assert _Parser("({a:1})").parse_value() == {"a": 1}
    assert _Parser("({a:1}").parse_value() == {"a": 1}

    bare = _Parser("notobj")
    assert bare._parse_object() == {}


def test_parser_recursion_error_degrades(monkeypatch: pytest.MonkeyPatch) -> None:
    """RecursionError during conditional parse degrades to None."""

    def boom(_self: _Parser) -> Any:
        raise RecursionError

    monkeypatch.setattr(catalog_mod._Parser, "_parse_conditional", boom)
    assert _Parser("1").parse_value() is None


def test_parser_array_number_edges() -> None:
    """Sparse arrays, unclosed strings, exponent and BigInt numeric literals."""
    assert _Parser("[,1]").parse_value() == [1]
    assert _Parser('"open')._read_string().startswith('"')
    assert _Parser("1e+2").parse_value() == 100.0
    assert _Parser("99n").parse_value() == 99

    parser = _Parser("x")
    parser.i = 1
    parser._skip_balanced("{", "}")
    assert parser.i == 1
    assert _Parser("notarr")._parse_array() == []
    obj_key = _Parser("{0x10:1}")
    assert obj_key._parse_object() == {"16": 1}
    assert _Parser("0x1a:1")._parse_object_key() == "26"
    assert _Parser(".5:1")._parse_object_key() == "0.5"


def test_parse_object_key_hex_when_first_peek_is_not_digit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hex literal keys still parse when ``_peek`` is not a decimal digit (edge guard)."""
    parser = _Parser("0x2:1")

    def fake_peek(self: _Parser) -> str:
        if self.i == 0:
            return "x"
        return catalog_mod._Parser._peek(self)

    monkeypatch.setattr(catalog_mod._Parser, "_peek", fake_peek)
    assert parser._parse_object_key() == "2"


def test_parser_computed_key_parse_failure_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Computed object keys fall back when the inner expression cannot parse."""
    real_parse = catalog_mod._Parser.parse_value

    def flaky_key_parse(self: _Parser) -> Any:
        if self.source == "failkey":
            msg = "key fail"
            raise ValueError(msg)
        return real_parse(self)

    monkeypatch.setattr(catalog_mod._Parser, "parse_value", flaky_key_parse)
    assert _Parser("{[failkey]:1}")._parse_object() == {"failkey": 1}


def test_collect_bindings_and_largest_object_ignore_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Broken bindings and object scans are skipped without aborting."""
    real_parse = catalog_mod._Parser.parse_value

    def boom_parse(self: _Parser) -> Any:
        if self.source.strip() == "RAISE":
            msg = "bind fail"
            raise ValueError(msg)
        return real_parse(self)

    monkeypatch.setattr(catalog_mod._Parser, "parse_value", boom_parse)
    bindings = collect_bindings("const x = RAISE; const y = 2;")
    assert bindings.get("y") == 2

    real_object = catalog_mod._Parser._parse_object

    def boom_object(self: _Parser) -> dict[str, Any]:
        if self.source.lstrip().startswith("{bad"):
            msg = "obj fail"
            raise ValueError(msg)
        return real_object(self)

    monkeypatch.setattr(catalog_mod._Parser, "_parse_object", boom_object)
    assert _largest_object_literal("{good: {a:1}} {bad:", {}) == {"good": {"a": 1}}


def test_i18n_non_object_and_collect_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-object default exports and outer i18n failures return empty dicts."""
    assert parse_i18n_module(b"export default 42") == {}
    assert parse_i18n_module(b"export default {{'}':1}") == {}
    assert not is_translations_array_value([1, 2])
    monkeypatch.setattr(catalog_mod, "collect_bindings", lambda _s: (_ for _ in ()).throw(RuntimeError("no i18n")))
    assert parse_i18n_module(b"export default {}") == {}


def test_iter_top_level_and_language_bruteforce_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assignment and DFS object scans skip values that fail to parse."""
    real_parse = catalog_mod._Parser.parse_value

    def boom_assign(self: _Parser) -> Any:
        if self.source.lstrip().startswith("{a"):
            msg = "assign fail"
            raise ValueError(msg)
        return real_parse(self)

    monkeypatch.setattr(catalog_mod._Parser, "parse_value", boom_assign)
    assert iter_top_level_object_assignments(b"name={a:1}") == []

    monkeypatch.setattr(catalog_mod, "collect_bindings", lambda _s: {})
    monkeypatch.setattr(catalog_mod, "iter_top_level_object_assignments", lambda _c: [])

    real_object = catalog_mod._Parser._parse_object

    def boom_brute(self: _Parser) -> dict[str, Any]:
        if "translations" in self.source:
            msg = "brute fail"
            raise ValueError(msg)
        return real_object(self)

    monkeypatch.setattr(catalog_mod._Parser, "_parse_object", boom_brute)
    assert find_language_config_object(b"zzz={translations:[{id:'en',flag:'gb'}],defaultTranslation:'en'};") is None


def test_find_language_config_nested_and_bruteforce() -> None:
    """DFS handles shared nested dicts, lists, and bare object literals."""
    shared = b"const child={translations:[{id:'en',flag:'gb'}],defaultTranslation:'en'};const wrap={a:child,b:child};"
    assert find_language_config_object(shared) is not None
    listed = b"const x={items:[{translations:[{id:'en',flag:'gb'}],defaultTranslation:'en'}]};"
    assert find_language_config_object(listed) is not None
    bare = b"noise {translations:[{id:'en',flag:'gb'}],defaultTranslation:'en'} tail"
    assert find_language_config_object(bare) is not None


def test_find_language_config_skips_revisited_nodes() -> None:
    """DFS does not recurse into the same dict object twice."""
    code = b"const same={junk:1}; const holder={refs:[same,same]};"
    assert find_language_config_object(code) is None


def test_parse_js_declaration_requires_const() -> None:
    """Test helper rejects non-const declarations."""
    with pytest.raises(ValueError, match="expected const"):
        parse_js_declaration(b"let x = 1;")


def test_inline_spans_unclosed_and_index_scan_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unclosed braces advance; index build catches span-scan failures."""
    assert _find_inline_param_object_spans(b"{" + b"x" * 50) == []
    monkeypatch.setattr(
        catalog_mod,
        "_find_inline_param_object_spans",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("span boom")),
    )
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    assets = catalog._build_asset_index_from_index_js("https://ex/index.js", b"//")
    assert assets.inline_param_candidates == []
