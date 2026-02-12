"""Tests for ParamMap parsing and resolution.

These tests focus on "param map" assets used for mapping symbolic parameter tokens
(e.g. ``PARAM_66``) to concrete pool/channel/index paths and metadata.

They complement existing tests that cover i18n parsing and menu parsing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pybragerone.models.catalog import AssetRef, LiveAssetsCatalog


@pytest.mark.asyncio
async def test_param_map_resolves_from_dedicated_asset_file() -> None:
    """Resolve a ParamMap from a dedicated asset file named <TOKEN>-<hash>.js."""
    token = "PARAM_66"
    asset_url = "https://example.com/assets/PARAM_66-ABC123.js"

    # Minimal but representative param map shape.
    js = """
    export default {
      group: "P4",
      componentType: "slider",
      units: 1,
      limits: { min: 10, max: 90 },
      statusFlags: [{ bit: 3, label: "pump" }],
      use: {
        v: { pool: "P4", chan: "v", idx: 1 },
        u: { pool: "P4", chan: "u", idx: 1 },
        s: [{ pool: "P5", chan: "s", idx: 40 }],
        n: { pool: "P4", chan: "n", idx: 1 },
        x: { pool: "P4", chan: "x", idx: 1 }
      }
    };
    """

    mock_api = AsyncMock()

    async def get_bytes(url: str) -> bytes:
        if url == asset_url:
            return js.encode("utf-8")
        return b""

    mock_api.get_bytes.side_effect = get_bytes

    catalog = LiveAssetsCatalog(mock_api)

    # Avoid refresh_index(): wire the catalog index directly.
    catalog._idx.assets_by_basename[token] = [AssetRef(url=asset_url, base=token, hash="ABC123")]

    result = await catalog.get_param_mapping([token])

    assert token in result
    pm = result[token]

    assert pm.key == token
    assert pm.group == "P4"
    assert pm.component_type == "slider"
    assert pm.units == 1
    assert pm.limits == {"min": 10, "max": 90}
    assert pm.status_flags and pm.status_flags[0]["bit"] == 3

    # Paths should be normalized into lists.
    assert pm.paths["value"] and pm.paths["value"][0]["pool"] == "P4"
    assert pm.paths["unit"] and pm.paths["unit"][0]["chan"] == "u"
    assert pm.paths["status"] and pm.paths["status"][0]["pool"] == "P5"
    assert pm.paths["min"] and pm.paths["min"][0]["chan"] == "n"
    assert pm.paths["max"] and pm.paths["max"][0]["chan"] == "x"


@pytest.mark.asyncio
async def test_param_map_inline_fallback_from_index_candidate() -> None:
    """Resolve a ParamMap using the inline index fallback.

    The inline fallback is used only when:
    - exactly one token is unresolved via file assets
    - the index contains exactly one inline param-map candidate
    """
    token = "PARAM_INLINE"

    # This is intentionally just an object literal; the parser falls back to the
    # largest object in the AST when an explicit export is missing.
    inline_obj = (
        b"{"
        b" group: 'P6',"
        b" componentType: 'select',"
        b" units: 2,"
        b" use: { v: { pool: 'P6', chan: 'v', idx: 2 }, u: { pool: 'P6', chan: 'u', idx: 2 } }"
        b"}"
    )

    prefix = b"/* prefix */\n"
    suffix = b"\n/* suffix */"
    index_bytes = prefix + inline_obj + suffix

    mock_api = AsyncMock()
    catalog = LiveAssetsCatalog(mock_api)

    # Ensure get_param_mapping() does not try to auto-load index via HTTP.
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/dummy.js", base="dummy", hash="x")]

    start = len(prefix)
    end = start + len(inline_obj)
    catalog._idx.index_bytes = index_bytes
    catalog._idx.inline_param_candidates = [(start, end)]

    result = await catalog.get_param_mapping([token])

    assert token in result
    pm = result[token]

    assert pm.origin == "inline:index"
    assert pm.group == "P6"
    assert pm.component_type == "select"
    assert pm.units == 2
    assert pm.paths["value"][0]["pool"] == "P6"
    assert pm.paths["unit"][0]["idx"] == 2
