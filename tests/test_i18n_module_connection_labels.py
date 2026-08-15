"""Tests for SPA module connection i18n label resolution."""

from __future__ import annotations

from typing import Any

import pytest

from pybragerone.models.i18n import I18nResolver


class _FakeAssets:
    """Minimal assets stub returning a ``module`` i18n namespace."""

    def __init__(self, module: dict[str, Any]) -> None:
        """Store the fake module namespace."""
        self._module = module

    async def list_language_config(self) -> None:
        """No language config needed when lang is explicit."""
        return None

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        """Return the stubbed module namespace."""
        if namespace == "module":
            return dict(self._module)
        return {}


@pytest.mark.asyncio
async def test_resolve_module_connection_labels_flattens_spa_keys() -> None:
    """Labels mirror SPA ``module.serverConnection`` / ``module.connection.*`` keys."""
    assets = _FakeAssets(
        {
            "serverConnection": "Server connection status",
            "noConnection": "No connection with module",
            "connection": {
                "status": "Connection with module status",
                "connected": "Connected",
                "notConnected": "Disconnected",
                "index": "Connection with module",
            },
            "ignored": 123,
        }
    )
    # _FakeAssets only stubs the methods I18nResolver calls (not LiveAssetsCatalog).
    resolver = I18nResolver(assets, lang="en")  # type: ignore[arg-type]
    labels = await resolver.resolve_module_connection_labels()
    assert labels["serverConnection"] == "Server connection status"
    assert labels["connection.status"] == "Connection with module status"
    assert labels["connection.connected"] == "Connected"
    assert labels["connection.notConnected"] == "Disconnected"
    assert labels["connection.index"] == "Connection with module"
    assert "ignored" not in labels
