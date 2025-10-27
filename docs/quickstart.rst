Quick Start Tutorial
====================

This tutorial will get you up and running with pybragerone in just a few minutes.

Installation
------------

Install from PyPI:

.. code-block:: bash

   pip install pybragerone

Or install from TestPyPI for pre-release versions:

.. code-block:: bash

   pip install -i https://test.pypi.org/simple/ pybragerone

Optional Extras
~~~~~~~~~~~~~~~

.. code-block:: bash

   # CLI tools with rich formatting
   pip install "pybragerone[cli]"

   # Secure token storage
   pip install "pybragerone[keyring]"

Basic Usage
-----------

Step 1: Login and Get Devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pybragerone.api import BragerOneApiClient

   async def main():
       # Create API client
       async with BragerOneApiClient() as client:
           # Login with your credentials
           await client.login("user@example.com", "password")

           # Get available objects (heating systems)
           objects = await client.get_objects()
           print(f"Found {len(objects)} objects")

           for obj in objects:
               print(f"- {obj.name} (ID: {obj.id}, Device: {obj.deviceId})")

   asyncio.run(main())

Step 2: Read Parameters
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pybragerone.api import BragerOneApiClient

   async def main():
       async with BragerOneApiClient() as client:
           await client.login("user@example.com", "password")

           # Get first object
           objects = await client.get_objects()
           obj = objects[0]

           # Get modules for this object
           modules = await client.get_modules(obj.id)
           print(f"Object has {len(modules)} modules")

           # Get parameters for the device
           device_id = obj.deviceId
           module_ids = [m.id for m in modules]

           params = await client.get_parameters(device_id, module_ids)

           # Display parameters
           for param in params:
               if param.value is not None:
                   print(f"{param.pool}.{param.chan}{param.idx} = {param.value}")

   asyncio.run(main())

Step 3: Real-time Updates
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pybragerone.api import BragerOneApiClient
   from pybragerone.gateway import BragerOneGateway

   async def main():
       async with BragerOneApiClient() as client:
           await client.login("user@example.com", "password")

           # Get device info
           objects = await client.get_objects()
           obj = objects[0]
           modules = await client.get_modules(obj.id)

           # Create gateway for real-time updates
           gateway = BragerOneGateway(client)

           # Start gateway (connects WebSocket, subscribes, fetches initial data)
           await gateway.start(obj.deviceId, [m.id for m in modules])

           # Subscribe to parameter updates
           print("Listening for updates (press Ctrl+C to stop)...")
           try:
               async for event in gateway.event_bus.subscribe():
                   print(f"Update: {event.pool}.{event.chan}{event.idx} = {event.value}")
           except KeyboardInterrupt:
               print("Stopping...")

           # Cleanup
           await gateway.stop()

   asyncio.run(main())

Step 4: Using ParamStore
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pybragerone.api import BragerOneApiClient
   from pybragerone.gateway import BragerOneGateway
   from pybragerone.models.param import ParamStore

   async def main():
       async with BragerOneApiClient() as client:
           await client.login("user@example.com", "password")

           objects = await client.get_objects()
           obj = objects[0]
           modules = await client.get_modules(obj.id)

           # Create ParamStore to track current values
           param_store = ParamStore()

           # Create gateway
           gateway = BragerOneGateway(client)

           # Subscribe ParamStore to updates
           async def update_store():
               async for event in gateway.event_bus.subscribe():
                   param_store.upsert(event)

           # Start update task
           import asyncio
           update_task = asyncio.create_task(update_store())

           # Start gateway
           await gateway.start(obj.deviceId, [m.id for m in modules])

           # Wait a bit for initial data
           await asyncio.sleep(2)

           # Read from ParamStore
           print("Current parameters:")
           for key, value in param_store.items():
               print(f"  {key} = {value}")

           # Get specific parameter
           temp = param_store.get("P4.v1")
           if temp is not None:
               print(f"Temperature: {temp}°C")

           # Cleanup
           update_task.cancel()
           await gateway.stop()

   asyncio.run(main())

Using the CLI
-------------

For quick testing and debugging, use the CLI tool:

.. code-block:: bash

   # Interactive mode with guided login
   pybragerone-cli --email user@example.com --password "***"

   # Enable debug logging
   pybragerone-cli --email user@example.com --password "***" --debug

   # Show raw WebSocket messages
   pybragerone-cli --email user@example.com --password "***" --raw-ws

   # Dump ParamStore to JSON files
   pybragerone-cli --email user@example.com --password "***" --dump-store

Next Steps
----------

.. seealso::
   - :doc:`quick_reference` - Common patterns and workflows
   - :doc:`architecture_guide` - Understand the architecture
   - :doc:`api_reference` - Complete API documentation
   - :doc:`pydantic_models` - Data models reference

Common Patterns
~~~~~~~~~~~~~~~

**Config Flow (No WebSocket)**

For Home Assistant config flow, you don't need WebSocket:

.. code-block:: python

   # Just REST API is enough
   async with BragerOneApiClient() as client:
       await client.login(email, password)
       objects = await client.get_objects()
       modules = await client.get_modules(object_id)

       # Enable asset-aware mode for metadata
       param_store = ParamStore()
       await param_store.init_with_api(client)

       # Fetch initial data
       params = await client.get_parameters(device_id, module_ids)
       for event in params:
           param_store.upsert(event)

       # Now you have metadata for entity discovery
       label = param_store.get_label("P4.v1", lang="en")
       unit = param_store.get_unit("P4.v1")

**Runtime (Lightweight Mode)**

For runtime, use lightweight mode for best performance:

.. code-block:: python

   param_store = ParamStore()  # No init_with_api()

   # Subscribe to updates
   async for event in gateway.event_bus.subscribe():
       param_store.upsert(event)

   # Fast access
   value = param_store.get("P4.v1")

Troubleshooting
---------------

**Connection Issues**

If you can't connect, check:

1. Valid credentials
2. Internet connection to BragerOne cloud
3. Device is online and accessible

**No Updates**

If WebSocket connects but no updates arrive:

1. Check that you called ``gateway.start()`` (not just connect)
2. Verify modules are correct
3. Try fetching parameters manually first

**ImportError**

If you get import errors:

.. code-block:: bash

   # Ensure you installed the package
   pip install pybragerone

   # For CLI features
   pip install "pybragerone[cli]"

Need Help?
----------

- **GitHub Issues**: https://github.com/marpi82/py-bragerone/issues
- **GitHub Releases**: https://github.com/marpi82/py-bragerone/releases
- **Documentation**: https://marpi82.github.io/py-bragerone/
