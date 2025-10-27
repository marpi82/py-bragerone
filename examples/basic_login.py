#!/usr/bin/env python3
"""Basic login example - List available devices and objects.

This example demonstrates:
- Creating an API client
- Logging in with credentials (from env vars or hardcoded)
- Fetching available objects (heating systems)
- Listing modules for each object

Environment variables:
    PYBO_EMAIL: Login email
    PYBO_PASSWORD: Login password

Usage:
    # With environment variables
    export PYBO_EMAIL="user@example.com"
    export PYBO_PASSWORD="your-password"
    python examples/basic_login.py

    # Or edit the script to use hardcoded credentials
"""

import asyncio
import os

from pybragerone.api import BragerOneApiClient


async def main() -> None:
    """Main function demonstrating basic login and device listing."""
    # Get credentials from environment variables or use defaults
    email = os.getenv("PYBO_EMAIL", "user@example.com")
    password = os.getenv("PYBO_PASSWORD", "password")

    # Create API client
    client = BragerOneApiClient()

    try:
        # Login with credentials
        print(f"Logging in as {email}...")
        await client.ensure_auth(email, password)
        print("✓ Login successful")

        # Get available objects (heating systems)
        objects = await client.get_objects()
        print(f"\n✓ Found {len(objects)} heating system(s)")

        # List each object with its modules
        for obj in objects:
            print(f"\n📦 Object: {obj.name}")
            print(f"   ID: {obj.id}")
            print(f"   Address: {obj.addressStreet or 'N/A'}, {obj.addressCity or 'N/A'}")

            # Get modules for this object
            modules = await client.get_modules(obj.id)
            print(f"   Modules: {len(modules)}")

            for module in modules:
                devid = module.devid or f"id:{module.id}"
                version = module.moduleVersion or module.gateway.version or "unknown"
                print(f"      - {module.name} (devid: {devid}, version: {version})")
    finally:
        # Always close the client
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
