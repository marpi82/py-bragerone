"""Debug specific test failures."""

import asyncio
import logging

from pybragerone.models.catalog import LiveAssetsCatalog
from tests.test_parser_resilience import MockApiClient


async def debug_failing_tests():
    """Debug the two failing tests."""
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("debug_test")

    failing_cases = [
        (
            "var_assignment",
            """var HL = {
            translations: [
                { id: 'pl', flag: 'pl', name: 'Polski' },
                { id: 'en', flag: 'gb', name: 'English' },
                { id: 'cs', flag: 'cz', name: 'Čeština', dev: true }
            ],
            defaultTranslation: 'pl'
        };""",
        ),
        (
            "unicode_handling",
            """var HL = {
            translations: [
                { id: 'pl', flag: 'pl', name: 'Polski' },
                { id: 'cs', flag: 'cz', name: 'Čeština' },
                { id: 'ru', flag: 'ru', name: 'Русский' },
                { id: 'ja', flag: 'jp', name: '日本語' }
            ],
            defaultTranslation: 'pl'
        };""",
        ),
    ]

    for test_name, js_content in failing_cases:
        print(f"\n🔧 Debug: {test_name}")
        print("-" * 40)

        try:
            client = MockApiClient(js_content)
            catalog = LiveAssetsCatalog(client, logger=logger)  # type: ignore

            await catalog.refresh_index("index-main.js")
            config = await catalog.list_language_config()

            if config:
                print(f"✅ SUCCESS: {len(config.translations)} languages found")
            else:
                print("❌ FAILED: No config found")

        except Exception as e:
            print(f"❌ ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(debug_failing_tests())
