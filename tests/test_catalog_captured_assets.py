"""Parse-only regression over captured BragerOne JS assets in ``tests/assets/``.

These tests feed dumped ``*.js`` bytes into tree-sitter helpers. They do **not**
authenticate, fetch ``one.brager.pl``, resolve live menus, or attach permissions.
Missing dumps skip; a helper that returns nothing fails so an upstream bundle
shape change is visible.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pybragerone.models.catalog import LiveAssetsCatalog

_ASSETS_ROOT = Path(__file__).resolve().parent / "assets"
_HASHED_JS = re.compile(r"^(.+)-([A-Za-z0-9_-]+)\.js$", re.IGNORECASE)


class _DummyApi:
    """API stub that must never hit the network during captured-asset tests."""

    one_base = "https://one.brager.pl"

    async def get_bytes(self, url: str) -> bytes:
        """Refuse network fetches; captured tests parse local files only."""
        raise AssertionError(f"captured-asset tests must not fetch {url}")


def _js_files(subdir: str) -> list[Path]:
    """List ``*.js`` dumps in ``tests/assets/<subdir>``."""
    folder = _ASSETS_ROOT / subdir
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".js")


def _paths_or_skip(subdir: str) -> list[Path | None]:
    """Return captured JS paths, or ``[None]`` so pytest still collects a skip."""
    files: list[Path | None] = list(_js_files(subdir))
    return files or [None]


def _skip_if_missing(path: Path | None, subdir: str) -> Path:
    """Skip the test when the dump directory has no JS files."""
    if path is None:
        pytest.skip(f"Drop captured *.js files into tests/assets/{subdir}")
    return path


def _token_from_filename(path: Path) -> str:
    """Derive the catalog token from a hashed ``BASENAME-<hash>.js`` filename."""
    match = _HASHED_JS.match(path.name)
    if match:
        return match.group(1).rsplit("/", 1)[-1]
    return path.stem


def _catalog() -> LiveAssetsCatalog:
    """Build a catalog whose API stub must never fetch the network."""
    return LiveAssetsCatalog(_DummyApi())  # type: ignore[arg-type]


@pytest.mark.captured_assets
@pytest.mark.parametrize("captured_index_path", _paths_or_skip("index"), ids=lambda p: p.name if p else "no-assets")
def test_captured_index_parses(captured_index_path: Path | None) -> None:
    """Parse dumped ``index-*.js`` into basenames / menu map / language config."""
    path = _skip_if_missing(captured_index_path, "index")
    catalog = _catalog()
    index = catalog._build_asset_index_from_index_js(
        f"https://one.brager.pl/assets/{path.name}",
        path.read_bytes(),
    )
    language_ok = False
    try:
        language = catalog._parse_language_config_from_js(index.index_bytes)
        language_ok = bool(language.translations)
    except Exception:
        language_ok = False
    assert index.assets_by_basename or index.menu_map or language_ok, (
        f"{path.name}: index parsed empty (no assets, menus, or language config)"
    )


@pytest.mark.captured_assets
@pytest.mark.parametrize("captured_param_path", _paths_or_skip("params"), ids=lambda p: p.name if p else "no-assets")
def test_captured_param_map_parses(captured_param_path: Path | None) -> None:
    """Parse dumped parameter-map modules (``PARAM_*``, ``STATUS_*``, …)."""
    path = _skip_if_missing(captured_param_path, "params")
    token = _token_from_filename(path)
    catalog = _catalog()
    param_map = catalog._parse_param_map_from_js(path.read_bytes(), token, origin=f"captured:{path.name}")
    assert param_map is not None, f"{path.name}: param-map parser returned None (token={token})"
    has_paths = any(param_map.paths.get(name) for name in ("value", "unit", "status", "command", "min", "max"))
    assert param_map.group or has_paths or param_map.units is not None, f"{path.name}: param-map has no group/paths/units"


@pytest.mark.captured_assets
@pytest.mark.parametrize("captured_menu_path", _paths_or_skip("menus"), ids=lambda p: p.name if p else "no-assets")
def test_captured_menu_js_parses(captured_menu_path: Path | None) -> None:
    """Parse dumped ``module.menu-*.js`` into raw route dicts (no permission/i18n resolve)."""
    path = _skip_if_missing(captured_menu_path, "menus")
    catalog = _catalog()
    routes = catalog._parse_menu_routes(path.read_bytes())
    assert isinstance(routes, list)
    assert routes, f"{path.name}: menu JS parsed to zero routes (export shape changed?)"


@pytest.mark.captured_assets
@pytest.mark.parametrize("captured_i18n_path", _paths_or_skip("i18n"), ids=lambda p: p.name if p else "no-assets")
def test_captured_i18n_parses(captured_i18n_path: Path | None) -> None:
    """Parse dumped language modules (``parameters-*.js``, ``units-*.js``, …)."""
    path = _skip_if_missing(captured_i18n_path, "i18n")
    catalog = _catalog()
    translations = catalog._parse_i18n_from_js(path.read_bytes())
    assert isinstance(translations, dict)
    assert translations, f"{path.name}: i18n parser returned an empty object"
