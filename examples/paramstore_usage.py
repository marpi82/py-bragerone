#!/usr/bin/env python3
"""ParamStore usage example - Lightweight and asset-aware modes.

This example demonstrates:
- Lightweight mode: Simple key→value parameter storage
- Asset-aware mode: Integration with LiveAssetsCatalog for i18n/metadata
- Using ParamStore with Gateway and EventBus
- Accessing parameter values and metadata

Environment variables:
    PYBO_EMAIL: Login email
    PYBO_PASSWORD: Login password
    PYBO_OBJECT_ID: Object ID
    PYBO_MODULES: Comma-separated module IDs

Usage:
    export PYBO_EMAIL="user@example.com"
    export PYBO_PASSWORD="your-password"
    export PYBO_OBJECT_ID="12345"
    export PYBO_MODULES="MODULE1,MODULE2"
    python examples/paramstore_usage.py
"""

import asyncio
import os

from pybragerone import BragerOneGateway
from pybragerone.models.param import ParamStore


async def main() -> None:
    """Main function demonstrating ParamStore usage."""
    # Get configuration
    email = os.getenv("PYBO_EMAIL")
    password = os.getenv("PYBO_PASSWORD")
    object_id_str = os.getenv("PYBO_OBJECT_ID")
    modules_str = os.getenv("PYBO_MODULES")

    if not all([email, password, object_id_str, modules_str]):
        print("❌ Error: Required environment variables not set")
        print("\nRequired:")
        print("  PYBO_EMAIL, PYBO_PASSWORD, PYBO_OBJECT_ID, PYBO_MODULES")
        return

    # Type narrowing for mypy
    assert email is not None
    assert password is not None
    assert object_id_str is not None
    assert modules_str is not None

    object_id = int(object_id_str)
    modules = [m.strip() for m in modules_str.split(",")]

    print("🔧 ParamStore Example - Lightweight Mode\n")
    print(f"Connecting as: {email}")
    print(f"Object ID: {object_id}")
    print(f"Modules: {', '.join(modules)}\n")

    # ========== Lightweight Mode ==========
    # Simple key→value storage, minimal overhead
    # Best for runtime performance

    gateway = BragerOneGateway(
        email=email,
        password=password,
        object_id=object_id,
        modules=modules,
    )

    # Create ParamStore in lightweight mode
    pstore = ParamStore()

    # Subscribe ParamStore to EventBus (background task)
    store_task = asyncio.create_task(pstore.run_with_bus(gateway.bus))

    try:
        # Start gateway
        await gateway.start()
        print("✓ Gateway started")

        # Wait for initial parameters to populate
        await asyncio.sleep(2)

        # Access parameters using flatten() method
        print("\n📊 Sample parameters from ParamStore (lightweight mode):")
        print("-" * 60)

        # Get flattened view of all parameters
        params = pstore.flatten()
        params_list = list(params.items())[:10]  # Show first 10

        for param_key, value in params_list:
            print(f"  {param_key:20} = {value}")

        total_params = len(params)
        print(f"\n✓ Total parameters in store: {total_params}")

        # Individual parameter access via get_family
        # Example: get P4 index 1
        family = pstore.get_family("P4", 1)
        if family:
            print(f"\n✓ Direct access example: P4.v1 = {family.value}")
            print(f"   Unit code: {family.unit_code}")
            print(f"   Status: {family.status_raw}")

        # Monitor updates for a few seconds
        print("\n🔔 Monitoring live updates (5 seconds)...")
        update_count = 0

        async def count_updates() -> None:
            nonlocal update_count
            async for event in gateway.bus.subscribe():
                if event.value is not None:
                    update_count += 1

        count_task = asyncio.create_task(count_updates())
        await asyncio.sleep(5)
        count_task.cancel()

        print(f"✓ Received {update_count} parameter updates in 5 seconds")

    finally:
        # Cleanup
        store_task.cancel()
        await gateway.stop()
        print("\n✓ Gateway stopped")


if __name__ == "__main__":
    asyncio.run(main())
