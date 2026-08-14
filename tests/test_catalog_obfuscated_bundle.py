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

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import (
    AssetRef,
    LiveAssetsCatalog,
    _collect_bindings,
    _count_js_escape_leaks,
    _i18n_import_base_and_hash,
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
