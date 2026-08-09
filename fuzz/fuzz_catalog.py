"""Atheris harness for the tree-sitter-based live-asset catalog parsers.

Feeds arbitrary bytes into the JavaScript asset parsing paths (index,
menu routes, embedded parameter maps) that normally process the vendor's
web-app bundles. These paths are expected to degrade gracefully on
malformed input — anything other than the expected exceptions below is
reported by Atheris as a crash and considered a resilience finding.

Run (optional, requires the ``fuzz`` dependency group)::

    uv run --group fuzz python fuzz/fuzz_catalog.py
"""

from __future__ import annotations

import contextlib
import sys
from typing import cast

import atheris

with atheris.instrument_imports():
    from pybragerone.api.client import BragerOneApiClient
    from pybragerone.models.catalog import LiveAssetsCatalog

# Expected degradation only — unexpected errors must reach Atheris.
# RecursionError: deeply nested payloads hit the interpreter recursion limit;
# the parser's depth guards treat it as "unparseable", which is acceptable.
_EXPECTED = (ValueError, TypeError, AttributeError, RecursionError)


def _catalog() -> LiveAssetsCatalog:
    """Build a catalog without a real API client (sync parse paths never touch it)."""
    return LiveAssetsCatalog(cast(BragerOneApiClient, None))


def TestOneInput(data: bytes) -> None:
    """Fuzz the JS asset parsers with arbitrary bytes."""
    catalog = _catalog()

    with contextlib.suppress(*_EXPECTED):
        catalog._build_asset_index_from_index_js("https://example.invalid/index.js", data)

    with contextlib.suppress(*_EXPECTED):
        catalog._parse_menu_routes(data)

    with contextlib.suppress(*_EXPECTED):
        catalog._parse_index_token_raw_maps(data)

    with contextlib.suppress(*_EXPECTED):
        catalog._extract_root_object_from_js(data)


def main() -> None:
    """Entry point for continuous / local Atheris runs."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
