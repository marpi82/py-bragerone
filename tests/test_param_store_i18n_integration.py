"""Integration test for ParamStore with i18n functionality."""

import pytest

from typing import TYPE_CHECKING

from pybragerone.models.catalog import LiveAssetsCatalog
from pybragerone.models.param import ParamStore

if TYPE_CHECKING:
    from pybragerone.api import BragerOneApiClient


class MockApiClient:
    """Mock API client for integration testing."""

    def __init__(self) -> None:
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
            "../../resources/languages/pl/parameters.json": () => d(() => import("./parameters-PL123.js"), []).then(e => e.default),
            "../../resources/languages/en/parameters.json": () => d(() => import("./parameters-EN456.js"), []).then(e => e.default),
            "../../resources/languages/pl/units.json": () => d(() => import("./units-PL789.js"), []).then(e => e.default),
            "../../resources/languages/en/units.json": () => d(() => import("./units-EN101.js"), []).then(e => e.default)
        };
        """

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
        if "index-" in url:
            return self.index_content.encode("utf-8")

        filename = url.split("/")[-1]
        if filename in self.i18n_files:
            return self.i18n_files[filename].encode("utf-8")

        return b"export default {};"


@pytest.mark.asyncio
class TestParamStoreI18nIntegration:
    """Test integration between ParamStore and i18n system."""

    async def test_param_store_with_i18n(self) -> None:
        """Test ParamStore using i18n translations."""
        client: BragerOneApiClient = MockApiClient()  # type: ignore

        # Create ParamStore with i18n support
        param_store = ParamStore()
        param_store.init_with_api(client)

        # Initialize assets (normally done by refresh_index)
        if param_store._assets:
            await param_store._assets.refresh_index("http://example.com/index-main.js")

        # Add some test parameters
        param_store.upsert("P4.v1", 23.5)  # Temperature value
        param_store.upsert("P4.u1", 1)  # Unit code for °C
        param_store.upsert("P6.v2", 2.8)  # Pressure value
        param_store.upsert("P6.u2", 2)  # Unit code for bar

        # Test Polish translations
        pl_params = await param_store.get_i18n_parameters(lang="pl")
        assert "TEMP_SENSOR_1" in pl_params
        assert pl_params["TEMP_SENSOR_1"] == "Czujnik temperatury 1"
        assert pl_params["PRESSURE_VALVE"] == "Zawór ciśnieniowy"

        pl_units = await param_store.get_i18n_units(lang="pl")
        assert pl_units["1"] == "°C"
        assert pl_units["2"] == "bar"

        # Test English translations
        en_params = await param_store.get_i18n_parameters(lang="en")
        assert en_params["TEMP_SENSOR_1"] == "Temperature sensor 1"
        assert en_params["PRESSURE_VALVE"] == "Pressure valve"

        en_units = await param_store.get_i18n_units(lang="en")
        assert en_units["1"] == "°C"
        assert en_units["2"] == "bar"

    async def test_param_store_resolve_labels_and_units(self) -> None:
        """Test resolving parameter labels and units through i18n."""
        client: BragerOneApiClient = MockApiClient()  # type: ignore

        param_store = ParamStore()
        param_store.init_with_api(client)

        # Initialize assets
        if param_store._assets:
            await param_store._assets.refresh_index("http://example.com/index-main.js")

        # Add parameter with unit
        param_store.upsert("P4.v1", 25.0)  # Temperature
        param_store.upsert("P4.u1", 1)  # °C unit code

        # Test label resolution
        label = await param_store.resolve_label("TEMP_SENSOR_1")
        assert label == "Czujnik temperatury 1"  # Polish default

        # Test unit resolution
        unit = await param_store.resolve_unit(1)  # °C
        assert unit == "°C"

        unit = await param_store.resolve_unit(2)  # bar
        assert unit == "bar"

        # Test unknown unit
        unit = await param_store.resolve_unit(999)
        assert unit is None

    async def test_language_config_integration(self) -> None:
        """Test that ParamStore correctly detects available languages."""
        client: BragerOneApiClient = MockApiClient()  # type: ignore

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
        """Test ParamStore language detection and fallback."""
        client: BragerOneApiClient = MockApiClient()  # type: ignore

        param_store = ParamStore()
        param_store.init_with_api(client)

        # Initialize assets
        if param_store._assets:
            await param_store._assets.refresh_index("http://example.com/index-main.js")

        # Should auto-detect Polish as default language
        default_lang = await param_store._ensure_lang()
        assert default_lang == "pl"

        # Test manual language override
        en_params = await param_store.get_i18n_parameters(lang="en")
        assert en_params["TEMP_SENSOR_1"] == "Temperature sensor 1"
