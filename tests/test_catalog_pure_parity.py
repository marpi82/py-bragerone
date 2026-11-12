"""Pure-Python catalog parser regressions (former oracle fixtures)."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import cast

import pytest

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import LiveAssetsCatalog, TranslationConfig

_ASSETS = Path(__file__).resolve().parent / "assets"
_PARAMS_ASSETS = sorted((_ASSETS / "params").glob("*.js")) if (_ASSETS / "params").is_dir() else []
_I18N_ASSETS = sorted((_ASSETS / "i18n").glob("*.js")) if (_ASSETS / "i18n").is_dir() else []
_INDEX_ASSETS = sorted((_ASSETS / "index").glob("*.js")) if (_ASSETS / "index").is_dir() else []


class _DummyApi:
    one_base = "https://example.invalid"


def _catalog() -> LiveAssetsCatalog:
    return LiveAssetsCatalog(cast(BragerOneApiClient, _DummyApi()))


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
def test_i18n_parse_hand_fixtures(js: bytes) -> None:
    """Hand-written i18n modules parse to dicts."""
    catalog = _catalog()
    parsed = catalog._parse_i18n_from_js(js)
    assert isinstance(parsed, dict)


@pytest.mark.parametrize(
    "js",
    [
        (
            b"const u={0x9:{'options':{0x0:'units.17.0',0x1:'units.17.1'}},"
            b"0xa:{'text':'units.10','value':_0x201288=>_0x201288*0x6},"
            b"0x31:{'text':'units.31','value':_0x4fdb4d=>Number(_0x4fdb4d*0.1)['toFixed'](0x1)}};"
            b"export{u as default};"
        ),
    ],
)
def test_units_table_hand_fixtures(js: bytes) -> None:
    """Hex-keyed units tables normalize numeric keys."""
    catalog = _catalog()
    table = catalog._parse_units_descriptor_table_from_index(js)
    assert "9" in table


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
    ],
)
def test_language_config_hand_fixtures(js: bytes) -> None:
    """Language config objects become TranslationConfig."""
    catalog = _catalog()
    cfg = catalog._parse_language_config_from_js(js)
    assert isinstance(cfg, TranslationConfig)
    assert cfg.default_translation == "pl"


@pytest.mark.skipif(not _PARAMS_ASSETS, reason="no captured param assets")
@pytest.mark.parametrize("path", _PARAMS_ASSETS, ids=lambda p: p.name)
def test_param_root_object_captured(path: Path) -> None:
    """Captured param assets yield dict roots when parseable."""
    catalog = _catalog()
    code = path.read_bytes()
    root = catalog._extract_root_object_from_js(code)
    assert root is None or isinstance(root, dict)


@pytest.mark.skipif(not _I18N_ASSETS, reason="no captured i18n assets")
@pytest.mark.parametrize("path", _I18N_ASSETS, ids=lambda p: p.name)
def test_i18n_captured(path: Path) -> None:
    """Captured i18n assets parse without error."""
    catalog = _catalog()
    parsed = catalog._parse_i18n_from_js(path.read_bytes())
    assert isinstance(parsed, dict)


@pytest.mark.skipif(not _INDEX_ASSETS, reason="no captured index assets")
@pytest.mark.parametrize("path", _INDEX_ASSETS, ids=lambda p: p.name)
def test_index_units_and_language_captured(path: Path) -> None:
    """Captured index bytes exercise units and optional language config."""
    catalog = _catalog()
    code = path.read_bytes()
    assert isinstance(catalog._parse_units_descriptor_table_from_index(code), dict)
    with contextlib.suppress(ValueError):
        catalog._parse_language_config_from_js(code)
