"""Atheris harness for the tree-sitter-based live-asset catalog parsers.

Feeds arbitrary bytes into the JavaScript asset parsing paths (index,
menu routes, embedded parameter maps) that normally process the vendor's
web-app bundles. These paths are expected to never raise on malformed
input — any exception reaches Atheris and is reported as a crash, i.e. a
resilience finding to fix in the parser (not to suppress here).

Run (optional, requires the ``fuzz`` dependency group)::

    uv run --group fuzz python fuzz/fuzz_catalog.py
"""

from __future__ import annotations

import sys
from typing import cast

import atheris

with atheris.instrument_imports():
    from pybragerone.api.client import BragerOneApiClient
    from pybragerone.models.catalog import LiveAssetsCatalog


def _catalog() -> LiveAssetsCatalog:
    """Build a catalog without a real API client (sync parse paths never touch it)."""
    return LiveAssetsCatalog(cast(BragerOneApiClient, None))


def TestOneInput(data: bytes) -> None:
    """Fuzz the JS asset parsers with arbitrary bytes."""
    catalog = _catalog()
    catalog._build_asset_index_from_index_js("https://example.invalid/index.js", data)
    catalog._parse_menu_routes(data)
    catalog._parse_index_token_raw_maps(data)
    catalog._extract_root_object_from_js(data)


def main() -> None:
    """Entry point for continuous / local Atheris runs."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
