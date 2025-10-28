#!/usr/bin/env python3
"""Read parameters example - Fetch and display parameters from devices.

This example demonstrates:
- Logging in and selecting an object
- Getting modules for the object
- Fetching parameters using the REST API
- Displaying parameter values

Environment variables:
    PYBO_EMAIL: Login email
    PYBO_PASSWORD: Login password
    PYBO_OBJECT_ID: (Optional) Object ID to use

Usage:
    export PYBO_EMAIL="user@example.com"
    export PYBO_PASSWORD="your-password"
    python examples/read_parameters.py
"""

import asyncio
import os

from pybragerone.api import BragerOneApiClient


async def main() -> None:
    """Main function demonstrating parameter reading."""
    # Get credentials
    email = os.getenv("PYBO_EMAIL", "user@example.com")
    password = os.getenv("PYBO_PASSWORD", "password")
    object_id_env = os.getenv("PYBO_OBJECT_ID")

    client = BragerOneApiClient()

    try:
        # Login
        print(f"Logging in as {email}...")
        await client.ensure_auth(email, password)
        print("✓ Login successful")

        # Get object ID (from env or first available)
        if object_id_env:
            object_id = int(object_id_env)
            print(f"\n📦 Using object ID from PYBO_OBJECT_ID: {object_id}")
        else:
            objects = await client.get_objects()
            if not objects:
                print("❌ No objects found!")
                return
            object_id = objects[0].id
            print(f"\n📦 Using first object: {objects[0].name} (ID: {object_id})")

        # Get modules
        modules = await client.get_modules(object_id)
        print(f"✓ Found {len(modules)} module(s)")

        # Get module device IDs
        devids = [m.devid for m in modules if m.devid]
        if not devids:
            print("❌ No device IDs found in modules!")
            return

        print(f"✓ Device IDs: {', '.join(devids)}")

        # Fetch parameters using prime endpoint
        print(f"\n📊 Fetching parameters for devices: {', '.join(devids)}")
        result = await client.modules_parameters_prime(devids, return_data=True)

        # Result is tuple (status, data) when return_data=True
        if isinstance(result, tuple):
            status, data = result
        else:
            print("❌ Unexpected response format")
            return

        if status not in (200, 201):
            print(f"❌ Failed to fetch parameters (status: {status})")
            return

        # The response structure contains nested dictionaries
        # Example: {"MODULE1": {"P4": {"v1": 20, "v2": 30}}}
        print("✓ Retrieved parameters\n")
        print("Parameters:")
        print("-" * 60)

        param_count = 0
        for devid, pools in data.items():
            if not isinstance(pools, dict):
                continue

            print(f"\n🔧 Device: {devid}")

            for pool, channels in pools.items():
                if not isinstance(channels, dict):
                    continue

                for chan_idx, value in channels.items():
                    # Format: pool + channel+index (e.g., "P4" + "v1")
                    param_key = f"{pool}.{chan_idx}"
                    print(f"  {param_key:20} = {value}")
                    param_count += 1

                    if param_count >= 20:  # Limit output
                        break

                if param_count >= 20:
                    break

            if param_count >= 20:
                print("\n  ... (showing first 20 parameters)")
                break
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
