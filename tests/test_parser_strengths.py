"""Test cases that demonstrate parser's resilience strengths."""

import pytest

from pybragerone.models.catalog import LiveAssetsCatalog


class MockApiClient:
    """Mock API client for testing."""

    def __init__(self, js_content: str):
        """Initialize mock API with given JS content."""
        self.js_content = js_content

    async def get_bytes(self, url: str) -> bytes:
        """Return JS content as bytes."""
        return self.js_content.encode("utf-8")


@pytest.mark.asyncio
class TestParserStrengths:
    """Test cases that highlight parser's resilience strengths."""

    async def test_variable_name_independence_showcase(self) -> None:
        """Showcase: Parser works with ANY variable name - complete independence."""
        # Different variable names that would break the old HL-searching parser
        test_cases = [
            "var COMPLETELY_DIFFERENT_NAME",
            "const MINIFIED_XYZ",
            "let RANDOM_CONFIG_OBJECT",
            "var a",  # single letter minified
        ]

        for var_name in test_cases:
            js_content = f"""{var_name} = {{
                translations: [
                    {{ id: 'pl', flag: 'pl' }},
                    {{ id: 'en', flag: 'gb' }}
                ],
                defaultTranslation: 'pl'
            }};"""

            client = MockApiClient(js_content)
            catalog = LiveAssetsCatalog(client)  # type: ignore

            await catalog.refresh_index("index-main.js")
            config = await catalog.list_language_config()

            assert config is not None, f"Failed for variable: {var_name}"
            assert config.default_translation == "pl"
            assert len(config.translations) == 2

    async def test_minification_resilience_showcase(self) -> None:
        """Showcase: Parser handles minified code perfectly."""
        minified_examples = [
            # Extreme minification - single line, no spaces
            "var x={translations:[{id:'pl',flag:'pl'},{id:'en',flag:'gb'}],defaultTranslation:'pl'};",
            # Multiple vars on one line
            "var a=1,config={translations:[{id:'pl',flag:'pl'}],defaultTranslation:'pl'},z=9;",
            # Compressed with JavaScript boolean
            "const c={translations:[{id:'pl',flag:'pl'},{id:'dev',flag:'x',dev:!0}],defaultTranslation:'pl'};",
        ]

        for js_content in minified_examples:
            client = MockApiClient(js_content)
            catalog = LiveAssetsCatalog(client)  # type: ignore

            await catalog.refresh_index("index-main.js")
            config = await catalog.list_language_config()

            assert config is not None
            assert config.default_translation == "pl"

    async def test_structure_recognition_showcase(self) -> None:
        """Showcase: Parser recognizes structure pattern, not variable names."""
        # Same structure, completely different context and variable names
        js_content = """
        // Complex production-like code
        function initializeApplication() {
            var userSettings = { theme: 'dark' };
            var serverConfig = { timeout: 5000 };

            // Language configuration buried in the middle
            window.appLanguages = {
                translations: [
                    { id: 'PL', flag: 'pl', name: 'Polish', region: 'EU' },
                    { id: 'EN', flag: 'en', name: 'English', region: 'US' },
                    { id: 'DE', flag: 'de', name: 'German', region: 'EU' }
                ],
                defaultTranslation: 'pl',
                version: '2.0',
                lastUpdated: new Date()
            };

            var otherStuff = { irrelevant: true };
            return { userSettings, serverConfig };
        }

        // More unrelated code
        var API_ENDPOINTS = {
            users: '/api/users',
            auth: '/api/auth'
        };
        """

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert config.default_translation == "pl"
        assert len(config.translations) == 3

        # Verify it extracted the right data
        lang_ids = [t["id"] for t in config.translations]
        assert "PL" in lang_ids
        assert "EN" in lang_ids
        assert "DE" in lang_ids

    async def test_robustness_against_invalid_data_showcase(self) -> None:
        """Showcase: Parser correctly rejects malformed data."""
        invalid_cases = [
            # Wrong property names
            "var HL = { langs: [], default: 'pl' };",
            # Missing required properties
            "var HL = { translations: [] };",
            "var HL = { defaultTranslation: 'pl' };",
            # Wrong data types
            "var HL = { translations: 'not_array', defaultTranslation: 'pl' };",
            "var HL = { translations: [], defaultTranslation: 123 };",
            # Empty or malformed
            "",
            "var x = {[}",  # syntax error
        ]

        for js_content in invalid_cases:
            client = MockApiClient(js_content)
            catalog = LiveAssetsCatalog(client)  # type: ignore

            await catalog.refresh_index("index-main.js")
            config = await catalog.list_language_config()

            # Should correctly reject all invalid cases
            assert config is None, f"Should reject invalid case: {js_content[:50]}..."

    async def test_threshold_validation_showcase(self) -> None:
        """Showcase: Smart validation with 70% threshold for flexibility."""
        # Test case: 3 valid + 1 invalid = 75% > 70% threshold → should pass
        js_content = """var HL = {
            translations: [
                { id: 'pl', flag: 'pl' },           // ✅ valid
                { id: 'en', flag: 'gb' },           // ✅ valid
                { id: 'de', flag: 'de' },           // ✅ valid
                { notId: 'broken', notFlag: 'x' }   // ❌ invalid but only 25%
            ],
            defaultTranslation: 'pl'
        };"""

        client = MockApiClient(js_content)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        # Should pass because 75% valid > 70% threshold
        assert config is not None
        assert len(config.translations) == 4
        assert config.default_translation == "pl"

    async def test_production_ready_showcase(self) -> None:
        """Showcase: Handles production-like BragerOne structure perfectly."""
        production_like_js = """
        // Production BragerOne-style index file
        !function(e,t){"object"==typeof exports&&"undefined"!=typeof module?module.exports=t():"function"==typeof define&&define.amd?define(t):(e=e||self).MyApp=t()}(this,(function(){"use strict";

        var otherMinifiedStuff=function(){return 42};

        // Language configuration in production style
        var HL = {
            translations: [
                { id: "PL", flag: "pl", variants: { 2: "PL_GLOBAL_5_SKIEPKO" }, countryFlag: "pl" },
                { id: "EN", flag: "en", countryFlag: "gb", name: "English" },
                { id: "DE", flag: "de", countryFlag: "de", name: "Deutsch" },
                { id: "FR", flag: "fr", countryFlag: "fr", name: "Français" },
                { id: "CZ", flag: "cz", countryFlag: "cz", name: "Čeština" },
                { id: "NL", flag: "nl", dev: true, name: "Nederlands" },
                { id: "HU", flag: "hu", dev: true, name: "Magyar" },
                { id: "JP", flag: "jp", dev: true, name: "日本語" }
            ],
            defaultTranslation: "pl",
            supportedVariants: ["light", "dark"],
            version: "1.2.3"
        };

        var moreProductionCode=function(x){return x*2};
        return{init:function(){console.log("App initialized")}}}));
        """  # noqa: E501

        client = MockApiClient(production_like_js)
        catalog = LiveAssetsCatalog(client)  # type: ignore

        await catalog.refresh_index("index-main.js")
        config = await catalog.list_language_config()

        assert config is not None
        assert config.default_translation == "pl"
        assert len(config.translations) == 8

        # Verify production vs development separation
        prod_langs = [t for t in config.translations if not t.get("dev", False)]
        dev_langs = [t for t in config.translations if t.get("dev", False)]

        assert len(prod_langs) == 5  # PL, EN, DE, FR, CZ
        assert len(dev_langs) == 3  # NL, HU, JP

        # Verify specific production characteristics
        pl_lang = next(t for t in config.translations if t["id"] == "PL")
        assert "variants" in pl_lang  # Complex production feature

        jp_lang = next(t for t in config.translations if t["id"] == "JP")
        assert jp_lang.get("dev") is True  # Development flag works
