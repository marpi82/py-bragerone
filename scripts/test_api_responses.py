#!/usr/bin/env python3
"""Test script to inspect actual API response structures.

This script calls various API endpoints and prints their raw response structures
to help understand what the API actually returns vs. what our models expect.

Usage:
    python scripts/test_api_responses.py

Environment variables:
    BRAGER_EMAIL - user email for authentication
    BRAGER_PASSWORD - user password for authentication
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pybragerone.api.client import BragerOneApiClient


def print_section(title: str) -> None:
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_response(endpoint: str, status: int, data: Any) -> None:
    """Print API response in readable format."""
    print(f"\n📍 Endpoint: {endpoint}")
    print(f"📊 Status: {status}")
    print(f"📦 Type: {type(data).__name__}")

    if isinstance(data, dict):
        print(f"🔑 Keys: {list(data.keys())}")
        print("\n💾 Full response:")
        print(json.dumps(data, indent=2, default=str))
    elif isinstance(data, list):
        print(f"📏 Length: {len(data)}")
        if data:
            print(f"🔍 First item type: {type(data[0]).__name__}")
            if isinstance(data[0], dict):
                print(f"🔑 First item keys: {list(data[0].keys())}")
            print("\n💾 First item:")
            print(json.dumps(data[0], indent=2, default=str))
    else:
        print(f"💾 Response: {data}")


async def test_system_version(client: BragerOneApiClient) -> None:
    """Test /v1/system/version endpoint (no auth needed)."""
    print_section("Testing: GET /v1/system/version (no auth)")

    try:
        from pybragerone.api.endpoints import system_version_url

        status, data, _ = await client._req("GET", system_version_url(), auth=False)
        print_response("GET /v1/system/version", status, data)
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_user_info(client: BragerOneApiClient) -> None:
    """Test /v1/user endpoint."""
    print_section("Testing: GET /v1/user")

    try:
        from pybragerone.api.endpoints import user_url

        status, data, _ = await client._req("GET", user_url())
        print_response("GET /v1/user", status, data)
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_user_permissions(client: BragerOneApiClient) -> None:
    """Test /v1/user/permissions endpoint."""
    print_section("Testing: GET /v1/user/permissions")

    try:
        from pybragerone.api.endpoints import user_permissions_url

        status, data, _ = await client._req("GET", user_permissions_url())
        print_response("GET /v1/user/permissions", status, data)
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_objects(client: BragerOneApiClient) -> Any:
    """Test /v1/objects endpoint."""
    print_section("Testing: GET /v1/objects")

    try:
        from pybragerone.api.endpoints import objects_url

        status, data, _ = await client._req("GET", objects_url())
        print_response("GET /v1/objects", status, data)
        return data
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def test_object_details(client: BragerOneApiClient, object_id: int) -> None:
    """Test /v1/objects/{id} endpoint."""
    print_section(f"Testing: GET /v1/objects/{object_id}")

    try:
        from pybragerone.api.endpoints import object_url

        status, data, _ = await client._req("GET", object_url(object_id))
        print_response(f"GET /v1/objects/{object_id}", status, data)
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_object_permissions(client: BragerOneApiClient, object_id: int) -> None:
    """Test /v1/objects/{id}/permissions endpoint."""
    print_section(f"Testing: GET /v1/objects/{object_id}/permissions")

    try:
        from pybragerone.api.endpoints import object_permissions_url

        status, data, _ = await client._req("GET", object_permissions_url(object_id))
        print_response(f"GET /v1/objects/{object_id}/permissions", status, data)
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_modules(client: BragerOneApiClient, object_id: int) -> None:
    """Test /v1/modules endpoint."""
    print_section(f"Testing: GET /v1/modules?group_id={object_id}")

    try:
        from pybragerone.api.endpoints import modules_url

        status, data, _ = await client._req("GET", modules_url(object_id))
        print_response(f"GET /v1/modules?group_id={object_id}", status, data)
    except Exception as e:
        print(f"❌ Error: {e}")


async def main() -> None:
    """Run all API response tests."""
    email = os.getenv("BRAGER_EMAIL")
    password = os.getenv("BRAGER_PASSWORD")

    if not email or not password:
        print("❌ Error: BRAGER_EMAIL and BRAGER_PASSWORD environment variables required!")
        print("\nUsage:")
        print("  export BRAGER_EMAIL='your@email.com'")
        print("  export BRAGER_PASSWORD='yourpassword'")
        print("  python scripts/test_api_responses.py")
        sys.exit(1)

    print("🚀 Starting API response structure tests...")
    print(f"📧 Email: {email}")

    client = BragerOneApiClient(
        enable_http_trace=True,
        redact_secrets=False,  # Show full details for debugging
    )

    try:
        # Test system version (no auth)
        await test_system_version(client)

        # Login
        print_section("Logging in...")
        await client.ensure_auth(email, password)
        print("✅ Login successful!")

        # Test authenticated endpoints
        await test_user_info(client)
        await test_user_permissions(client)

        # Get objects to get an object_id for further tests
        objects_data = await test_objects(client)

        # If we have objects, test object-specific endpoints
        if objects_data:
            # Extract object_id from response
            object_id = None
            if isinstance(objects_data, list) and objects_data:
                object_id = objects_data[0].get("id")
            elif isinstance(objects_data, dict):
                if objects_data.get("data"):
                    object_id = objects_data["data"][0].get("id")
                elif objects_data.get("objects"):
                    object_id = objects_data["objects"][0].get("id")

            if object_id:
                await test_object_details(client, object_id)
                await test_object_permissions(client, object_id)
                await test_modules(client, object_id)
            else:
                print("\n⚠️  Could not extract object_id from response")

        print_section("✅ All tests completed successfully!")
        return None

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return None
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
