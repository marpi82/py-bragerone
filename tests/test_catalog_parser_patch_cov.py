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
    _scan_top_level_declarations,
    _split_top_level_declarators,
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
    """RecursionError during value parse degrades to None."""

    def boom(_self: _Parser) -> Any:
        raise RecursionError

    # Hot path enters via ``_parse_unary``; binary/ternary still uses ``_parse_conditional``.
    monkeypatch.setattr(catalog_mod._Parser, "_parse_unary", boom)
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


def test_object_shorthand_and_number_exponent_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shorthand without binding, non-str shorthand key, and ``1e2`` without sign."""
    assert _Parser("{foo}")._parse_object() == {"foo": "foo"}
    assert _Parser("1e2").parse_value() == 100.0
    assert _Parser("1e-1").parse_value() == 0.1

    real_key = catalog_mod._Parser._parse_object_key

    def non_str_key(self: _Parser) -> Any:
        self._skip_ws_and_comments()
        if self._peek() == "7":
            self._advance()
            return 7
        return real_key(self)

    monkeypatch.setattr(catalog_mod._Parser, "_parse_object_key", non_str_key)
    assert _Parser("{7}")._parse_object() == {}


def test_scan_and_split_edge_branches() -> None:
    """Unclosed quote at EOF skips the string loop; trailing comma yields empty tail."""
    assert _scan_top_level_declarations('"') == []
    assert _split_top_level_declarators("a=1,") == ["a=1"]
    assert collect_bindings("const a=1, b=2,;") == {"a": 1, "b": 2}


def test_i18n_null_default_and_non_dict_assignment(monkeypatch: pytest.MonkeyPatch) -> None:
    """``export default null`` skips the non-object warning; non-dict ``={…}`` scans are ignored."""
    assert parse_i18n_module(b"export default null") == {}

    real_parse = catalog_mod._Parser.parse_value

    def non_dict_assign(self: _Parser) -> Any:
        if self.source.lstrip().startswith("{"):
            return 42
        return real_parse(self)

    monkeypatch.setattr(catalog_mod._Parser, "parse_value", non_dict_assign)
    assert iter_top_level_object_assignments(b"name={a:1}") == []


def test_menu_export_none_and_index_token_map_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Menu export degrades when root export is None; index-token lookup covers hit/miss/errors."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    monkeypatch.setattr(catalog_mod, "extract_root_export", lambda _code: None)
    assert catalog._parse_menu_export(b"export default {priority:1}") == ([], 0)

    js = b"const maps={PARAM_OK:{group:'P1',number:1,use:'v'}};"
    built = catalog._parse_param_map_from_index_token(js, "PARAM_OK", "test")
    assert built is not None
    assert catalog._parse_param_map_from_index_token(js, "PARAM_MISSING", "test") is None

    real_maps = catalog_mod.LiveAssetsCatalog._parse_index_token_raw_maps
    monkeypatch.setattr(
        catalog_mod.LiveAssetsCatalog,
        "_parse_index_token_raw_maps",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("maps boom")),
    )
    assert catalog._parse_param_map_from_index_token(js, "PARAM_OK", "test") is None
    monkeypatch.setattr(catalog_mod.LiveAssetsCatalog, "_parse_index_token_raw_maps", real_maps)

    monkeypatch.setattr(
        catalog_mod,
        "_parse_index_token_raw_maps_ctx",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("token-map boom")),
    )
    assert catalog._parse_index_token_raw_maps(b"const x={PARAM_X:{group:'P1',number:1}};") == {}


def test_units_table_int_keys_and_named_alias_remap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-str descriptor keys normalize; named CustomUnit aliases remap non-digit keys."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    monkeypatch.setattr(
        catalog_mod,
        "iter_top_level_object_assignments",
        lambda _code: [
            {
                9: {"text": "units.9"},
                "BOILER_STATE": {"text": "units.9998"},
            }
        ],
    )
    monkeypatch.setattr(
        catalog_mod.LiveAssetsCatalog,
        "_parse_custom_unit_codes_from_index",
        lambda _self, _code: {"BOILER_STATE": "9998"},
    )
    table = catalog._parse_units_descriptor_table_from_index(b"// unused when patched")
    assert table["9"]["text"] == "units.9"
    assert table["9998"]["text"] == "units.9998"


def test_lazy_bindings_and_overlay_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover lazy TDZ, mutators, overlay misses, and factory plan edge paths."""
    lazy = catalog_mod._LazyBindings([("a", "1"), ("b", "a + 1")])
    assert "a" in lazy
    bad_key: object = 7
    assert bad_key not in lazy
    assert len(lazy) == 2
    assert set(lazy) == {"a", "b"}
    assert lazy["a"] == 1
    # Already-materialized re-entry via ``_materialize``.
    assert lazy._materialize("a") == 1
    lazy["c"] = 9
    assert lazy["c"] == 9
    del lazy["a"]
    with pytest.raises(KeyError):
        _ = lazy["a"]
    with pytest.raises(KeyError):
        _ = lazy["missing"]

    # Re-enter materialize while in progress (TDZ).
    lazy2 = catalog_mod._LazyBindings([("loop", "loop")])
    lazy2._cache["loop"] = catalog_mod._IN_PROGRESS
    with pytest.raises(KeyError):
        _ = lazy2["loop"]
    with pytest.raises(KeyError):
        lazy2._materialize("loop")

    # Failed binding parse stores None.
    real_parse = catalog_mod._Parser.parse_value

    def boom_parse(self: _Parser) -> Any:
        if "BOOM_BIND" in self.source:
            msg = "bind fail"
            raise ValueError(msg)
        return real_parse(self)

    monkeypatch.setattr(catalog_mod._Parser, "parse_value", boom_parse)
    lazy3 = catalog_mod._LazyBindings([("bad", "BOOM_BIND")])
    assert lazy3["bad"] is None

    overlay = catalog_mod._BindingsOverlay({"parent": 1})
    assert "parent" in overlay
    assert overlay["parent"] == 1
    with pytest.raises(KeyError):
        _ = overlay["missing"]

    # Expression factory body + return-by-name and return-by-expr paths.
    assert catalog_mod._body_builds_object_factory("{ const x = {a:1}; }") is True
    assert catalog_mod._body_builds_object_factory("{ notAFactory }") is False
    assert catalog_mod._body_builds_object_factory("x + 1") is False
    assert _eval_factory_body("({a:1})", {}) == {"a": 1}
    assert _eval_factory_body("{ const o = {a:1}; return o; }", {}) == {"a": 1}
    assert _eval_factory_body("{ const o = {a:1}; return {b: 2}; }", {}) == {"b": 2}
    assert _eval_factory_body("{ const o = {a:1}; }", {}) is None

    # Force factory-plan cache clear branch.
    catalog_mod._FACTORY_BODY_PLANS.clear()
    for i in range(520):
        catalog_mod._factory_body_plan(f"({{k{i}:1}})")
    assert len(catalog_mod._FACTORY_BODY_PLANS) <= 512


def test_module_context_and_token_map_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shared context, span helpers, and selective token-map paths."""
    code = b"{a:1}; const BasicParameters={'PARAM_1':{group:'P1',number:1}};"
    ctx = catalog_mod._ModuleParseContext.from_bytes(code)
    assert ctx.lazy is ctx.lazy  # cached property
    assert ctx.object_spans() is ctx.object_spans()
    spans = catalog_mod._iter_object_spans(ctx.source, limit=8)
    assert spans
    assert catalog_mod._tightest_object_span(ctx.object_spans(), ctx.source.find("{")) is not None
    assert catalog_mod._tightest_object_span(spans, len(ctx.source) + 10) is None

    # String / comment / escape / non-comment slash branches in object-span scan.
    assert catalog_mod._iter_object_spans(r"/* c */ {a:1} // x" + "\n" + r'{b:"\""}')
    assert catalog_mod._iter_object_spans("'{' {a:1}")
    assert catalog_mod._iter_object_spans('"{" {a:1}')
    assert catalog_mod._iter_object_spans("`{` {a:1}")
    assert catalog_mod._iter_object_spans("/* unterminated {a:1}") == []
    assert catalog_mod._iter_object_spans('"unterminated') == []  # while exits at EOF
    assert catalog_mod._iter_object_spans("{a:1/2}")  # `/` not starting a comment

    items = catalog_mod._token_map_binding_items("var IconsList={}, BasicParameters={PARAM_Z:{group:'P1'}};")
    assert any(name == "BasicParameters" for name, _ in items)
    assert catalog_mod._extract_binding_value_at("1,2", 0) == "1"
    assert catalog_mod._extract_binding_value_at(r'"\","', 0) == r'"\","'
    assert catalog_mod._extract_binding_value_at('"noend', 0) == '"noend'

    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    maps = catalog._parse_index_token_raw_maps(code)
    assert "PARAM_1" in maps
    # Cached token-map path.
    assert catalog._parse_index_token_raw_maps(code) == maps

    # Mapping (non-dict) ingest + non-token keys skipped.
    from collections.abc import Mapping as MappingABC

    class _Map(MappingABC[str, Any]):
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def __getitem__(self, key: str) -> Any:
            return self._data[key]

        def __iter__(self) -> Any:
            return iter(self._data)

        def __len__(self) -> int:
            return len(self._data)

    out: dict[str, dict[str, Any]] = {}
    catalog_mod._ingest_token_maps(out, {"skip": {"a": 1}, "PARAM_M": _Map({"group": "P1"})})
    assert out["PARAM_M"] == {"group": "P1"}

    # Context cache hit (same bytes object and equality path).
    ctx1 = catalog._module_context_for(code)
    ctx2 = catalog._module_context_for(code)
    assert ctx1 is ctx2
    code2 = bytes(bytearray(code))  # equal content, distinct object (no bytes interning)
    assert code2 == code and code2 is not code
    assert catalog._module_context_for(code2) is ctx1

    # Language needle + missing span falls through to assignment/brute paths.
    lang = b"const cfg={translations:[{id:'en',flag:'gb'}],defaultTranslation:'en'};"
    assert find_language_config_object(lang) is not None
    # Cached language object.
    ctx_lang = catalog_mod._ModuleParseContext.from_bytes(lang)
    assert catalog_mod._find_language_config_object_ctx(ctx_lang) is not None
    assert catalog_mod._find_language_config_object_ctx(ctx_lang) is not None

    monkeypatch.setattr(catalog_mod, "_tightest_object_span", lambda *_a, **_k: None)
    assert find_language_config_object(lang) is not None

    # Brute-force path when assignments are empty and needle spans miss.
    monkeypatch.setattr(catalog_mod, "_iter_top_level_object_assignments_ctx", lambda _ctx: [])
    bare = b"({translations:[{id:'en',flag:'gb'}],defaultTranslation:'en'})"
    assert find_language_config_object(bare) is not None


@pytest.mark.asyncio
async def test_token_map_binding_failure_and_root_extract_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Token-map narrow binding exceptions and extract_root_object failures are swallowed."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))

    real_get = catalog_mod._LazyBindings.__getitem__

    def boom_bp(self: catalog_mod._LazyBindings, key: str) -> Any:
        if key == "BasicParameters":
            msg = "token boom"
            raise RuntimeError(msg)
        return real_get(self, key)

    monkeypatch.setattr(catalog_mod._LazyBindings, "__getitem__", boom_bp)
    monkeypatch.setattr(catalog_mod, "_iter_top_level_object_assignments_ctx", lambda _ctx: [])
    monkeypatch.setattr(catalog_mod, "extract_root_object", lambda _c: (_ for _ in ()).throw(RuntimeError("root")))
    assert catalog._parse_index_token_raw_maps(b"const BasicParameters={PARAM_X:{group:'P1'}};") == {}

    monkeypatch.setattr(catalog_mod._LazyBindings, "__getitem__", real_get)
    # Fewer than 10 tokens → fallback tries extract_root_object and swallows.
    assert catalog._parse_index_token_raw_maps(b"export default {noTokens:1};") == {}

    # ``_full_root`` reuse of a token-shaped cached root.
    index_js = b"export default {PARAM_ROOT:{group:'P8',name:'x',value:[{group:'P8',number:1,use:'v'}]}};"
    catalog._idx.index_bytes = index_js
    catalog._idx.inline_param_candidates = []
    catalog._idx.assets_by_basename["dummy"] = [catalog_mod.AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]
    ctx = catalog._module_context_for(index_js)
    ctx._root_object = {"PARAM_ROOT": {"group": "P8", "name": "x", "value": [{"group": "P8", "number": 1, "use": "v"}]}}
    # Force index-token path (no dedicated asset for PARAM_ROOT).
    mapped = await catalog.get_param_mapping(["PARAM_ROOT"])
    assert "PARAM_ROOT" in mapped

    # ``_full_root`` extract failure → None, mapping still resolves via token maps when possible.
    catalog2 = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    catalog2._idx.index_bytes = index_js
    catalog2._idx.inline_param_candidates = []
    catalog2._idx.assets_by_basename["dummy"] = [catalog_mod.AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]
    monkeypatch.setattr(catalog_mod, "extract_root_object", lambda _c: (_ for _ in ()).throw(RuntimeError("root2")))
    mapped2 = await catalog2.get_param_mapping(["PARAM_ROOT"])
    assert "PARAM_ROOT" in mapped2 or mapped2 == {}


def test_units_selective_binding_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Units table prefers option-rich bindings then falls back to assignments."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    js = (
        b"const units={0x1:{text:'units.1',options:{a:1,b:2,c:3,d:4,e:5,f:6,g:7,h:8,i:9,j:10}},"
        b"0x2:{text:'units.2',options:{a:1}}};"
    )
    table = catalog._parse_units_descriptor_table_from_index(js)
    assert "1" in table

    real_lazy_get = catalog_mod._LazyBindings.__getitem__

    def boom_get(self: catalog_mod._LazyBindings, key: str) -> Any:
        if key == "boom":
            msg = "units boom"
            raise RuntimeError(msg)
        return real_lazy_get(self, key)

    monkeypatch.setattr(catalog_mod._LazyBindings, "__getitem__", boom_get)
    js_boom = b"const boom={" + b"options," * 15 + b"x:1};const units={0:{text:'units.0'," + b"options:{a:1}," * 12 + b"}};"
    table2 = catalog._parse_units_descriptor_table_from_index(js_boom)
    assert isinstance(table2, dict)


def test_units_decoy_option_rich_const_still_finds_paramish_table() -> None:
    """Option-rich decoy consts must not block bare ``name={…}`` units tables.

    Counterexample: ``const decoy={options,options,…}`` satisfies the selective
    filter while the real table is only ``unitsTable={0:{text:'units.0',options:{…}},…}``
    (no ``const``/``let``/``var``). Pre-fix returned ``{}``; SPA bootstrap needs the table.
    """
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    decoy = "options," * 15 + "x:1"
    unit_entries = ",".join(f"{i}:{{text:'units.{i}',options:{{a:1,b:2,c:3,d:4,e:5,f:6,g:7,h:8,i:9,j:10}}}}" for i in range(3))
    js = f"const decoy={{{decoy}}};unitsTable={{{unit_entries}}};".encode()
    table = catalog._parse_units_descriptor_table_from_index(js)
    assert table.get("0", {}).get("text") == "units.0"
    assert "1" in table and "2" in table


def test_assignment_scan_skips_and_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assignment filters skip huge non-PARAM objects and swallow binding failures."""
    huge = "x" * 120_000
    code = f"const big={{{huge}:1}}; const ok={{PARAM_1:{{group:'P1'}}}};".encode()
    objs = iter_top_level_object_assignments(code)
    assert any("PARAM_1" in obj for obj in objs)

    real_get = catalog_mod._LazyBindings.__getitem__

    def boom(self: catalog_mod._LazyBindings, key: str) -> Any:
        if key == "bad":
            msg = "assign boom"
            raise RuntimeError(msg)
        return real_get(self, key)

    monkeypatch.setattr(catalog_mod._LazyBindings, "__getitem__", boom)
    objs2 = iter_top_level_object_assignments(b"const bad={PARAM_Y:{group:'P1'}}; const ok={PARAM_Z:{group:'P2'}};")
    assert any("PARAM_Z" in obj for obj in objs2)

    # Paramish ``= {…}`` scan: successful non-dict parse must be skipped (False branch).
    real_parse = catalog_mod._Parser.parse_value

    def non_dict_parse(self: _Parser) -> Any:
        if "options" in self.source[self.i : self.i + 40]:
            return ["options"]
        return real_parse(self)

    monkeypatch.setattr(catalog_mod._Parser, "parse_value", non_dict_parse)
    assert iter_top_level_object_assignments(b"name={options:1}") == []


def test_parse_menu_export_depth_limit() -> None:
    """Deeply nested menu containers stop at depth 5 without routes."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    nested: dict[str, Any] = {"leaf": True}
    for _ in range(7):
        nested = {"wrap": nested}
    # No path/name keys within depth budget → empty routes.
    js = ("export default " + repr(nested).replace("True", "true") + ";").encode()
    routes, priority = catalog._parse_menu_export(js)
    assert routes == []
    assert priority == 0

    # Nested under ``deviceMenu`` then values walk.
    menu_js = b"export default {outer:{deviceMenu:[{path:'a',name:'A'}]}};"
    routes2, _ = catalog._parse_menu_export(menu_js)
    assert routes2 and routes2[0]["path"] == "a"

    # Named key present but empty → fall through to values walk / next key.
    empty_key = b"export default {routes:[], deviceMenu:[{path:'b',name:'B'}]};"
    routes3, _ = catalog._parse_menu_export(empty_key)
    assert routes3 and routes3[0]["path"] == "b"


def test_token_map_mapping_false_and_enough_tokens() -> None:
    """Non-Mapping BasicParameters is skipped; >=10 tokens skip assignment fallback."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    # Successful narrow lookup that is not a Mapping.
    ctx = catalog._module_context_for(b"const BasicParameters=42;")
    # Force narrow path by calling ctx helper with a stubbed narrow map.
    out = catalog_mod._parse_index_token_raw_maps_ctx(ctx)
    assert isinstance(out, dict)

    entries = ",".join(f"PARAM_{i}:{{group:'P1',number:{i}}}" for i in range(12))
    code = f"const BasicParameters={{{entries}}};".encode()
    maps = catalog._parse_index_token_raw_maps(code)
    assert len(maps) >= 10


def test_largest_object_literal_parse_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_largest_object_literal`` advances past braces that fail to parse."""
    real = catalog_mod._Parser._parse_object

    def boom(self: _Parser) -> Any:
        if self.source[self.i :].startswith("{bad"):
            msg = "object boom"
            raise ValueError(msg)
        return real(self)

    monkeypatch.setattr(catalog_mod._Parser, "_parse_object", boom)
    assert _largest_object_literal("{bad}; {ok:1}", {}) == {"ok": 1}


def test_units_non_dict_binding_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Units candidate bindings that materialize to non-dicts are skipped."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    real_get = catalog_mod._LazyBindings.__getitem__

    def non_dict(self: catalog_mod._LazyBindings, key: str) -> Any:
        if key == "unitsish":
            return [1, 2, 3]
        return real_get(self, key)

    monkeypatch.setattr(catalog_mod._LazyBindings, "__getitem__", non_dict)
    js = b"const unitsish={" + b"options," * 15 + b"x:1};"
    table = catalog._parse_units_descriptor_table_from_index(js)
    assert isinstance(table, dict)


@pytest.mark.asyncio
async def test_looks_like_param_map_paths_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Index fallback accepts ParamMaps that only expose channel paths."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))
    index_js = b"export default {PARAM_PATHS:{value:[{group:'P1',number:1,use:'v'}]}};"
    catalog._idx.index_bytes = index_js
    catalog._idx.inline_param_candidates = []
    catalog._idx.assets_by_basename["dummy"] = [catalog_mod.AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]

    # Build a ParamMap with paths but no group/units via the real builder when possible.
    raw = {"value": [{"group": "P1", "number": 1, "use": "v"}]}
    pm = catalog._build_param_map_from_obj(raw, "PARAM_PATHS", origin="test")
    assert pm is not None
    # Clear group/units so ``_looks_like_param_map`` must accept via paths.
    pm.group = None
    pm.units = None
    assert pm.paths.get("value")

    monkeypatch.setattr(
        catalog,
        "_build_param_map_from_obj",
        lambda obj, tok, origin="inline": pm if tok == "PARAM_PATHS" else None,
    )
    monkeypatch.setattr(catalog, "_parse_index_token_raw_maps", lambda _code: {"PARAM_PATHS": raw})
    mapped = await catalog.get_param_mapping(["PARAM_PATHS"])
    assert "PARAM_PATHS" in mapped
