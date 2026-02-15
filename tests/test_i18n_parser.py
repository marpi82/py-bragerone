"""Test i18n language file parsing and loading."""

import pytest

from pybragerone.models.catalog import LiveAssetsCatalog


class MockApiClient:
    """Mock API client for testing i18n functionality."""

    def __init__(self, index_content: str, i18n_files: dict[str, str] | None = None):
        """Initialize mock API client with index content and i18n files."""
        self.index_content = index_content
        self.i18n_files = i18n_files or {}

    async def get_bytes(self, url: str) -> bytes:
        """Fetch content for the given URL."""
        if "index-" in url:
            return self.index_content.encode("utf-8")

        # Extract filename from URL for i18n files
        filename = url.split("/")[-1]
        if filename in self.i18n_files:
            return self.i18n_files[filename].encode("utf-8")

        # Default: return empty export
        return b"export default {};"


@pytest.mark.asyncio
class TestI18nParser:
    """Test i18n language file parsing functionality."""

    async def test_basic_i18n_loading(self) -> None:
        """Test basic i18n file loading and parsing."""
        # Index content with i18n imports
        index_content = """
        // Some other stuff
        var assets = {
            "../../resources/languages/pl/parameters.json": () => d(() => import("./parameters-ABC123.js"), []).then(e => e.default),
            "../../resources/languages/en/parameters.json": () => d(() => import("./parameters-XYZ789.js"), []).then(e => e.default)
        };
        """  # noqa: E501

        # Mock i18n file content
        i18n_files = {
            "parameters-ABC123.js": 'export default { "TEMP_SENSOR": "Czujnik temperatury", "PRESSURE_VALVE": "Zawór ciśnieniowy" };',  # noqa: E501
            "parameters-XYZ789.js": 'export default { "TEMP_SENSOR": "Temperature sensor", "PRESSURE_VALVE": "Pressure valve" };',
        }

        client = MockApiClient(index_content, i18n_files)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("http://example.com/index-main.js")

        # Test Polish translations
        pl_params = await catalog.get_i18n("pl", "parameters")
        assert pl_params["TEMP_SENSOR"] == "Czujnik temperatury"
        assert pl_params["PRESSURE_VALVE"] == "Zawór ciśnieniowy"

        # Test English translations
        en_params = await catalog.get_i18n("en", "parameters")
        assert en_params["TEMP_SENSOR"] == "Temperature sensor"
        assert en_params["PRESSURE_VALVE"] == "Pressure valve"

    async def test_i18n_not_found(self) -> None:
        """Test behavior when i18n file is not found."""
        index_content = """
        var assets = {
            "../../resources/languages/pl/parameters.json": () => d(() => import("./parameters-ABC123.js"), [])
        };
        """

        client = MockApiClient(index_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("http://example.com/index-main.js")

        # Test non-existent language
        result = await catalog.get_i18n("de", "parameters")
        assert result == {}

        # Test non-existent namespace
        result = await catalog.get_i18n("pl", "nonexistent")
        assert result == {}

    async def test_i18n_complex_structure(self) -> None:
        """Test i18n with nested objects and various data types."""
        index_content = """
        var assets = {
            "../../resources/languages/en/units.json": () => d(() => import("./units-HASH123.js"), []).then(e => e.default)
        };
        """

        i18n_files = {
            "units-HASH123.js": """export default {
                "temperature": {
                    "celsius": "°C",
                    "fahrenheit": "°F"
                },
                "pressure": {
                    "bar": "bar",
                    "psi": "psi"
                },
                "time_units": {
                    "seconds": "s",
                    "minutes": "min",
                    "hours": "h"
                },
                "boolean_values": {
                    "true": "Yes",
                    "false": "No"
                }
            };"""
        }

        client = MockApiClient(index_content, i18n_files)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("http://example.com/index-main.js")

        units = await catalog.get_i18n("en", "units")

        # Test nested structure
        assert units["temperature"]["celsius"] == "°C"
        assert units["temperature"]["fahrenheit"] == "°F"
        assert units["pressure"]["bar"] == "bar"
        assert units["time_units"]["hours"] == "h"
        assert units["boolean_values"]["true"] == "Yes"

    async def test_i18n_malformed_javascript(self) -> None:
        """Test handling of malformed JavaScript in i18n files."""
        index_content = """
        var assets = {
            "../../resources/languages/pl/broken.json": () => d(() => import("./broken-ABC123.js"), [])
        };
        """

        i18n_files = {
            "broken-ABC123.js": "export default {[};"  # Invalid bracket sequence
        }

        client = MockApiClient(index_content, i18n_files)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("http://example.com/index-main.js")

        # Should return empty dict for malformed JS
        result = await catalog.get_i18n("pl", "broken")
        assert result == {}

    async def test_i18n_various_import_formats(self) -> None:
        """Test different formats of import declarations in index."""
        index_content = """
        var assets = {
            // Different quote styles
            "../../resources/languages/pl/app.json": () => d(() => import('./app-HASH1.js'), []).then(e => e.default),
            '../../resources/languages/en/app.json': () => d(() => import("./app-HASH2.js"), []).then(e => e.default),

            // Different spacing
            "../../resources/languages/cz/units.json":()=>d(()=>import("./units-HASH3.js"),[]).then(e=>e.default),

            // With extra parameters
            "../../resources/languages/de/params.json": () => d(() => import("./params-HASH4.js"), ["dep"]).then(e => e.default)
        };
        """

        i18n_files = {
            "app-HASH1.js": 'export default { "welcome": "Witamy" };',
            "app-HASH2.js": 'export default { "welcome": "Welcome" };',
            "units-HASH3.js": 'export default { "meter": "m" };',
            "params-HASH4.js": 'export default { "param1": "Parameter 1" };',
        }

        client = MockApiClient(index_content, i18n_files)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("http://example.com/index-main.js")

        # Test all variations work
        assert await catalog.get_i18n("pl", "app") == {"welcome": "Witamy"}
        assert await catalog.get_i18n("en", "app") == {"welcome": "Welcome"}
        assert await catalog.get_i18n("cz", "units") == {"meter": "m"}
        assert await catalog.get_i18n("de", "params") == {"param1": "Parameter 1"}

    async def test_i18n_namespace_is_case_insensitive(self) -> None:
        """Ensure i18n namespace lookup works for camelCase bundles like `diodeState.json`."""
        index_content = """
        var assets = {
            "../../resources/languages/pl/diodeState.json": () => d(() => import("./diodeState-H1.js"), []).then(e => e.default)
        };
        """

        i18n_files = {
            "diodeState-H1.js": 'export default { "on": "Włączony", "off_manual": "Wyłączony (ręcznie)" };',
        }

        client = MockApiClient(index_content, i18n_files)
        catalog = LiveAssetsCatalog(client)  # type: ignore
        await catalog.refresh_index("http://example.com/index-main.js")

        # Requesting the namespace in different casings should work.
        assert await catalog.get_i18n("pl", "diodestate") == {"on": "Włączony", "off_manual": "Wyłączony (ręcznie)"}
        assert await catalog.get_i18n("pl", "diodeState") == {"on": "Włączony", "off_manual": "Wyłączony (ręcznie)"}

    async def test_i18n_unicode_content(self) -> None:
        """Test i18n files with Unicode content."""
        index_content = """
        var assets = {
            "../../resources/languages/pl/messages.json": () => d(() => import("./messages-UNI123.js"), [])
        };
        """

        i18n_files = {
            "messages-UNI123.js": """export default {
                "greeting": "Cześć! 👋",
                "symbols": "°C, ±, ≤, ≥, ≠",
                "polish_chars": "ąćęłńóśźż",
                "unicode_test": "测试 тест ทดสอบ"
            };"""
        }

        client = MockApiClient(index_content, i18n_files)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("http://example.com/index-main.js")

        messages = await catalog.get_i18n("pl", "messages")

        assert "👋" in messages["greeting"]
        assert "±" in messages["symbols"]
        assert "ąćę" in messages["polish_chars"]
        assert "测试" in messages["unicode_test"]

    async def test_index_units_descriptor_table_is_available_by_raw_code(self) -> None:
        """Index-defined units descriptor table should be parsed and exposed by raw unit code."""
        index_content = """
        const QO = {
            2: { text: "units.2" },
            3: { text: "units.3" },
            49: { text: "units.31", value: e => Number((e * .1).toFixed(1)), valuePrepare: e => e / .1 },
            8: { options: { 22: "units.8.22" } }
        };
        export default {};
        """

        client = MockApiClient(index_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore[arg-type]
        await catalog.refresh_index("http://example.com/index-main.js")

        desc_49 = await catalog.get_unit_descriptor(49)
        assert isinstance(desc_49, dict)
        assert desc_49.get("text") == "units.31"
        assert isinstance(desc_49.get("value"), str)

        desc_8 = await catalog.get_unit_descriptor("8")
        assert isinstance(desc_8, dict)
        assert isinstance(desc_8.get("options"), dict)
        assert desc_8["options"]["22"] == "units.8.22"
