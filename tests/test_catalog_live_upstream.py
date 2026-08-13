"""Live, unauthenticated catalog checks (opt-in with ``pytest --run-live``)."""

from __future__ import annotations

import pytest

from pybragerone import BragerOneApiClient
from pybragerone.models.catalog import INDEX_ASSET_RE, LiveAssetsCatalog


@pytest.mark.needs_internet
async def test_live_system_version_and_index_parse() -> None:
    """Public version + homepage index must parse without login."""
    client = BragerOneApiClient(validate_on_start=False)
    try:
        version = await client.get_system_version()
        assert version.version

        catalog = LiveAssetsCatalog(client)
        await catalog._auto_discover_and_load_index()
        index_url = catalog._last_index_url or ""
        assert INDEX_ASSET_RE.search(index_url) or (catalog._idx.index_bytes and catalog._idx.assets_by_basename)
        assert catalog._idx.assets_by_basename, "live index parsed to zero asset basenames"
    finally:
        await client.close()
