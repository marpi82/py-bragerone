Quick Reference
===============

A quick reference guide for common patterns and usage in pybragerone.

.. seealso::
   - :doc:`getting_started` - Installation and basic setup
   - :doc:`architecture_guide` - Deep dive into architecture
   - :doc:`api_reference` - Complete API documentation

.. contents:: :local:

Essential Concepts
------------------

.. important::
   **Always fetch initial data via REST API** when starting up or after reconnecting WebSocket.
   WebSocket only sends updates, never the full state!

.. tip::
   **Two modes for ParamStore:**

   - **Lightweight mode** (runtime): Simple key→value storage, fast and minimal overhead
   - **Asset-aware mode** (setup): Rich metadata with labels, units, and translations

Key Workflows
-------------

.. note::
   **For Home Assistant integration:**

   1. **Setup phase** (config flow): Use asset-aware mode to discover entities
   2. **Runtime phase**: Switch to lightweight mode for performance
   3. **After reconnect**: Always re-fetch data from REST API

Core Components
---------------

EventBus
~~~~~~~~

The EventBus handles real-time parameter updates with multicast delivery.

.. code-block:: python

   from pybragerone.models.events import EventBus, ParamUpdate

   # Create event bus
   event_bus = EventBus()

   # Subscribe to updates
   async for event in event_bus.subscribe():
       if isinstance(event, ParamUpdate):
           print(f"Parameter {event.pool}.{event.chan}{event.idx} = {event.value}")

.. tip::
   Subscribe **before** fetching initial data to avoid missing updates.

ParamUpdate Events
~~~~~~~~~~~~~~~~~~

Every parameter change triggers a ``ParamUpdate`` event with these fields:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Field
     - Description
   * - ``devid``
     - Device identifier
   * - ``pool``
     - Parameter pool (e.g., ``"P4"``, ``"P5"``)
   * - ``chan``
     - Channel type: ``"v"`` (value), ``"s"`` (status), ``"u"`` (unit)
   * - ``idx``
     - Parameter index (integer)
   * - ``value``
     - Current value or ``None`` if metadata-only
   * - ``meta``
     - Additional info (timestamps, averages, etc.)

ParamStore Usage
----------------

Lightweight Mode (Runtime)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

For production use, lightweight mode provides fast access to parameter values.

.. code-block:: python

   from pybragerone.models.param import ParamStore

   # Create store
   param_store = ParamStore()

   # Subscribe to EventBus
   async for event in event_bus.subscribe():
       param_store.upsert(event)

   # Read values
   temperature = param_store.get("P4.v1")  # Returns value or None
   status = param_store.get("P5.s40")      # Returns status bitmask

.. note::
   **Binary sensor pattern** for status bits:

   .. code-block:: python

      status_value = param_store.get("P5.s40")
      bit_index = 3
      is_active = bool(status_value & (1 << bit_index))

Asset-Aware Mode (Setup)
~~~~~~~~~~~~~~~~~~~~~~~~~

For config flow and entity discovery, enable rich metadata support.

.. code-block:: python

   # Initialize with API client
   await param_store.init_with_api(api_client)

   # Access metadata
   label = param_store.get_label("P4.v1", lang="en")     # "Temperature"
   unit = param_store.get_unit("P4.v1")                   # "°C"
   enum_options = param_store.get_enum_labels("P5.u1")   # ["Off", "On", "Auto"]

.. warning::
   Asset-aware mode requires fetching JavaScript assets from BragerOne web app.
   Use only during setup, not in production runtime!

Home Assistant Integration
---------------------------

The typical integration flow has two distinct phases:

Configuration Phase
~~~~~~~~~~~~~~~~~~~

During config flow, use asset-aware mode to discover entities.

.. code-block:: python

   # 1. Login via REST
   await api_client.login(email, password)

   # 2. Select object and modules
   objects = await api_client.get_objects()
   modules = await api_client.get_modules(object_id)

   # 3. Enable asset-aware mode
   param_store = ParamStore()
   await param_store.init_with_api(api_client)

   # 4. Fetch initial parameters
   params = await api_client.get_parameters(device_id, module_ids)
   for event in params:
       param_store.upsert(event)

   # 5. Build entity descriptors with metadata
   descriptors = []
   for key in param_store.keys():
       descriptor = {
           "key": key,
           "label": param_store.get_label(key, lang="en"),
           "unit": param_store.get_unit(key),
           "enum_labels": param_store.get_enum_labels(key),
       }
       descriptors.append(descriptor)

.. note::
   No WebSocket connection needed during config flow!

Runtime Phase
~~~~~~~~~~~~~

At runtime, use lightweight mode for best performance.

.. code-block:: python

   # 1. Create gateway and lightweight ParamStore
   gateway = BragerOneGateway(api_client)
   param_store = ParamStore()  # No init_with_api()

   # 2. Subscribe to updates
   async def handle_updates():
       async for event in gateway.event_bus.subscribe():
           param_store.upsert(event)
           # Trigger HA entity updates

   # 3. Start gateway (connects WS, subscribes, primes)
   await gateway.start(device_id, module_ids)

.. important::
   **After WebSocket reconnect:** Always re-fetch parameters via REST!

   .. code-block:: python

      # On reconnect
      await gateway.subscribe(device_id, module_ids)
      params = await api_client.get_parameters(device_id, module_ids)
      for event in params:
          param_store.upsert(event)

Parameter Format
----------------

Parameters use a structured addressing scheme:

Format
~~~~~~

.. code-block:: text

   P<pool_number>.<channel><index>

   Examples:
   - P4.v1    → Pool 4, value channel, index 1
   - P5.s40   → Pool 5, status channel, index 40
   - P6.u13   → Pool 6, unit channel, index 13

Channels
~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 10 20 70

   * - Channel
     - Name
     - Purpose
   * - ``v``
     - Value
     - Primary reading or setpoint
   * - ``s``
     - Status
     - Binary status bitmask (use bit extraction)
   * - ``u``
     - Unit
     - Unit code or enum index
   * - ``n``
     - Min
     - Minimum allowed value
   * - ``x``
     - Max
     - Maximum allowed value
   * - ``t``
     - Type
     - Data type identifier

.. tip::
   **Extracting status bits:**

   .. code-block:: python

      # P5.s40 holds a bitmask
      status = param_store.get("P5.s40")  # e.g., 0b00001010 = 10

      # Check individual bits
      bit_0 = bool(status & (1 << 0))  # False (pump off)
      bit_1 = bool(status & (1 << 1))  # True (heater on)
      bit_3 = bool(status & (1 << 3))  # True (alarm active)

Entity Naming
-------------

.. code-block:: python

   # Recommended unique_id format for HA entities
   unique_id = f"bragerone_{device_id}_{pool}_{chan}{idx}"

   # For binary sensors from status bits
   unique_id = f"bragerone_{device_id}_{pool}_{chan}{idx}_bit{bit_index}"

   # Examples:
   # - bragerone_ABC123_P4_v1
   # - bragerone_ABC123_P5_s40_bit3

Best Practices
--------------

Logging & Debugging
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Use single-line JSON for logs
   import json
   logger.debug(f"Event: {json.dumps(event.model_dump(), separators=(',', ':'))}")

   # Dump large payloads to files
   with open("param_store.json", "w") as f:
       json.dump(param_store.to_dict(), f, indent=2)

.. tip::
   **CLI debugging flags:**

   - ``--debug`` → Verbose logging
   - ``--raw-ws`` → Show raw WebSocket payloads
   - ``--dump-store`` → Save ParamStore to JSON

Error Handling
~~~~~~~~~~~~~~

.. warning::
   **Never let EventBus consumers crash!**

   .. code-block:: python

      async def safe_consumer():
          async for event in event_bus.subscribe():
              try:
                  await process_event(event)
              except Exception as e:
                  logger.error(f"Event processing failed: {e}", exc_info=True)
                  # Continue processing other events

Performance Tips
~~~~~~~~~~~~~~~~

- **Rate limiting:** Use ``asyncio.Semaphore`` for write operations
- **Retry logic:** Add exponential backoff for REST prime (200/500/800ms)
- **Lightweight mode:** Always use in production runtime
- **Batch updates:** Group entity updates to reduce overhead

Writing Parameters
------------------

Number Values
~~~~~~~~~~~~~

.. code-block:: python

   # Write a new value
   await api_client.set_parameter(
       device_id=device_id,
       pool="P4",
       chan="v",
       idx=1,
       value=22.5
   )

Status Bits
~~~~~~~~~~~

.. code-block:: python

   # Read-modify-write pattern for bits
   current = param_store.get("P5.s40")

   # Set bit 3 to True
   new_value = current | (1 << 3)

   # Set bit 3 to False
   new_value = current & ~(1 << 3)

   # Write back
   await api_client.set_parameter(
       device_id=device_id,
       pool="P5",
       chan="s",
       idx=40,
       value=new_value
   )
