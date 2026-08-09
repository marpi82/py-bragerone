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


# Reused across iterations: constructing a catalog rebuilds the tree-sitter
# parser, which would dominate the hot path. The fuzzed methods only read
# input bytes; the index-builder overwrites its state on every call.
_CATALOG = _catalog()


def TestOneInput(data: bytes) -> None:
    """Fuzz the JS asset parsers with arbitrary bytes."""
    _CATALOG._build_asset_index_from_index_js("https://example.invalid/index.js", data)
    _CATALOG._parse_menu_routes(data)
    _CATALOG._parse_index_token_raw_maps(data)
    _CATALOG._extract_root_object_from_js(data)


def main() -> None:
    """Entry point for continuous / local Atheris runs."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
