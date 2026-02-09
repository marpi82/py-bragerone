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

Complete example: `examples/basic_login.py <https://github.com/marpi82/py-bragerone/blob/main/examples/basic_login.py>`_

.. literalinclude:: ../../examples/basic_login.py
   :language: python
   :lines: 30-65
   :linenos:
   :emphasize-lines: 11-12, 15-16, 21-28

Step 2: Read Parameters
~~~~~~~~~~~~~~~~~~~~~~~

Complete example: `examples/read_parameters.py <https://github.com/marpi82/py-bragerone/blob/main/examples/read_parameters.py>`_

.. literalinclude:: ../../examples/read_parameters.py
   :language: python
   :lines: 32-80
   :linenos:
   :emphasize-lines: 9-11, 25-32

Step 3: Real-time Updates with Gateway
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Complete example: `examples/realtime_updates.py <https://github.com/marpi82/py-bragerone/blob/main/examples/realtime_updates.py>`_

.. literalinclude:: ../../examples/realtime_updates.py
   :language: python
   :lines: 68-92
   :linenos:
   :emphasize-lines: 6-7, 14-16, 20-23

.. tip::
   Set environment variables for easy testing:

   .. code-block:: bash

      export PYBO_EMAIL="user@example.com"
      export PYBO_PASSWORD="your-password"
      export PYBO_OBJECT_ID="12345"
      export PYBO_MODULES="MODULE1,MODULE2"

Step 4: Using ParamStore
~~~~~~~~~~~~~~~~~~~~~~~~~

Complete example: `examples/paramstore_usage.py <https://github.com/marpi82/py-bragerone/blob/main/examples/paramstore_usage.py>`_

.. literalinclude:: ../../examples/paramstore_usage.py
   :language: python
   :lines: 65-90
   :linenos:
   :emphasize-lines: 5-6, 14-18, 22-26

.. note::
   **ParamStore modes:**

   - **Lightweight mode** (shown above): Fast key→value storage for runtime
   - **Asset-aware mode**: Rich metadata with i18n labels/units (use during HA config flow)

   See :doc:`../architecture/overview` for details on when to use each mode.

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
   - :doc:`../reference/core_components` - Common patterns and workflows
   - :doc:`../architecture/overview` - Understand the architecture
   - :doc:`../api/api_reference` - Complete API documentation
   - :doc:`../api/pydantic_models` - Data models reference

Common Patterns
~~~~~~~~~~~~~~~

**Config Flow (No WebSocket)**

For Home Assistant config flow, you don't need WebSocket:

.. code-block:: python

   # Just REST API is enough
   client = BragerOneApiClient()
   await client.ensure_auth(email, password)
   try:
      objects = await client.get_objects()
      modules = await client.get_modules(object_id=objects[0].id)
      devids = [str(m.devid or m.id) for m in modules if (m.devid or m.id) is not None]

      # Enable asset-aware mode for metadata
      param_store = ParamStore()
      param_store.init_with_api(client, lang="en")

      # Fetch initial data (REST prime)
      status, payload = await client.modules_parameters_prime(devids, return_data=True)
      if status in (200, 204) and isinstance(payload, dict):
         param_store.ingest_prime_payload(payload)

      label = await param_store.resolve_label("PARAM_0")
      print(f"Example label: {label}")
   finally:
      await client.close()

**Runtime (Lightweight Mode)**

For runtime, use lightweight mode for best performance:

.. code-block:: python

   param_store = ParamStore()  # No init_with_api()
   asyncio.create_task(param_store.run_with_bus(gateway.bus))

   # Subscribe to updates
   async for event in gateway.bus.subscribe():
      pass  # ParamStore is updated by the background task

   # Fast access
   fam = param_store.get_family("P4", 1)
   value = fam.value if fam else None

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
