#!/usr/bin/env python3
"""Real-time parameter updates example using Gateway and WebSocket.

This example demonstrates:
- Using BragerOneGateway for complete setup
- Subscribing to real-time parameter updates via EventBus
- Displaying live parameter changes from WebSocket

Environment variables:
    PYBO_EMAIL: Login email
    PYBO_PASSWORD: Login password
    PYBO_OBJECT_ID: Object ID
    PYBO_MODULES: Comma-separated module IDs (e.g., "ABC123,DEF456")

Usage:
    export PYBO_EMAIL="user@example.com"
    export PYBO_PASSWORD="your-password"
    export PYBO_OBJECT_ID="12345"
    export PYBO_MODULES="MODULE1,MODULE2"
    python examples/realtime_updates.py
"""

import asyncio
import contextlib
import os
import signal

from pybragerone import BragerOneGateway


async def main() -> None:
    """Main function demonstrating real-time parameter monitoring."""
    # Get configuration from environment
    email = os.getenv("PYBO_EMAIL")
    password = os.getenv("PYBO_PASSWORD")
    object_id_str = os.getenv("PYBO_OBJECT_ID")
    modules_str = os.getenv("PYBO_MODULES")

    # Validate required environment variables
    if not email or not password:
        print("❌ Error: PYBO_EMAIL and PYBO_PASSWORD must be set")
        print("\nUsage:")
        print("  export PYBO_EMAIL='user@example.com'")
        print("  export PYBO_PASSWORD='your-password'")
        print("  export PYBO_OBJECT_ID='12345'")
        print("  export PYBO_MODULES='MODULE1,MODULE2'")
        return

    if not object_id_str or not modules_str:
        print("❌ Error: PYBO_OBJECT_ID and PYBO_MODULES must be set")
        print("\nExample:")
        print("  export PYBO_OBJECT_ID='12345'")
        print("  export PYBO_MODULES='ABC123,DEF456'")
        return

    object_id = int(object_id_str)
    modules = [m.strip() for m in modules_str.split(",")]

    print("📡 Connecting to BragerOne...")
    print(f"   Email: {email}")
    print(f"   Object ID: {object_id}")
    print(f"   Modules: {', '.join(modules)}")

    # Create Gateway (handles API + WebSocket + EventBus)
    gateway = BragerOneGateway(
        email=email,
        password=password,
        object_id=object_id,
        modules=modules,
    )

    # Create event subscriber task
    async def monitor_updates() -> None:
        """Subscribe to EventBus and print parameter updates."""
        print("\n🔔 Monitoring parameter updates (Ctrl+C to stop)...\n")
        update_count = 0

        async for event in gateway.bus.subscribe():
            update_count += 1

            # Skip meta-only events (no value change)
            if event.value is None:
                continue

            # Format parameter key
            param_key = f"{event.pool}.{event.chan}{event.idx}"

            # Display update with device ID
            print(f"[{update_count:4d}] {event.devid:12} {param_key:15} = {event.value}")

    # Start gateway
    try:
        # Start gateway (connects WebSocket, subscribes, primes parameters)
        await gateway.start()
        print("✓ Gateway started successfully")

        # Start monitoring task
        monitor_task = asyncio.create_task(monitor_updates())

        # Wait for Ctrl+C
        stop_event = asyncio.Event()

        def signal_handler() -> None:
            stop_event.set()

        # Register signal handler for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        await stop_event.wait()

        # Cancel monitoring and wait for clean shutdown
        monitor_task.cancel()
        # Await ensures task completes gracefully despite cancellation
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task

    finally:
        # Stop gateway (disconnects WebSocket, closes API)
        print("\n\n🛑 Shutting down...")
        await gateway.stop()
        print("✓ Gateway stopped")


if __name__ == "__main__":
    asyncio.run(main())
