#!/usr/bin/env python3
"""Live testing script for BragerOne API with real credentials.

This script connects to real BragerOne API using environment variables
and tests the menu parsing and permission filtering functionality.

Environment variables (set in .env file):
- PYBO_EMAIL: BragerOne username/email
- PYBO_PASSWORD: BragerOne password
- PYBO_OBJECT_ID: Specific object ID to test (optional)
- LOG_LEVEL: Logging level (default: INFO)
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from pybragerone.api import BragerOneApiClient
from pybragerone.models.catalog import LiveAssetsCatalog

# Load environment variables from .env file
load_dotenv()


async def _fetch_text(url: str) -> str:
    """Fetch raw text from a URL using httpx.

    We use a short-lived httpx client here to avoid changing the API client's
    session management. This is only used for simple HTML discovery of assets.
    """
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def setup_logging() -> logging.Logger:
    """Set up logging configuration."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    return logging.getLogger("live_test")


async def test_live_menu_parsing() -> None:
    """Test menu parsing with live BragerOne API data."""
    logger = setup_logging()

    # Get credentials from environment (.env file loaded by poetry)
    email = os.getenv("PYBO_EMAIL")
    password = os.getenv("PYBO_PASSWORD")
    specific_object_id = os.getenv("PYBO_OBJECT_ID")

    if not email or not password:
        logger.error("Missing credentials! Set PYBO_EMAIL and PYBO_PASSWORD in .env file")
        logger.info("Create .env file from .env.example and set your credentials")
        return

    logger.info("🔐 Starting live test with credentials: %s", email)
    if specific_object_id:
        logger.info("🎯 Testing specific object ID: %s", specific_object_id)

    # Create results directory
    results_dir = Path(__file__).parent / "live_test_results"
    results_dir.mkdir(exist_ok=True)

    # Create API client
    api = BragerOneApiClient()
    try:
        # Login
        logger.info("🔑 Logging in...")
        token = await api.ensure_auth(email, password)
        logger.info("✅ Login successful, token expires: %s", token.expires_at)

        # Get user info and permissions
        logger.info("👤 Getting user info...")
        user_info = await api.get_user()
        logger.info("User: %s (%s)", user_info.user.name, user_info.user.email)

        permissions_response = await api.get_user_permissions()
        permissions = permissions_response.permissions
        logger.info("🔒 User permissions (%d): %s", len(permissions), permissions[:5] if permissions else "[]")

        # Note: Empty permissions may be normal for demo accounts or specific user roles
        if not permissions:
            logger.info("INFO: User has no permissions - this may be expected for demo/test accounts")

        # Get user objects
        logger.info("🏢 Getting user objects...")
        objects = await api.get_objects()
        logger.info("Objects found: %d", len(objects))
        for obj in objects[:3]:  # First 3
            logger.info("  - %s (ID: %d)", obj.name, obj.id)

        if not objects:
            logger.warning("No objects found for user")
            return

        # Test with specific object if provided, otherwise first object
        if specific_object_id:
            test_objects = [obj for obj in objects if str(obj.id) == specific_object_id]
            if not test_objects:
                logger.error("Object ID %s not found in user's objects", specific_object_id)
                logger.info("Available objects: %s", [obj.id for obj in objects])
                return
            test_object = test_objects[0]
        else:
            test_object = objects[0]

        logger.info("🧪 Testing with object: %s (ID: %d)", test_object.name, test_object.id)

        # Get object permissions
        obj_permissions_response = await api.get_object_permissions(test_object.id)
        obj_permissions = obj_permissions_response.permissions
        logger.info("🔒 Object permissions (%d): %s", len(obj_permissions), obj_permissions[:5] if obj_permissions else "[]")

        # Note about empty object permissions
        if not obj_permissions:
            logger.info("INFO: Object has no permissions - testing will show all menu items without filtering")

        # Get modules for the test object to get real deviceMenu and permissions
        logger.info("🔧 Getting modules for object %d...", test_object.id)
        modules = await api.get_modules(test_object.id)
        logger.info("Modules found: %d", len(modules))

        # Log module details
        for module in modules:
            logger.info("  - %s: deviceMenu=%d, permissions=%d", module.name, module.deviceMenu, len(module.permissions))

        if not modules:
            logger.error("No modules found - cannot test menu parsing")
            return

        # Create catalog and test menu parsing
        logger.info("📋 Creating LiveAssetsCatalog...")
        catalog = LiveAssetsCatalog(api, logger=logger)

        # Discover actual index file from /assets/ page instead of guessing
        logger.info("🔍 Discovering index file from /assets/ page...")
        catalog_loaded = False

        try:
            import time

            start_time = time.time()

            assets_html = await _fetch_text("https://one.brager.pl/assets/")
            discovery_time = time.time() - start_time
            logger.info("📥 Assets page fetched in %.2fs", discovery_time)

            import re

            # Look for patterns like /assets/index-XXXXXXXX.js
            m = re.search(r"/assets/(index-[A-Za-z0-9_-]+\.js)", assets_html)
            if m:
                discovered = m.group(1)
                discovered_url = f"https://one.brager.pl/assets/{discovered}"
                logger.info("🎯 Discovered index file: %s", discovered_url)

                try:
                    start_time = time.time()
                    await catalog.refresh_index(discovered_url)
                    index_time = time.time() - start_time
                    logger.info("✅ Index loaded successfully in %.2fs", index_time)
                    catalog_loaded = True
                except Exception as e2:
                    logger.error("❌ Discovered index failed to load: %s", e2)
            else:
                logger.warning("🔎 No hashed index pattern found on assets page")

        except Exception as discovery_e:
            logger.error("❌ Error during discovery of assets page: %s", discovery_e)

        # Only try fallback URLs if discovery completely failed
        if not catalog_loaded:
            logger.info("🔄 Discovery failed, trying fallback URLs...")
            alternative_urls = [
                f"https://one.brager.pl/assets/index-{test_object.id}.js",
                "https://one.brager.pl/assets/index-main.js",
                "https://one.brager.pl/assets/index.js",
            ]

            for alt_url in alternative_urls:
                logger.info("🔄 Trying fallback URL: %s", alt_url)
                try:
                    await catalog.refresh_index(alt_url)
                    logger.info("✅ Fallback URL worked!")
                    catalog_loaded = True
                    break
                except Exception as alt_e:
                    logger.debug("❌ Fallback URL failed: %s", alt_e)

        if not catalog_loaded:
            logger.error("❌ Could not load any asset catalog")
            return

        # Test language config
        try:
            start_time = time.time()
            lang_config = await catalog.list_language_config()
            lang_time = time.time() - start_time

            if lang_config:
                logger.info(
                    "🌍 Languages available (%d): %s (%.2fs)",
                    len(lang_config.translations),
                    [t.get("id", "unknown") for t in lang_config.translations],
                    lang_time,
                )
                logger.info("Default language: %s", lang_config.default_translation)
            else:
                logger.warning("No language configuration found")
        except Exception as e:
            logger.warning("Error getting language config: %s", e)

        # Test menu parsing for each module with its specific permissions
        for module in modules:
            logger.info("📱 Testing menu for module '%s' (deviceMenu=%d)", module.name[:30], module.deviceMenu)

            try:
                # Use module's specific permissions for menu filtering
                module_permissions = module.permissions
                logger.info("🔒 Module permissions (%d): %s", len(module_permissions), module_permissions[:5])

                # Test with module permissions (this is the real-world scenario)
                start_time = time.time()
                menu_filtered = await catalog.get_module_menu(module.deviceMenu, permissions=module_permissions)
                menu_time = time.time() - start_time
                logger.info(
                    "🔒 Menu with module permissions: %d routes, %d tokens (%.2fs)",
                    len(menu_filtered.routes),
                    len(menu_filtered.tokens),
                    menu_time,
                )

                # Analyze tokens from filtered menu
                filtered_tokens = menu_filtered.tokens

                logger.info("🔍 Token analysis:")
                logger.info("  - Visible tokens with permissions: %d", len(filtered_tokens))

                if filtered_tokens:
                    logger.info("  - Sample visible tokens: %s", list(filtered_tokens)[:5])

                # Group routes by main sections (only visible ones)
                sections = {}
                visible_routes = [route for route in menu_filtered.routes if route.get("_visible", False)]
                for route in visible_routes:
                    path_parts = route.get("path", "").split("/")
                    main_section = path_parts[0] if path_parts else "unknown"

                    if main_section not in sections:
                        sections[main_section] = []
                    sections[main_section].append(route.get("path", ""))

                logger.info("📋 Route sections found:")
                for section_name, paths in sections.items():
                    logger.info(f"  - {section_name}: {len(paths)} routes")  # Save detailed results
                results = {
                    "test_info": {
                        "timestamp": asyncio.get_event_loop().time(),
                        "user_email": email,
                        "log_level": os.getenv("LOG_LEVEL", "DEBUG"),
                    },
                    "module_info": {
                        "name": module.name,
                        "device_menu": module.deviceMenu,
                        "permissions_count": len(module_permissions),
                    },
                    "object_info": {"id": test_object.id, "name": test_object.name},
                    "permissions": {"module_permissions": module_permissions},
                    "menu_filtered": {
                        "routes_count": len(menu_filtered.routes),
                        "tokens": sorted(list(filtered_tokens)),
                        "sample_route": menu_filtered.routes[0] if menu_filtered.routes else None,
                        "all_routes": menu_filtered.routes,
                        "routes_by_section": sections,
                    },
                    "analysis": {
                        "visible_tokens": len(filtered_tokens),
                        "visible_token_list": sorted(list(filtered_tokens)),
                    },
                }

                filename = results_dir / f"live_test_results_module_{module.deviceMenu}_{module.name[:20]}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                logger.info("📄 Detailed results saved to: %s", filename)

            except Exception as e:
                logger.error("❌ Error testing module '%s' (deviceMenu=%d): %s", module.name[:20], module.deviceMenu, e)

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise
    finally:
        # Close API session to prevent unclosed connector warnings
        try:
            await api.close()
            logger.debug("✅ API session closed")
        except Exception as close_e:
            logger.debug("Warning: Could not close API session: %s", close_e)


async def compare_with_app_data() -> None:
    """Helper to compare parsed data with what you see in the app."""
    logger = logging.getLogger("compare")

    logger.info("🔍 COMPARISON GUIDE:")
    logger.info("1. Check the generated JSON files in scripts/live_test_results/")
    logger.info("2. Compare 'visible_tokens' with parameters you can see in your app")
    logger.info("3. Verify 'hidden_tokens' are indeed not visible in your app")
    logger.info("4. Check route structure matches your app's menu hierarchy")
    logger.info("5. Validate permission filtering works correctly")

    # Instructions for manual verification
    print("\n" + "=" * 60)
    print("MANUAL VERIFICATION CHECKLIST:")
    print("=" * 60)
    print("□ Login to your BragerOne app")
    print("□ Navigate to parameters/configuration section")
    print("□ Compare visible parameters with 'visible_tokens' in JSON")
    print("□ Check if any 'hidden_tokens' are actually visible (security issue)")
    print("□ Verify menu structure matches app navigation")
    print("□ Test with different user permissions if available")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_live_menu_parsing())
    asyncio.run(compare_with_app_data())
