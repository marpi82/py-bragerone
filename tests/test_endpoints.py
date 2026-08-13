"""Tests for REST URL builders."""

from __future__ import annotations

from pybragerone.api.constants import API_BASE
from pybragerone.api.endpoints import module_url


def test_module_url_quotes_module_id() -> None:
    """Module IDs are path-encoded on the modules collection."""
    assert module_url("ABC 1") == f"{API_BASE}/modules/ABC%201"
    assert module_url("plain", api_base="https://example.test/v1") == "https://example.test/v1/modules/plain"
