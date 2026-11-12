"""Parity: pure-Python i18n/units/language parsers vs tree-sitter oracles."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import LiveAssetsCatalog, TranslationConfig

_ASSETS = Path(__file__).resolve().parent / "assets"
_I18N_ASSETS = sorted((_ASSETS / "i18n").glob("*.js")) if (_ASSETS / "i18n").is_dir() else []
_INDEX_ASSETS = sorted((_ASSETS / "index").glob("*.js")) if (_ASSETS / "index").is_dir() else []


class _DummyApi:
    """Stand-in; parity tests never fetch the network."""

    one_base = "https://example.invalid"


def _catalog() -> LiveAssetsCatalog:
    return LiveAssetsCatalog(cast(BragerOneApiClient, _DummyApi()))


def _normalize_for_parity(value: Any) -> Any:
    """Drop callables / normalize arrows so pure vs tree-sitter can compare."""
    if callable(value) and not isinstance(value, type):
        return "<callable>"
    if isinstance(value, Mapping):
        return {str(k): _normalize_for_parity(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_for_parity(v) for v in value]
    if isinstance(value, str) and "=>" in value:
        return "<arrow>"
    return value


def _assert_parity(
    pure: Any,
    treesitter: Any,
    *,
    label: str,
) -> None:
    assert _normalize_for_parity(pure) == _normalize_for_parity(treesitter), label


@pytest.mark.parametrize(
    "js",
    [
        b'export default { "hi": "there" };',
        b"const bundle = { ok: true };\nexport { bundle as default };\n",
        b"const only = { a: 1 };",
        "const MAINMENU_MENU_TERMOSTATU='Menu\\x20termostatów';export{MAINMENU_MENU_TERMOSTATU as default};\n".encode(),
        b'export default "Bare title";',
        b"const MAINMENU_X='Title';\nexport default MAINMENU_X;\n",
        b"export default {};",
        b"const t={'a':'Ilo\\u015b\\u0107\\x20rozpale\\u0144'};export default t;",
    ],
)
def test_i18n_pure_matches_treesitter_fixtures(js: bytes) -> None:
    """Hand fixtures: pure i18n parse equals tree-sitter oracle."""
    catalog = _catalog()
    _assert_parity(
        catalog._parse_i18n_from_js(js),
        catalog._parse_i18n_from_js_treesitter(js),
        label=js[:60].decode("utf-8", errors="replace"),
    )


@pytest.mark.parametrize(
    "js",
    [
        (
            b"const u={0x9:{'options':{0x0:'units.17.0',0x1:'units.17.1'}},"
            b"0xa:{'text':'units.10','value':_0x201288=>_0x201288*0x6},"
            b"0x31:{'text':'units.31','value':_0x4fdb4d=>Number(_0x4fdb4d*0.1)['toFixed'](0x1)}};"
            b"export{u as default};"
        ),
        (
            b"const params={"
            b"PARAM_0:{'text':'parameters.0'},"
            b"PARAM_1:{'text':'parameters.1'},"
            b"PARAM_2:{'options':{0:'a',1:'b'}},"
            b"PARAM_3:{'text':'parameters.3'},"
            b"PARAM_4:{'text':'parameters.4'}};"
            b"const units={"
            b"0x270e:{'options':{'BoilerState[\\'STOP\\']':'units.9998.0','BoilerState[\\'STANDBY\\']':'units.9998.4'}},"
            b"0x270a:{'options':{0x0:'units.9994.0',0x1:'units.9994.1'}}};"
            b"export{params,units};"
        ),
        (
            b"define_AppContainer_default$6={'translations':["
            b"{'id':'PL','flag':'pl'},{'id':'EN','flag':'en'}],'defaultTranslation':'pl'};"
            b"const _u={0x9:{'text':'units.1'},0x31:{'text':'units.31'}};"
        ),
    ],
)
def test_units_pure_matches_treesitter_fixtures(js: bytes) -> None:
    """Units table: pure path matches tree-sitter after callable normalization."""
    catalog = _catalog()
    _assert_parity(
        catalog._parse_units_descriptor_table_from_index(js),
        catalog._parse_units_descriptor_table_from_index_treesitter(js),
        label="units",
    )


@pytest.mark.parametrize(
    "js",
    [
        b"""
        const cfg = {
          translations: [
            {id: "pl", flag: "PL", extra: {ok: true}, n: 1, f: 2.5, on: true, off: false, z: null},
            {id: "en", flag: "EN", tags: ["a", "b"]}
          ],
          defaultTranslation: "pl"
        };
        """,
        (
            b"define_AppContainer_default$6={'translations':["
            b"{'id':'PL','flag':'pl','variants':{'153':{'1201':'PL_5_RTP_TIS'}}},"
            b"{'id':'EN','flag':'en'}],'defaultTranslation':'pl'};"
        ),
    ],
)
def test_language_config_pure_matches_treesitter_fixtures(js: bytes) -> None:
    """Language config: pure TranslationConfig equals tree-sitter oracle."""
    catalog = _catalog()
    pure = catalog._parse_language_config_from_js(js)
    treesitter = catalog._parse_language_config_from_js_treesitter(js)
    assert isinstance(pure, TranslationConfig)
    assert isinstance(treesitter, TranslationConfig)
    assert pure.default_translation == treesitter.default_translation
    _assert_parity(pure.translations, treesitter.translations, label="language")


@pytest.mark.skipif(not _I18N_ASSETS, reason="no captured i18n assets")
@pytest.mark.parametrize("path", _I18N_ASSETS, ids=lambda p: p.name)
def test_i18n_pure_matches_treesitter_captured(path: Path) -> None:
    """Captured i18n chunks: pure ≡ tree-sitter."""
    catalog = _catalog()
    code = path.read_bytes()
    _assert_parity(
        catalog._parse_i18n_from_js(code),
        catalog._parse_i18n_from_js_treesitter(code),
        label=path.name,
    )


@pytest.mark.skipif(not _INDEX_ASSETS, reason="no captured index assets")
@pytest.mark.parametrize("path", _INDEX_ASSETS, ids=lambda p: p.name)
def test_index_units_and_language_pure_matches_treesitter_captured(path: Path) -> None:
    """Captured index: units table + language config pure ≡ tree-sitter."""
    catalog = _catalog()
    code = path.read_bytes()
    _assert_parity(
        catalog._parse_units_descriptor_table_from_index(code),
        catalog._parse_units_descriptor_table_from_index_treesitter(code),
        label=f"units:{path.name}",
    )
    pure_cfg: TranslationConfig | None
    ts_cfg: TranslationConfig | None
    try:
        pure_cfg = catalog._parse_language_config_from_js(code)
    except ValueError:
        pure_cfg = None
    try:
        ts_cfg = catalog._parse_language_config_from_js_treesitter(code)
    except ValueError:
        ts_cfg = None
    if pure_cfg is None and ts_cfg is None:
        return
    assert pure_cfg is not None and ts_cfg is not None
    assert pure_cfg.default_translation == ts_cfg.default_translation
    _assert_parity(pure_cfg.translations, ts_cfg.translations, label=f"lang:{path.name}")
