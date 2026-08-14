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
    LiveAssetsCatalog,
    _count_js_escape_leaks,
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


def test_count_js_escape_leaks_walks_nested_values() -> None:
    r"""A leftover ``\x20`` in nested i18n is a leak; a decoded space is not."""
    assert _count_js_escape_leaks("8087 ") == 0
    assert _count_js_escape_leaks("8087 \\x20") == 1
    assert _count_js_escape_leaks({"0": " ", "1": "a\\u00a0b"}) == 1
    assert _count_js_escape_leaks([{"x": "ok"}, {"y": "\\x0a"}]) == 1


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
