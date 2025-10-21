"""Test parser resilience to variable name changes and edge cases."""

import pytest

from pybragerone.models.catalog import LiveAssetsCatalog


class MockApiClient:
    """Mock API client for testing different JS patterns."""

    def __init__(self, js_content: str):
        """Initialize mock API with given JS content."""
        self.js_content = js_content

    async def get_bytes(self, url: str) -> bytes:
        """Return JS content as bytes."""
        return self.js_content.encode("utf-8")


@pytest.mark.asyncio
class TestParserResilience:
    """Test parser resilience to various JavaScript patterns and variable names."""

    async def test_var_assignment(self) -> None:
        """Test parser with var assignment."""
        js_content = """var HL = {
            translations: [
                { id: 'pl', flag: 'pl', name: 'Polski' },
                { id: 'en', flag: 'gb', name: 'English' },
                { id: 'cs', flag: 'cz', name: 'Čeština', dev: true }
            ],
            defaultTranslation: 'pl'
        };"""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert config.default_translation == "pl"
        assert len(config.translations) == 3

        # Check production vs development languages
        prod_langs = [t for t in config.translations if not t.get("dev", False)]
        dev_langs = [t for t in config.translations if t.get("dev", False)]

        assert len(prod_langs) == 2  # pl, en
        assert len(dev_langs) == 1  # cs

    async def test_const_assignment(self) -> None:
        """Test parser with const assignment."""
        js_content = """const CONFIG = {
            translations: [
                { id: 'pl', flag: 'pl' },
                { id: 'en', flag: 'gb' }
            ],
            defaultTranslation: 'pl'
        };"""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert config.default_translation == "pl"
        assert len(config.translations) == 2

    async def test_export_default(self) -> None:
        """Test parser with export default."""
        js_content = """export default {
            translations: [
                { id: 'pl', flag: 'pl' },
                { id: 'en', flag: 'gb' }
            ],
            defaultTranslation: 'pl'
        };"""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert config.default_translation == "pl"
        assert len(config.translations) == 2

    async def test_window_assignment(self) -> None:
        """Test parser with window property assignment."""
        js_content = """window.I18N_CFG = {
            translations: [
                { id: 'pl', flag: 'pl' },
                { id: 'en', flag: 'gb' }
            ],
            defaultTranslation: 'pl'
        };"""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert config.default_translation == "pl"
        assert len(config.translations) == 2

    async def test_minified_code(self) -> None:
        """Test parser with minified JavaScript."""
        js_content = "var a={translations:[{id:'pl',flag:'pl'},{id:'en',flag:'gb'}],defaultTranslation:'pl'},b=42;"

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert config.default_translation == "pl"
        assert len(config.translations) == 2

    async def test_nested_objects(self) -> None:
        """Test parser with nested object structures."""
        js_content = """window.app = {
            config: {
                translations: [
                    { id: 'pl', flag: 'pl' },
                    { id: 'en', flag: 'gb' }
                ],
                defaultTranslation: 'pl'
            }
        };"""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert config.default_translation == "pl"
        assert len(config.translations) == 2

    async def test_invalid_empty_file(self) -> None:
        """Test parser with empty file."""
        js_content = ""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is None

    async def test_invalid_syntax_error(self) -> None:
        """Test parser with syntax error."""
        js_content = "var x = {[}"

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is None

    async def test_invalid_no_language_config(self) -> None:
        """Test parser with no language configuration."""
        js_content = "var x = 42; var y = 'hello';"

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is None

    async def test_invalid_missing_translations(self) -> None:
        """Test parser with missing translations array."""
        js_content = "var HL = { defaultTranslation: 'pl' };"

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is None

    async def test_invalid_missing_default_translation(self) -> None:
        """Test parser with missing defaultTranslation."""
        js_content = "var HL = { translations: [] };"

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is None

    async def test_unicode_handling(self) -> None:
        """Test parser with Unicode characters."""
        js_content = """var HL = {
            translations: [
                { id: 'pl', flag: 'pl', name: 'Polski' },
                { id: 'cs', flag: 'cz', name: 'Čeština' },
                { id: 'ru', flag: 'ru', name: 'Русский' },
                { id: 'ja', flag: 'jp', name: '日本語' }
            ],
            defaultTranslation: 'pl'
        };"""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert len(config.translations) == 4

        # Verify Unicode names are preserved
        names = [t.get("name", "") for t in config.translations]
        assert "Čeština" in names
        assert "Русский" in names
        assert "日本語" in names

    async def test_boolean_types(self) -> None:
        """Test parser with different boolean values."""
        js_content = """var HL = {
            translations: [
                { id: 'pl', flag: 'pl' },
                { id: 'en', flag: 'gb', dev: false },
                { id: 'cs', flag: 'cz', dev: true }
            ],
            defaultTranslation: 'pl'
        };"""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert len(config.translations) == 3

    async def test_array_threshold(self) -> None:
        """Test that array validation threshold works correctly."""
        # 75% of objects have id+flag (should pass 70% threshold)
        js_content = """var HL = {
            translations: [
                { id: 'pl', flag: 'pl' },
                { id: 'en', flag: 'gb' },
                { id: 'de', flag: 'de' },
                { notId: 'invalid', notFlag: 'x' }
            ],
            defaultTranslation: 'pl'
        };"""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        # Should pass because 3/4 = 75% > 70% threshold
        assert config is not None
        assert len(config.translations) == 4

    async def test_realistic_bragerone_structure(self) -> None:
        """Test with structure similar to real BragerOne index files."""
        js_content = """
        // Some other code
        var otherVar = 42;

        var HL = {
            translations: [
                { id: "PL", flag: "pl", variants: { 2: "PL_GLOBAL_5_SKIEPKO" } },
                { id: "EN", flag: "en", countryFlag: "gb" },
                { id: "DE", flag: "de" },
                { id: "FR", flag: "fr" },
                { id: "CZ", flag: "cz" },
                { id: "NL", flag: "nl", dev: true },
                { id: "HU", flag: "hu", dev: true }
            ],
            defaultTranslation: "pl"
        };

        // More code
        function doSomething() {
            return HL.defaultTranslation;
        }
        """

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert config.default_translation == "pl"
        assert len(config.translations) == 7

        # Check production vs development separation
        prod_langs = [t for t in config.translations if not t.get("dev", False)]
        dev_langs = [t for t in config.translations if t.get("dev", False)]

        assert len(prod_langs) == 5  # PL, EN, DE, FR, CZ
        assert len(dev_langs) == 2  # NL, HU
