"""Integration tests for asset-driven i18n.

These tests validate that `LiveAssetsCatalog` and `I18nResolver` work together
to provide language selection and translation/unit lookup.
"""

from typing import cast

import pytest

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import LiveAssetsCatalog
from pybragerone.models.i18n import I18nResolver


class MockApiClient:
    """Mock API client for integration testing."""

    def __init__(self) -> None:
        """Initialize the mock API client with test data."""
        # Index with language config and i18n assets
        self.index_content = """
        var HL = {
            translations: [
                { id: 'pl', flag: 'pl', name: 'Polski' },
                { id: 'en', flag: 'gb', name: 'English' }
            ],
            defaultTranslation: 'pl'
        };

        var assets = {
            "../../resources/languages/pl/parameters.json": () => d(() => import("./parameters-PL123.js"), []).then(e => e.default),  // noqa: E501
            "../../resources/languages/en/parameters.json": () => d(() => import("./parameters-EN456.js"), []).then(e => e.default),  // noqa: E501
            "../../resources/languages/pl/units.json": () => d(() => import("./units-PL789.js"), []).then(e => e.default),
            "../../resources/languages/en/units.json": () => d(() => import("./units-EN101.js"), []).then(e => e.default)
        };
        """  # noqa: E501

        # I18n translation files
        self.i18n_files = {
            # Polish translations
            "parameters-PL123.js": """export default {
                "TEMP_SENSOR_1": "Czujnik temperatury 1",
                "PRESSURE_VALVE": "Zawór ciśnieniowy",
                "PUMP_STATUS": "Status pompy"
            };""",
            "units-PL789.js": """export default {
                "1": "°C",
                "2": "bar",
                "3": "l/min"
            };""",
            # English translations
            "parameters-EN456.js": """export default {
                "TEMP_SENSOR_1": "Temperature sensor 1",
                "PRESSURE_VALVE": "Pressure valve",
                "PUMP_STATUS": "Pump status"
            };""",
            "units-EN101.js": """export default {
                "1": "°C",
                "2": "bar",
                "3": "l/min"
            };""",
        }

    async def get_bytes(self, url: str) -> bytes:
        """Return bytes for the requested URL."""
        if "index-" in url:
            return self.index_content.encode("utf-8")

        filename = url.split("/")[-1]
        if filename in self.i18n_files:
            return self.i18n_files[filename].encode("utf-8")

        return b"export default {};"


@pytest.mark.asyncio
class TestI18nIntegration:
    """Test integration between LiveAssetsCatalog and I18nResolver."""

    async def test_i18n_namespaces_fetch(self) -> None:
        """Fetch i18n namespaces in two languages."""
        client = cast(BragerOneApiClient, MockApiClient())

        catalog = LiveAssetsCatalog(client)
        await catalog.refresh_index("http://example.com/index-main.js")

        resolver = I18nResolver(catalog)

        # Test Polish translations
        pl_params = await resolver.get_namespace("parameters", lang="pl")
        assert "TEMP_SENSOR_1" in pl_params
        assert pl_params["TEMP_SENSOR_1"] == "Czujnik temperatury 1"
        assert pl_params["PRESSURE_VALVE"] == "Zawór ciśnieniowy"

        pl_units = await resolver.get_namespace("units", lang="pl")
        assert pl_units["1"] == "°C"
        assert pl_units["2"] == "bar"

        # Test English translations
        en_params = await resolver.get_namespace("parameters", lang="en")
        assert en_params["TEMP_SENSOR_1"] == "Temperature sensor 1"
        assert en_params["PRESSURE_VALVE"] == "Pressure valve"

        en_units = await resolver.get_namespace("units", lang="en")
        assert en_units["1"] == "°C"
        assert en_units["2"] == "bar"

    async def test_i18n_resolve_label_and_units(self) -> None:
        """Resolve parameter label and unit values."""
        client = cast(BragerOneApiClient, MockApiClient())

        catalog = LiveAssetsCatalog(client)
        await catalog.refresh_index("http://example.com/index-main.js")

        resolver = I18nResolver(catalog)

        # Should auto-detect Polish as default language
        default_lang = await resolver.ensure_lang()
        assert default_lang == "pl"

        # Test label resolution
        label = await resolver.resolve_param_label("TEMP_SENSOR_1")
        assert label == "Czujnik temperatury 1"  # Polish default

        # Test unit resolution
        unit = await resolver.resolve_unit(1)  # °C
        assert unit == "°C"

        unit = await resolver.resolve_unit(2)  # bar
        assert unit == "bar"

        # Test unknown unit
        unit = await resolver.resolve_unit(999)
        assert unit is None

    async def test_language_config_integration(self) -> None:
        """Test that the catalog correctly detects available languages."""
        client = cast(BragerOneApiClient, MockApiClient())

        # Test through LiveAssetsCatalog directly
        catalog = LiveAssetsCatalog(client)
        await catalog.refresh_index("http://example.com/index-main.js")

        # Get available language configuration
        lang_config = await catalog.list_language_config()
        assert lang_config is not None
        assert lang_config.default_translation == "pl"
        assert len(lang_config.translations) == 2

        # Check language details
        lang_ids = [t["id"] for t in lang_config.translations]
        assert "pl" in lang_ids
        assert "en" in lang_ids

    async def test_param_store_language_fallback(self) -> None:
        """Test default language detection and manual override."""
        client = cast(BragerOneApiClient, MockApiClient())

        catalog = LiveAssetsCatalog(client)
        await catalog.refresh_index("http://example.com/index-main.js")

        resolver = I18nResolver(catalog)

        assert await resolver.ensure_lang() == "pl"

        # Manual language override for a single lookup
        en_params = await resolver.get_namespace("parameters", lang="en")
        assert en_params["TEMP_SENSOR_1"] == "Temperature sensor 1"
