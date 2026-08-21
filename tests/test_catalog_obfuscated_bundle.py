"""Regression tests for the obfuscated live web-app bundle shape.

The production index quotes ordinary object keys, hex-keys the units table, and
emits hashed chunk names that contain (or even end with) hyphens. Hand-written
readable fixtures never exercised that combination, so language config, i18n
lookup, and the descriptor table each failed silently.
"""

from __future__ import annotations

import logging
from typing import cast

import pytest
from tree_sitter import Node

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import (
    AssetRef,
    LiveAssetsCatalog,
    _collect_bindings,
    _count_js_escape_leaks,
    _eval_arrow_body,
    _eval_js_binary,
    _i18n_import_base_and_hash,
    _is_js_nullish,
    _js_concat,
    _js_nullish_aware_equal,
    _js_truthy,
    _node_to_python,
    _walk,
)


class _DummyApi:
    """Stand-in used when a test never fetches the network."""

    one_base = "https://example.invalid"


class _IndexApi:
    """Return canned index and i18n bytes for ``get_i18n`` tests."""

    one_base = "https://one.brager.pl"

    def __init__(self, index: str, files: dict[str, str]) -> None:
        """Store index JS and a filename-to-source map."""
        self._index = index.encode()
        self._files = files

    async def get_bytes(self, url: str) -> bytes:
        """Return the index or a named i18n chunk."""
        name = url.rsplit("/", 1)[-1]
        if name.startswith("index-"):
            return self._index
        if name in self._files:
            return self._files[name].encode()
        raise AssertionError(f"unexpected fetch {url}")


def _catalog(api: object | None = None) -> LiveAssetsCatalog:
    """Build a catalog around ``api``, or a dummy that must not be fetched."""
    return LiveAssetsCatalog(cast(BragerOneApiClient, api or _DummyApi()))


_LIVE_LANGUAGE_SHAPE = """
define_AppContainer_default$6={'translations':[
  {'id':'PL','flag':'pl','variants':{'153':{'1201':'PL_5_RTP_TIS'}}},
  {'id':'EN','flag':'en'}
],'defaultTranslation':'pl'};
const _u={0x9:{'text':'units.1'},0x31:{'text':'units.31','value':"_0x2=>Number(_0x2*0.1)['toFixed'](0x1)"}};
"""


def test_property_name_unquotes_and_coerces_numeric_keys() -> None:
    """Quoted string keys and hex numeric keys resolve to the JS property name."""
    code = b"const o={'translations':1,0xa:2};"
    tree = _catalog()._ts.parse(code)
    obj = next(node for node in _walk(tree.root_node) if node.type == "object")
    parsed = _node_to_python(code, obj)
    assert parsed == {"translations": 1, "10": 2}


def test_quoted_language_config_matches_live_bundle() -> None:
    """Live index uses ``{'translations':..., 'defaultTranslation':...}``, not identifiers."""
    cfg = _catalog()._parse_language_config_from_js(_LIVE_LANGUAGE_SHAPE.encode())
    assert cfg.default_translation == "pl"
    assert cfg.translations[0]["id"] == "PL"
    assert cfg.translations[0]["flag"] == "pl"
    assert cfg.translations[0]["variants"]["153"]["1201"] == "PL_5_RTP_TIS"
    assert cfg.translations[1]["id"] == "EN"


def test_hex_keyed_descriptor_table_parses_beside_quoted_language_config() -> None:
    """The units table and language config can share one obfuscated index."""
    table = _catalog()._parse_units_descriptor_table_from_index(_LIVE_LANGUAGE_SHAPE.encode())
    assert table["9"]["text"] == "units.1"
    assert table["49"]["text"] == "units.31"


def test_empty_descriptor_table_warns_when_keys_cannot_be_normalized(caplog: pytest.LogCaptureFixture) -> None:
    """Descriptor-shaped values with non-numeric keys must not fail silently."""
    js = b"const table={foo:{text:'units.1'},bar:{options:{1:'x'}}};"
    with caplog.at_level(logging.WARNING, logger="pybragerone.models.catalog"):
        table = _catalog()._parse_units_descriptor_table_from_index(js)
    assert table == {}
    assert any("kept 0 of" in rec.getMessage() for rec in caplog.records)


def test_empty_descriptor_table_warns_on_large_index_without_candidates(caplog: pytest.LogCaptureFixture) -> None:
    """A 50k+ index with no descriptor-shaped objects is a silent empty table we must flag."""
    js = b"const x=1;\n" + b"//" + (b"x" * 50_000)
    with caplog.at_level(logging.WARNING, logger="pybragerone.models.catalog"):
        table = _catalog()._parse_units_descriptor_table_from_index(js)
    assert table == {}
    assert any("parsed to 0 entries from a" in rec.getMessage() for rec in caplog.records)


def test_count_js_escape_leaks_walks_nested_values() -> None:
    r"""A leftover ``\x20`` in nested i18n is a leak; a decoded space is not."""
    assert _count_js_escape_leaks("8087 ") == 0
    assert _count_js_escape_leaks("8087 \\x20") == 1
    assert _count_js_escape_leaks({"0": " ", "1": "a\\u00a0b"}) == 1
    assert _count_js_escape_leaks([{"x": "ok"}, {"y": "\\x0a"}]) == 1
    assert _count_js_escape_leaks("emoji \\u{1F4A9}") == 1
    assert _count_js_escape_leaks("\\x2") == 0
    assert _count_js_escape_leaks("\\u00") == 0
    assert _count_js_escape_leaks("\\u00a0") == 1
    assert _count_js_escape_leaks(0) == 0
    assert _count_js_escape_leaks(None) == 0


@pytest.mark.asyncio
async def test_i18n_hash_may_end_with_a_hyphen() -> None:
    """Vite hashes such as ``Db9Vj8s-`` used to miss the import regex entirely."""
    index = (
        "Object.assign({"
        '"../../resources/languages/en/tariff.json":'
        "()=>d(()=>import('./tariff-Db9Vj8s-.js'),true?[]:void 0x0)['then'](e=>e.default)"
        "});"
    )
    api = _IndexApi(index, {"tariff-Db9Vj8s-.js": "export default {'peak': 'Peak'};"})
    catalog = _catalog(api)
    await catalog.refresh_index("https://one.brager.pl/assets/index-Ab12.js", allow_recover=False)
    data = await catalog.get_i18n("en", "tariff")
    assert data == {"peak": "Peak"}


@pytest.mark.asyncio
async def test_i18n_hash_may_contain_an_internal_hyphen() -> None:
    """``info-Bpu026-3.js`` must resolve even when basename splitting is ambiguous."""
    index = 'var assets={"../../resources/languages/pl/info.json":()=>d(()=>import("./info-Bpu026-3.js"),[])};'
    api = _IndexApi(index, {"info-Bpu026-3.js": "export default {'title': 'Info'};"})
    catalog = _catalog(api)
    await catalog.refresh_index("https://one.brager.pl/assets/index-Ab12.js", allow_recover=False)
    data = await catalog.get_i18n("pl", "info")
    assert data == {"title": "Info"}


@pytest.mark.asyncio
async def test_get_i18n_warns_on_escape_leaks(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    r"""Fetched namespaces that still contain ``\x`` sequences log a warning."""
    index = 'var assets={"../../resources/languages/pl/units.json":()=>d(()=>import("./units-Ab12.js"),[])};'
    api = _IndexApi(index, {"units-Ab12.js": "export default {'0': 'ok'};"})
    catalog = _catalog(api)
    await catalog.refresh_index("https://one.brager.pl/assets/index-Ab12.js", allow_recover=False)
    monkeypatch.setattr(catalog, "_parse_i18n_from_js", lambda _code: {"0": "8087 \\x20"})
    with caplog.at_level(logging.WARNING, logger="pybragerone.models.catalog"):
        data = await catalog.get_i18n("pl", "units")
    assert data == {"0": "8087 \\x20"}
    assert any("escape sequences" in rec.getMessage() for rec in caplog.records)


@pytest.mark.asyncio
async def test_get_i18n_warns_when_fetched_asset_parses_empty(caplog: pytest.LogCaptureFixture) -> None:
    """A successful fetch that yields ``{}`` is a shape change, not a valid namespace."""
    index = 'var assets={"../../resources/languages/pl/units.json":()=>d(()=>import("./units-Ab12.js"),[])};'
    api = _IndexApi(index, {"units-Ab12.js": "export default {};"})
    catalog = _catalog(api)
    await catalog.refresh_index("https://one.brager.pl/assets/index-Ab12.js", allow_recover=False)
    with caplog.at_level(logging.WARNING, logger="pybragerone.models.catalog"):
        data = await catalog.get_i18n("pl", "units")
    assert data == {}
    assert any("parsed to 0 keys" in rec.getMessage() for rec in caplog.records)


@pytest.mark.parametrize(
    "parsed",
    [
        ["not", "a", "dict"],
        {"translations": "nope", "defaultTranslation": "pl"},
        {"translations": [{"id": "PL", "flag": "pl"}], "defaultTranslation": 1},
        {"translations": [{"id": "PL", "flag": "pl"}], "defaultTranslation": ""},
        {"translations": [1, "x"], "defaultTranslation": "pl"},
    ],
)
def test_language_config_rejects_malformed_parsed_object(monkeypatch: pytest.MonkeyPatch, parsed: object) -> None:
    """Guards after a successful structural match must still reject a bad Python value."""
    monkeypatch.setattr("pybragerone.models.catalog._node_to_python", lambda *_args, **_kwargs: parsed)
    with pytest.raises(ValueError, match="missing required fields"):
        _catalog()._parse_language_config_from_js(_LIVE_LANGUAGE_SHAPE.encode())


def test_language_config_rejects_empty_default_translation_string() -> None:
    """``defaultTranslation:''`` still matches the structural scan, then fails validation."""
    js = b"const c={'translations':[{'id':'PL','flag':'pl'}],'defaultTranslation':''};"
    with pytest.raises(ValueError, match="missing required fields"):
        _catalog()._parse_language_config_from_js(js)


def _index_with_i18n_import(filename: str, *, lang: str = "pl", namespace: str = "units") -> bytes:
    """Build a minimal index that points one namespace at ``filename``."""
    return (
        f"var assets={{\"../../resources/languages/{lang}/{namespace}.json\":()=>d(()=>import('./{filename}'),[])}};"
    ).encode()


def test_find_i18n_asset_accepts_unhashed_filename() -> None:
    """``import('./units.js')`` has no ``-hash`` segment to split on."""
    catalog = _catalog()
    catalog._idx.index_bytes = _index_with_i18n_import("units.js")
    catalog._last_index_url = "https://one.brager.pl/assets/index-Ab12.js"
    ref = catalog._find_i18n_asset("pl", "units")
    assert ref is not None
    assert ref.base == "units"
    assert ref.hash == ""
    assert ref.url.endswith("/units.js")


def test_find_i18n_asset_basename_matches_unhashed_import() -> None:
    """An empty hash (unhashed ``units.js``) must still accept a basename catalog hit."""
    catalog = _catalog()
    catalog._idx.index_bytes = _index_with_i18n_import("units.js")
    asset = AssetRef(url="https://cdn.example/not-units.js", base="units", hash="ignored")
    catalog._idx.assets_by_basename["units"] = [asset]
    assert catalog._find_i18n_asset("pl", "units") is asset


def test_find_i18n_asset_falls_back_to_basename_when_full_name_misses() -> None:
    """Basename+hash still wins when the stored URL does not match the import filename."""
    catalog = _catalog()
    catalog._idx.index_bytes = _index_with_i18n_import("units-Ab12.js")
    catalog._idx.assets_by_basename["units"] = [AssetRef(url="https://cdn.example/not-the-import.js", base="units", hash="Ab12")]
    ref = catalog._find_i18n_asset("pl", "units")
    assert ref is not None
    assert ref.hash == "Ab12"
    assert ref.url == "https://cdn.example/not-the-import.js"


def test_find_i18n_asset_falls_back_to_index_url_when_hash_mismatches() -> None:
    """A basename hit with the wrong hash must not be returned; join against the index URL."""
    catalog = _catalog()
    catalog._idx.index_bytes = _index_with_i18n_import("units-Ab12.js")
    catalog._idx.assets_by_basename["units"] = [AssetRef(url="https://cdn.example/units-OTHER.js", base="units", hash="OTHER")]
    catalog._last_index_url = "https://one.brager.pl/assets/index-Ab12.js"
    ref = catalog._find_i18n_asset("pl", "units")
    assert ref is not None
    assert ref.base == "units"
    assert ref.hash == "Ab12"
    assert ref.url.endswith("/units-Ab12.js")


def test_find_i18n_asset_returns_none_without_index_url_or_catalog_hit() -> None:
    """No index URL and no catalog hit means the namespace is simply missing."""
    catalog = _catalog()
    catalog._idx.index_bytes = _index_with_i18n_import("units-Ab12.js")
    catalog._last_index_url = None
    assert catalog._find_i18n_asset("pl", "units") is None


@pytest.mark.parametrize(
    ("namespace", "stem", "base", "file_hash"),
    [
        ("units", "units", "units", ""),
        ("Units", "units", "Units", ""),
        ("units", "units-Ab12", "units", "Ab12"),
        ("info", "info-Bpu026-3", "info", "Bpu026-3"),
        ("Info", "info-Bpu026-3", "Info", "Bpu026-3"),
        ("tariff", "tariff-Db9Vj8s-", "tariff", "Db9Vj8s-"),
        ("units", "other-Ab12", "other-Ab12", ""),
    ],
)
def test_i18n_import_base_and_hash_uses_json_namespace(namespace: str, stem: str, base: str, file_hash: str) -> None:
    """Hashes with internal or trailing hyphens stay attached to the JSON namespace."""
    assert _i18n_import_base_and_hash(namespace, stem) == (base, file_hash)


def test_find_i18n_asset_basename_matches_hyphenated_hash() -> None:
    """``info-Bpu026-3`` must look up basename ``info``, not ``info-Bpu026``."""
    catalog = _catalog()
    catalog._idx.index_bytes = _index_with_i18n_import("info-Bpu026-3.js", namespace="info")
    asset = AssetRef(url="https://cdn.example/info-other.js", base="info", hash="Bpu026-3")
    catalog._idx.assets_by_basename["info"] = [asset]
    assert catalog._find_i18n_asset("pl", "info") is asset


def test_find_i18n_asset_url_fallback_preserves_trailing_hyphen_hash() -> None:
    """URL fallback must keep ``Db9Vj8s-`` as the hash, not an empty rpartition tail."""
    catalog = _catalog()
    catalog._idx.index_bytes = _index_with_i18n_import("tariff-Db9Vj8s-.js", lang="en", namespace="tariff")
    catalog._last_index_url = "https://one.brager.pl/assets/index-Ab12.js"
    ref = catalog._find_i18n_asset("en", "tariff")
    assert ref is not None
    assert ref.base == "tariff"
    assert ref.hash == "Db9Vj8s-"
    assert ref.url.endswith("/tariff-Db9Vj8s-.js")


def test_find_i18n_asset_url_fallback_when_filename_does_not_start_with_namespace() -> None:
    """A divergent import filename still joins against the index URL."""
    catalog = _catalog()
    catalog._idx.index_bytes = _index_with_i18n_import("other-Ab12.js")
    catalog._last_index_url = "https://one.brager.pl/assets/index-Ab12.js"
    ref = catalog._find_i18n_asset("pl", "units")
    assert ref is not None
    assert ref.base == "other-Ab12"
    assert ref.hash == ""
    assert ref.url.endswith("/other-Ab12.js")


def test_extract_language_helpers_handle_quoted_keys() -> None:
    """The leftover byte helpers must unquote ``{'translations': ...}`` the same way as the main parser."""
    catalog = _catalog()
    js = _LIVE_LANGUAGE_SHAPE.encode()
    translations: list[dict[str, object]] | None = None
    for node in _walk(catalog._ts.parse(js).root_node):
        if node.type != "object":
            continue
        translations = catalog._extract_translations_array_bytes(node, js)
        if translations:
            assert catalog._extract_default_translation_bytes(node, js) == "pl"
            break
    assert translations is not None
    assert translations[0]["id"] == "PL"
    non_array = b"const c={'translations':1,'defaultTranslation':'pl'};"
    other = next(node for node in _walk(catalog._ts.parse(non_array).root_node) if node.type == "object")
    assert catalog._extract_translations_array_bytes(other, non_array) is None
    assert catalog._extract_default_translation_bytes(other, non_array) == "pl"
    numeric = b"const c={'foo':1,'defaultTranslation':1};"
    num_obj = next(node for node in _walk(catalog._ts.parse(numeric).root_node) if node.type == "object")
    assert catalog._extract_default_translation_bytes(num_obj, numeric) is None


def test_node_to_python_resolves_string_subscript_to_public_name() -> None:
    """``_0xabc['DISPLAY_FOO']`` is the public enum name, not leftover source text."""
    code = b"const o={'permissionModule':_0x521864['DISPLAY_PARAMETER_LEVEL_1'],'op':_0x4891b3['equalTo']};"
    tree = _catalog()._ts.parse(code)
    obj = next(node for node in _walk(tree.root_node) if node.type == "object")
    parsed = _node_to_python(code, obj)
    assert parsed == {"permissionModule": "DISPLAY_PARAMETER_LEVEL_1", "op": "equalTo"}


def test_node_to_python_evaluates_array_map_of_param_tokens() -> None:
    """Live menus 153/2190 wrap write lists in ``array['map'](x => ({…, parameter: helper(WRITE, x)}))``."""
    code = (
        b"const v=['PARAM_45','PARAM_34']['map'](_0x46820c=>("
        b"{'permissionModule':_0x58838d['DISPLAY_PARAMETER_LEVEL_1'],"
        b"'parameter':_0x2d2290(_0x870f31['WRITE'],_0x46820c)}));"
    )
    tree = _catalog()._ts.parse(code)
    call = next(node for node in _walk(tree.root_node) if node.type == "call_expression")
    parsed = _node_to_python(code, call)
    assert parsed == [
        {"permissionModule": "DISPLAY_PARAMETER_LEVEL_1", "parameter": "PARAM_45"},
        {"permissionModule": "DISPLAY_PARAMETER_LEVEL_1", "parameter": "PARAM_34"},
    ]


def test_eval_array_map_call_rejects_non_map_shapes() -> None:
    """``array['map']`` evaluation must not swallow unrelated calls or non-list receivers."""
    catalog = _catalog()

    def _call(js: bytes) -> object:
        tree = catalog._ts.parse(js)
        call = next(node for node in _walk(tree.root_node) if node.type == "call_expression")
        return _node_to_python(js, call)

    assert _call(b"const v=arr[0](x=>({a:1}));") == "arr[0](x=>({a:1}))"
    assert _call(b"const v=[1]['filter'](x=>({a:1}));") == "[1]['filter'](x=>({a:1}))"
    assert _call(b"const v='nope'['map'](x=>({a:1}));") == "'nope'['map'](x=>({a:1}))"
    assert _call(b"const v=[1]['map']();") == "[1]['map']()"
    assert _call(b"const v=[1]['map'](1);") == "[1]['map'](1)"

    def _boom(_item: object) -> object:
        raise TypeError("unexpected callback shape")

    raising = b"const v=[1]['map'](fn);"
    tree = catalog._ts.parse(raising)
    call = next(node for node in _walk(tree.root_node) if node.type == "call_expression")
    assert _node_to_python(raising, call, {"fn": _boom}) == "[1]['map'](fn)"


def test_node_to_python_returns_helper_last_arg_token() -> None:
    """Only obfuscated ``_0x…(WRITE, 'PARAM_45')`` helpers collapse to the public token."""
    catalog = _catalog()

    def _call(js: bytes) -> object:
        tree = catalog._ts.parse(js)
        call = next(node for node in _walk(tree.root_node) if node.type == "call_expression")
        return _node_to_python(js, call)

    assert _call(b"const v=_0x2d2290(_0x870f31['WRITE'],'PARAM_45');") == "PARAM_45"
    assert _call(b"const v=_0x2d2290(_0x870f31['STATUS'],'STATUS_P5_1');") == "STATUS_P5_1"

    # A readable callee with the same signature keeps its semantics.
    assert _call(b"const v=foo('WRITE','PARAM_45');") == "foo('WRITE','PARAM_45')"
    assert _call(b"const v=_0x1a['helper']('WRITE','PARAM_45');") == "_0x1a['helper']('WRITE','PARAM_45')"

    # Argument-shape guards, all behind an obfuscated callee.
    assert _call(b"const v=_0x2d2290();") == "_0x2d2290()"
    assert _call(b"const v=_0x2d2290(1);") == "_0x2d2290(1)"
    assert _call(b"const v=_0x2d2290('PARAM_45');") == "_0x2d2290('PARAM_45')"
    assert _call(b"const v=_0x2d2290(1,'PARAM_45');") == "_0x2d2290(1,'PARAM_45')"
    assert _call(b"const v=_0x2d2290('EQUALTO','PARAM_45');") == "_0x2d2290('EQUALTO','PARAM_45')"
    assert _call(b"const v=_0x2d2290('WRITE',1);") == "_0x2d2290('WRITE',1)"
    assert _call(b"const v=_0x2d2290('WRITE','DISPLAY_PARAMETER_LEVEL_1');") == ("_0x2d2290('WRITE','DISPLAY_PARAMETER_LEVEL_1')")


def test_node_to_python_invokes_bound_callable_with_multiple_args() -> None:
    """A bound callee with two arguments receives the argument list, not just the first value."""
    code = b"const v=fn(1,2);"
    tree = _catalog()._ts.parse(code)
    call = next(node for node in _walk(tree.root_node) if node.type == "call_expression")
    assert _node_to_python(code, call, {"fn": lambda args: args}) == [1, 2]


def test_node_to_python_does_not_collapse_array_map_subscript() -> None:
    """``['PARAM_1']['map']`` must keep the array so issue #285 can evaluate the call."""
    code = b"const v=['PARAM_1']['map'];"
    tree = _catalog()._ts.parse(code)
    sub = next(node for node in _walk(tree.root_node) if node.type == "subscript_expression")
    parsed = _node_to_python(code, sub)
    assert parsed == "['PARAM_1']['map']"


def test_node_to_python_does_not_collapse_identifier_method_subscript() -> None:
    """``arr['map']`` is a method lookup, not an obfuscated ``_0x…['ENUM']`` alias."""
    code = b"const v=arr['map'];"
    tree = _catalog()._ts.parse(code)
    sub = next(node for node in _walk(tree.root_node) if node.type == "subscript_expression")
    assert _node_to_python(code, sub) == "arr['map']"
    math_floor = b"const v=Math['floor'];"
    math_tree = _catalog()._ts.parse(math_floor)
    math_sub = next(node for node in _walk(math_tree.root_node) if node.type == "subscript_expression")
    assert _node_to_python(math_floor, math_sub) == "Math['floor']"


def test_node_to_python_resolves_identifier_subscript_from_bindings() -> None:
    """``_0x['DISPLAY_FOO']`` looks up the bound object when the catalog collected it."""
    code = b"const _0x={'DISPLAY_FOO':'yes','OTHER':1}; const v=_0x['DISPLAY_FOO'];"
    tree = _catalog()._ts.parse(code)
    bindings = _collect_bindings(code, tree.root_node)
    sub = next(node for node in _walk(tree.root_node) if node.type == "subscript_expression")
    assert _node_to_python(code, sub, bindings) == "yes"
    missing = b"const v=_0x['MISSING'];"
    missing_tree = _catalog()._ts.parse(missing)
    missing_sub = next(node for node in _walk(missing_tree.root_node) if node.type == "subscript_expression")
    assert _node_to_python(missing, missing_sub, bindings) == "MISSING"
    not_map = b"const v=_0x['DISPLAY_FOO'];"
    not_map_tree = _catalog()._ts.parse(not_map)
    not_map_sub = next(node for node in _walk(not_map_tree.root_node) if node.type == "subscript_expression")
    assert _node_to_python(not_map, not_map_sub, {"_0x": "not-a-map"}) == "DISPLAY_FOO"


def test_node_to_python_keeps_non_string_subscript() -> None:
    """Computed numeric indexes are not public enum names."""
    code = b"const v=arr[0];"
    tree = _catalog()._ts.parse(code)
    sub = next(node for node in _walk(tree.root_node) if node.type == "subscript_expression")
    assert _node_to_python(code, sub) == "arr[0]"


_LIVE_PARAM_66 = b"""
const builder={
  'name':'parameters.PARAM_66',
  'useComponent':_0x4d7e32['SWITCH'],
  'status':{[_0x4d7e32['INVISIBLE']]:[{'group':'P6','number':0x22,'use':'s'}],
            [_0x4d7e32['ENABLED']]:[{'group':'P6','number':0x23,'use':'s'}]},
  'any':[{'if':[{'operation':_0x4891b3['equalTo'],'expected':![],'value':[{'group':'P6','number':0x22}]}],
          'then':{'command':_0xabc['WRITE'],'value':!![]}}]
};
export { builder as default };
"""


def test_param_map_recovers_computed_status_keys_and_bool_literals() -> None:
    """Live PARAM_66 hides status names in computed keys and booleans in `![]` / `!![]`."""
    param = _catalog()._parse_param_map_from_js(_LIVE_PARAM_66, "PARAM_66", "test")
    assert param is not None
    assert param.component_type == "SWITCH"
    assert sorted(param.status_conditions or {}) == ["ENABLED", "INVISIBLE"]
    rule = param.command_rules[0]
    assert rule["command"] == "WRITE"
    assert rule["value"] is True
    assert rule["conditions"][0]["operation"] == "equalTo"
    assert rule["conditions"][0]["expected"] is False
    # Schema drift: the pool now lives on the nested channel refs, not at the top level.
    assert param.group is None


def test_property_name_resolves_computed_keys() -> None:
    """Computed keys resolve through the public enum name, the literal, or the raw text."""
    code = b"const o={[_0x4d['INVISIBLE']]:1,['lit']:2,[0x9]:3,[someVar]:4};"
    tree = _catalog()._ts.parse(code)
    obj = next(node for node in _walk(tree.root_node) if node.type == "object")
    assert _node_to_python(code, obj) == {"INVISIBLE": 1, "lit": 2, "9": 3, "someVar": 4}


@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        ("!0", True),
        ("!1", False),
        ("![]", False),
        ("!![]", True),
        ("true", "true"),
        ("void 0", None),
        ("undefined", None),
        ("PARAM_45", "PARAM_45"),
    ],
)
def test_command_rule_literals_normalize(literal: str, expected: object) -> None:
    """Minified boolean and undefined spellings normalize to Python values."""
    catalog = _catalog()
    param = catalog._build_param_map_from_obj(
        {"PARAM_X": {"group": "P4", "any": [{"if": [], "then": {"command": "WRITE", "value": literal}}]}},
        "PARAM_X",
        "test",
    )
    assert param is not None
    if expected is None:
        assert "value" not in param.command_rules[0]
    else:
        assert param.command_rules[0]["value"] == expected


def test_component_type_prefers_explicit_field_over_use_component() -> None:
    """``componentType`` wins; ``useComponent`` is only the obfuscated-bundle alias."""
    catalog = _catalog()
    both = catalog._build_param_map_from_obj(
        {"PARAM_X": {"componentType": "number", "useComponent": "SWITCH"}}, "PARAM_X", "test"
    )
    assert both is not None
    assert both.component_type == "number"
    neither = catalog._build_param_map_from_obj({"PARAM_X": {"group": "P4"}}, "PARAM_X", "test")
    assert neither is not None
    assert neither.component_type is None


_LIVE_PARAM_BUILDERS = b"""
const IconsList={'INFO':'INFO'},ParameterStatus={'INVISIBLE':'INVISIBLE'},
basicParameterBuilder_P11=({id:_0x581f65,icon:icon=IconsList['INFO'],number:_0x5273a8,
    useComponent:useComponent=void 0x0,status:status={}})=>{
  const _0x888193={'id':_0x581f65,'icon':icon,'name':'parameters.PARAM_P11_'+_0x5273a8,
    'value':[{'group':'P11','number':_0x5273a8,'use':'v'}],
    'status':{...{[ParameterStatus['INVISIBLE']]:[{'group':'P11','number':_0x5273a8,'use':'s','bit':0x7}]},...status},
    'useComponent':useComponent};
  return _0x888193;
},
paramTable={'PARAM_P11_1':basicParameterBuilder_P11({'id':0x1268919fb79d,'number':0x1}),
  'PARAM_P11_9':basicParameterBuilder_P11({'id':0x1268919fb7a5,'number':0x9,'useComponent':'SWITCH'})};
"""


def test_parameter_factory_builders_expand_to_param_maps() -> None:
    """Live inline parameters are ``basicParameterBuilder_PX({id, number})`` calls."""
    catalog = _catalog()
    maps = catalog._parse_index_token_raw_maps(_LIVE_PARAM_BUILDERS)
    assert "PARAM_P11_1" in maps
    built = catalog._build_param_map_from_obj(dict(maps["PARAM_P11_1"]), "PARAM_P11_1", "test")
    assert built is not None
    assert built.raw["name"] == "parameters.PARAM_P11_1"
    assert built.paths["value"] == [{"group": "P11", "number": 1, "use": "v"}]
    assert built.status_conditions is not None
    assert list(built.status_conditions) == ["INVISIBLE"]
    assert built.status_conditions["INVISIBLE"][0]["bit"] == 7
    assert "INVISIBLE" in (built.raw.get("status") or {})
    # `useComponent: void 0x0` is undefined, not a component name.
    assert built.component_type is None
    override = catalog._build_param_map_from_obj(dict(maps["PARAM_P11_9"]), "PARAM_P11_9", "test")
    assert override is not None
    assert override.component_type == "SWITCH"
    assert override.raw["name"] == "parameters.PARAM_P11_9"


_LIVE_NULLISH_NAME_BUILDERS = b"""
const IconsList={'INFO':'INFO'},
basicParameterBuilder_P6=({id:_0x522d69,icon:icon=IconsList['INFO'],name:_0x45f6f0,number:_0x3a4660,
    useComponent:useComponent=void 0x0,status:status={}})=>{
  const _0x4b63ed={'id':_0x522d69,'icon':icon,'name':_0x45f6f0??'parameters.PARAM_'+_0x3a4660,
    'value':[{'group':'P6','number':_0x3a4660,'use':'v'}],'useComponent':useComponent};
  return _0x4b63ed;
},
basicParameterBuilder_P32=({id:_0x1,name:_0x19fab0,number:_0x3211ea})=>{
  const _0x2={'id':_0x1,'name':_0x19fab0!==void 0x0?_0x19fab0:'parameters.PARAM_P32_'+_0x3211ea,
    'value':[{'group':'P32','number':_0x3211ea,'use':'v'}]};
  return _0x2;
},
paramTable={'PARAM_10':basicParameterBuilder_P6({'id':0x1,'number':0xa}),
  'PARAM_63':basicParameterBuilder_P6({'id':0x2,'number':0x3f,'name':'parameters.CUSTOM_63'}),
  'PARAM_P32_4':basicParameterBuilder_P32({'id':0x3,'number':0x4}),
  'PARAM_P32_9':basicParameterBuilder_P32({'id':0x4,'number':0x9,'name':'parameters.OVERRIDE'})};
"""


def test_parameter_factory_nullish_and_ternary_name_defaults() -> None:
    """Optional ``name`` args use ``??`` / ``!== void 0x0 ?`` defaults to ``parameters.*``."""
    catalog = _catalog()
    maps = catalog._parse_index_token_raw_maps(_LIVE_NULLISH_NAME_BUILDERS)
    assert maps["PARAM_10"]["name"] == "parameters.PARAM_10"
    assert maps["PARAM_63"]["name"] == "parameters.CUSTOM_63"
    assert maps["PARAM_P32_4"]["name"] == "parameters.PARAM_P32_4"
    assert maps["PARAM_P32_9"]["name"] == "parameters.OVERRIDE"
    built = catalog._build_param_map_from_obj(dict(maps["PARAM_10"]), "PARAM_10", "test")
    assert built is not None
    assert built.raw["name"] == "parameters.PARAM_10"
    assert built.paths["value"] == [{"group": "P6", "number": 10, "use": "v"}]


def test_js_nullish_ternary_and_equality_helpers() -> None:
    """Cover nullish / equality / truthiness helpers and leftover AST edges for patch coverage."""
    assert _is_js_nullish(None) is True
    assert _is_js_nullish("undefined") is True
    assert _is_js_nullish("void 0") is True
    assert _is_js_nullish("void 0x0") is True
    assert _is_js_nullish("_0x45f6f0") is True
    assert _is_js_nullish("parameters.PARAM_10") is False
    assert _is_js_nullish(0) is False

    assert _js_nullish_aware_equal(None, "undefined") is True
    assert _js_nullish_aware_equal(None, "_0xabc") is True
    assert _js_nullish_aware_equal(1, 1) is True
    assert _js_nullish_aware_equal(1, 2) is False

    assert _eval_js_binary("+", "a", 1) == (True, "a1")
    assert _eval_js_binary("+", [], {}) == (False, None)
    assert _eval_js_binary("??", None, "fallback") == (True, "fallback")
    assert _eval_js_binary("??", "kept", "fallback") == (True, "kept")
    assert _eval_js_binary("||", None, "fallback") == (True, "fallback")
    assert _eval_js_binary("||", "", "fallback") == (True, "fallback")
    assert _eval_js_binary("||", "kept", "fallback") == (True, "kept")
    assert _eval_js_binary("&&", "kept", "right") == (True, "right")
    assert _eval_js_binary("&&", None, "right") == (True, None)
    assert _eval_js_binary("===", None, None) == (True, True)
    assert _eval_js_binary("==", "x", "x") == (True, True)
    assert _eval_js_binary("!==", None, 1) == (True, True)
    assert _eval_js_binary("!=", 1, 1) == (True, False)
    assert _eval_js_binary("-", 1, 2) == (False, None)

    assert _js_truthy(None) is False
    assert _js_truthy(False) is False
    assert _js_truthy(0) is False
    assert _js_truthy(0.0) is False
    assert _js_truthy("") is False
    assert _js_truthy("ok") is True
    assert _js_truthy(1) is True

    # Bare ``undefined`` identifier and non-void unary leftovers.
    undef_code = b"const o={'a':undefined,'b':!0};"
    undef_tree = _catalog()._ts.parse(undef_code)
    undef_obj = next(n for n in _walk(undef_tree.root_node) if n.type == "object")
    assert _node_to_python(undef_code, undef_obj) == {"a": None, "b": "!0"}

    # ``===`` / ``!==`` through ternary AST (not only the helper).
    eq_code = b"const o={'a':'x'===undefined?'yes':'no','b':1!==undefined?'keep':'drop'};"
    eq_tree = _catalog()._ts.parse(eq_code)
    eq_obj = next(n for n in _walk(eq_tree.root_node) if n.type == "object")
    assert _node_to_python(eq_code, eq_obj) == {"a": "no", "b": "keep"}

    # Unknown binary operators fall back to leftover source text.
    unknown = b"const o={'a':1-2};"
    unknown_tree = _catalog()._ts.parse(unknown)
    unknown_obj = next(n for n in _walk(unknown_tree.root_node) if n.type == "object")
    assert _node_to_python(unknown, unknown_obj) == {"a": "1-2"}


def test_arrow_factory_keeps_non_object_bodies_as_source() -> None:
    """Unit transforms must stay source text; only object-building arrows become callables."""
    catalog = _catalog()
    transform = b"const t=_0x2=>Number(_0x2*0.1)['toFixed'](0x1);"
    tree = catalog._ts.parse(transform)
    arrow = next(node for node in _walk(tree.root_node) if node.type == "arrow_function")
    assert isinstance(_node_to_python(transform, arrow), str)
    block_number = b"const t=(_0x2)=>{const _0x3=_0x2*2;return _0x3;};"
    block_tree = catalog._ts.parse(block_number)
    block_arrow = next(node for node in _walk(block_tree.root_node) if node.type == "arrow_function")
    assert isinstance(_node_to_python(block_number, block_arrow), str)


def test_object_spread_and_string_concat() -> None:
    """Object spread merges maps and ``'a'+n`` builds the i18n name token."""
    code = b"const base={'a':1};const o={...base,'b':'p_'+0x2,'c':1+2,'d':base};"
    tree = _catalog()._ts.parse(code)
    bindings = _collect_bindings(code, tree.root_node)
    obj = [n for n in _walk(tree.root_node) if n.type == "object"][1]
    parsed = _node_to_python(code, obj, bindings)
    assert parsed == {"a": 1, "b": "p_2", "c": 3, "d": {"a": 1}}


def test_object_spread_ignores_non_mapping_and_keeps_unknown_operators() -> None:
    """A spread of a non-object contributes nothing; ``-`` is not concatenation."""
    code = b"const o={...missing,'a':1};const d='x'-1;const e=[1]+2;"
    tree = _catalog()._ts.parse(code)
    obj = next(n for n in _walk(tree.root_node) if n.type == "object")
    assert _node_to_python(code, obj) == {"a": 1}
    minus = next(n for n in _walk(tree.root_node) if n.type == "binary_expression")
    assert _node_to_python(code, minus) == "'x'-1"


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (1, 2, 3),
        (1.5, 2, 3.5),
        ("a", "b", "ab"),
        ("p_", 2, "p_2"),
        (2, "_p", "2_p"),
        ("v", 1.0, "v1"),
        ("v", 1.5, "v1.5"),
        ("v", True, "vtrue"),
        ("v", False, "vfalse"),
        (True, 1, None),
        (1, True, None),
        ("v", None, None),
        ("v", [1], None),
        (None, None, None),
    ],
)
def test_js_concat_covers_primitive_combinations(left: object, right: object, expected: object) -> None:
    """``+`` adds numbers, joins strings, and refuses anything it cannot represent."""
    assert _js_concat(left, right) == expected


def _arrow(catalog: LiveAssetsCatalog, js: bytes) -> tuple[bytes, Node]:
    """Return the first arrow function node in ``js``."""
    tree = catalog._ts.parse(js)
    return js, next(node for node in _walk(tree.root_node) if node.type == "arrow_function")


@pytest.mark.parametrize(
    ("js", "arg", "expected"),
    [
        (b"const f=({a})=>({'x':a});", {"a": 1}, {"x": 1}),
        (b"const f=({a})=>({'x':a});", {}, {"x": None}),
        (b"const f=({a=7})=>({'x':a});", {}, {"x": 7}),
        (b"const f=({a:b=7})=>({'x':b});", {"a": 2}, {"x": 2}),
        (b"const f=({a:b})=>({'x':b});", {"a": 3}, {"x": 3}),
        (b"const f=({...rest})=>({'x':1});", {"a": 3}, {"x": 1}),
        (b"const f=(v)=>({'x':v});", 5, {"x": 5}),
        (b"const f=({a})=>{return {'x':a};};", {"a": 4}, {"x": 4}),
        (b"const f=({a})=>{const o={'x':a};return o;};", {"a": 6}, {"x": 6}),
    ],
)
def test_arrow_factory_binds_parameter_shapes(js: bytes, arg: object, expected: object) -> None:
    """Destructured, shorthand, defaulted and plain parameters all bind."""
    code, node = _arrow(_catalog(), js)
    factory = _node_to_python(code, node)
    assert callable(factory)
    assert factory(arg) == expected


@pytest.mark.parametrize(
    "js",
    [
        b"const f=({a})=>a;",  # body is not an object
        b"const f=(a,b)=>({'x':a});",  # more than one parameter
        b"const f=([a])=>({'x':a});",  # array pattern is not supported
        b"const f=({a})=>{const o=1;return o;};",  # returned identifier is not an object
        b"const f=({a})=>{return;};",  # bare return
        b"const f=({a})=>{const o={'x':a};};",  # no return statement
        b"const f=({a})=>{return f(a);};",  # returns a call, not an object
    ],
)
def test_arrow_factory_declines_non_object_builders(js: bytes) -> None:
    """Only arrows that provably build an object become callables."""
    code, node = _arrow(_catalog(), js)
    assert not callable(_node_to_python(code, node))


def test_arrow_factory_ignores_unrelated_statements_in_the_block() -> None:
    """A block may hold statements the parser does not model before the return."""
    code, node = _arrow(_catalog(), b"const f=({a})=>{let q;q=1;const o={'x':a};return o;};")
    factory = _node_to_python(code, node)
    assert callable(factory)
    assert factory({"a": 9}) == {"x": 9}


def test_eval_arrow_body_returns_none_without_a_return_statement() -> None:
    """A block that never returns yields None; the factory path rejects it earlier."""
    catalog = _catalog()
    code = b"const f=({a})=>{const o={'x':a};};"
    _, arrow = _arrow(catalog, code)
    body = arrow.child_by_field_name("body")
    assert body is not None
    assert _eval_arrow_body(code, body, {}) is None


def test_string_concat_declines_non_primitive_operands() -> None:
    """``[1]+2`` has no representation this parser will invent."""
    code = b"const e=[1]+2;"
    tree = _catalog()._ts.parse(code)
    node = next(n for n in _walk(tree.root_node) if n.type == "binary_expression")
    assert _node_to_python(code, node) == "[1]+2"


def test_optional_chain_or_fallback_fills_minmax_paths() -> None:
    """Issue #329: ``_0x?.['minValue']||[{…}]`` must become paths.min / paths.max."""
    catalog = _catalog()
    code = b"""
    const map = {
      PARAM_TEST: {
        value: [{group: 'P6', number: 1, use: 'v'}],
        minValue: _0x39dd22?.['minValue']||[{group: 'P6', number: 42, use: 'n'}],
        maxValue: _0x39dd22?.['maxValue']||[{group: 'P6', number: 42, use: 'x'}],
      }
    };
    """
    tree = catalog._ts.parse(code)
    obj_node = next(n for n in _walk(tree.root_node) if n.type == "object" and b"PARAM_TEST" in code[n.start_byte : n.end_byte])
    root = _node_to_python(code, obj_node)
    assert isinstance(root, dict)
    param_obj = root["PARAM_TEST"]
    assert isinstance(param_obj, dict)
    built = catalog._build_param_map_from_obj(param_obj, "PARAM_TEST", "test")
    assert built is not None
    assert built.paths["min"] == [{"group": "P6", "number": 42, "use": "n"}]
    assert built.paths["max"] == [{"group": "P6", "number": 42, "use": "x"}]
    # Non-optional ``_0x['KEY']`` remains an import-alias public name.
    alias_code = b"_0x521864['DISPLAY_MENU_DHW']"
    alias_tree = catalog._ts.parse(alias_code)
    alias_expr = alias_tree.root_node.named_children[0]
    if alias_expr.type == "expression_statement":
        alias_expr = alias_expr.named_children[0]
    assert _node_to_python(alias_code, alias_expr) == "DISPLAY_MENU_DHW"
