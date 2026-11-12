"""Regression tests for inline param-map object span scanning."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import LiveAssetsCatalog, _find_inline_param_object_spans


def _catalog() -> LiveAssetsCatalog:
    return LiveAssetsCatalog(cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient)))


def test_find_inline_param_object_spans_skips_small_objects() -> None:
    """Objects shorter than 200 bytes are ignored."""
    small = b"const x = {'group': 1};"
    assert _find_inline_param_object_spans(small) == []


def test_find_inline_param_object_spans_finds_large_param_like_object() -> None:
    """Large literals containing param-map keys become candidate spans."""
    inner = b'"group":"P1","pool":' + b"x" * 220
    js = b"{" + inner + b"}"
    spans = _find_inline_param_object_spans(js)
    assert len(spans) == 1
    start, end = spans[0]
    assert js[start:end].startswith(b"{")


def test_find_inline_param_object_spans_handles_escaped_quotes() -> None:
    """Escaped quotes inside strings do not break brace balancing."""
    payload = (b"{'group':'P1','label':'a\\\\\"big\"}',") + b"y" * 200 + b"}"
    spans = _find_inline_param_object_spans(b"prefix" + payload)
    assert spans


def test_build_asset_index_collects_inline_param_candidates() -> None:
    """Index builder wires inline param-map span detection."""
    catalog = _catalog()
    big = b"{'group':'P6'," + b"q" * 250 + b"}"
    index = b"//" + big
    assets = catalog._build_asset_index_from_index_js("https://ex/assets/index-x.js", index)
    assert assets.inline_param_candidates
