Home Assistant Integration
==========================

The typical integration flow has two distinct phases:

Configuration Phase
-------------------

During config flow, use asset-aware mode to discover entities.

.. code-block:: python

   # 1. Login via REST
   await api_client.ensure_auth(email, password)

   # 2. Select object and modules
   objects = await api_client.get_objects()
   object_id = objects[0].id
   modules_resp = await api_client.get_modules(object_id=object_id)
   module_ids = [str(m.devid or m.id) for m in modules_resp if (m.devid or m.id) is not None]

   # 3. Enable asset-aware resolution
   param_store = ParamStore()
   resolver = ParamResolver.from_api(api=api_client, store=param_store, lang="en")

   # 4. Prime parameters via REST snapshot
   status, payload = await api_client.modules_parameters_prime(module_ids, return_data=True)
   if status in (200, 204) and isinstance(payload, dict):
       param_store.ingest_prime_payload(payload)

      # 5. Build entity descriptors with metadata from assets
      # Pick module permissions + menu id (deviceMenu) from one module; you can merge across modules if needed.
      first = modules_resp[0]
      device_menu = int(first.deviceMenu)
      permissions = list(getattr(first, "permissions", []) or [])
      symbols = await resolver.merge_assets_with_permissions(permissions=permissions, device_menu=device_menu)

      descriptors = []
      for symbol, desc in symbols.items():
         descriptors.append({
            "symbol": symbol,
            "label": desc.get("label"),
            "unit": desc.get("unit"),
         })

.. note::
   No WebSocket connection needed during config flow!

Runtime Phase
-------------

At runtime, use lightweight mode for best performance.

.. code-block:: python

   # 1. Create gateway and lightweight ParamStore
   gateway = BragerOneGateway(api=api_client, object_id=object_id, modules=module_ids)
   param_store = ParamStore()  # runtime-light (storage-only)

   # 2. Subscribe to updates
   async def handle_updates():
       async for event in gateway.bus.subscribe():
           if event.value is None:
               continue
           param_store.upsert(f"{event.pool}.{event.chan}{event.idx}", event.value)
           # Trigger HA entity updates

   # 3. Start gateway (connects WS, subscribes, primes)
   await gateway.start()

.. important::
   **After WebSocket reconnect:** Always re-fetch parameters via REST!

   .. code-block:: python

      # On reconnect, the gateway performs modules.connect + subscribe + prime again.
      # Make sure your ParamStore subscriber is active before starting the gateway.

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
