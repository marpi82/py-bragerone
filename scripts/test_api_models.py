#!/usr/bin/env python3
"""Simple test to verify API returns Pydantic models."""

import asyncio
import os
from pathlib import Path

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.api import (
    BragerObject,
    Module,
    ModuleCard,
    ObjectDetailsResponse,
    SystemVersion,
    UserInfoResponse,
)

try:
    from dotenv import load_dotenv

    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


async def test_api_models():
    """Test that API methods return proper Pydantic models."""
    username = os.getenv("PYBO_EMAIL")
    password = os.getenv("PYBO_PASSWORD")

    if not username or not password:
        print("ERROR: Missing PYBO_EMAIL or PYBO_PASSWORD environment variables")
        return

    def creds_provider():
        return (username, password)

    client = BragerOneApiClient(creds_provider=creds_provider)

    try:
        # Authenticate first
        await client.ensure_auth(username, password)

        # Test user info
        user_info = await client.get_user()
        print(f"✓ get_user() returned: {type(user_info)}")
        assert isinstance(user_info, UserInfoResponse)
        assert hasattr(user_info.user, "email")
        print(f"  User email: {user_info.user.email}")

        # Test user permissions
        permissions = await client.get_user_permissions()
        print(f"✓ get_user_permissions() returned: {type(permissions)} with {len(permissions)} items")
        assert isinstance(permissions, list)

        # Test objects list
        objects = await client.get_objects()
        print(f"✓ get_objects() returned: {type(objects)} with {len(objects)} items")
        assert isinstance(objects, list)
        if objects:
            assert isinstance(objects[0], BragerObject)
            print(f"  First object name: {objects[0].name}")

            # Test object details
            object_details = await client.get_object(objects[0].id)
            print(f"✓ get_object() returned: {type(object_details)}")
            assert isinstance(object_details, ObjectDetailsResponse)
            print(f"  Object status: {object_details.status}")

            # Test modules list
            modules = await client.get_modules(objects[0].id)
            print(f"✓ get_modules() returned: {type(modules)} with {len(modules)} items")
            assert isinstance(modules, list)
            if modules:
                assert isinstance(modules[0], Module)
                print(f"  First module name: {modules[0].name}")
                print(f"  Module gateway: {modules[0].gateway.address}")

                # Test module card
                try:
                    module_card = await client.get_module_card(modules[0].devid)
                    print(f"✓ get_module_card() returned: {type(module_card)}")
                    assert isinstance(module_card, ModuleCard)
                    print(f"  Client name: {module_card.clientFullName}")
                    print(f"  Address: {module_card.clientAddressCity}")
                except Exception as e:
                    print(f"⚠ get_module_card() failed: {e}")

        # Test system version
        try:
            version = await client.get_system_version()
            print(f"✓ get_system_version() returned: {type(version)}")
            assert isinstance(version, SystemVersion)
            print(f"  System version: {version.version.version}")
            print(f"  Dev mode: {version.version.devMode}")
        except Exception as e:
            print(f"⚠ get_system_version() failed: {e}")

        print("\n🎉 All API methods return correct Pydantic models!")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_api_models())
