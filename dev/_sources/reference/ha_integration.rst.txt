Home Assistant Integration
==========================

The typical integration flow has two distinct phases:

Configuration Phase
-------------------

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
-------------

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
