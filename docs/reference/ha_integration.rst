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

Module connectivity
-------------------

Two layers — do not conflate them:

1. **Module ↔ cloud** (SPA ``connectedAt``) — plant gateway reachability. Observe
   and wait when offline; the client cannot repair it.
2. **Library ↔ cloud** (Socket.IO client session) — must be **detectable** and
   **self-healing** (transport reset, reconnect, REST re-prime while down).

Per-module cloud online/offline is **not** on the ParamUpdate EventBus (so existing
``bus.subscribe()`` loops stay typed and unbroken). Use the dedicated gateway API:

.. code-block:: python

   from pybragerone.models.events import CloudSessionConnectivity, ModuleConnectivity

   def on_module(event: ModuleConnectivity) -> None:
       print(event.devid, "online" if event.online else "offline", event.source)

   def on_session(event: CloudSessionConnectivity) -> None:
       print("cloud session", "up" if event.up else "down", event.source)

   gateway.on_module_connectivity(on_module)
   gateway.on_cloud_session(on_session)
   # After start / refresh:
   # gateway.module_online(devid) -> True | False | None
   # gateway.module_connected_at(devid) -> int | None  # REST connectedAt
   # gateway.ws_session_up() -> bool  # library↔cloud Socket.IO
   # gateway.last_param_update_age_s() -> float | None

The gateway primes from ``GET /v1/modules`` (``connectedAt != 0`` means online —
same truthiness check as the SPA card/modal) and listens for the official Socket.IO
push ``app:module:connection:status:changed`` (payload
``{devid: {connectedAt, gateway}}``, applied by Layout / ObjectsLayout in the web
app). The client's own Socket.IO session is tracked separately and does **not**
force modules offline (SPA parity). A background REST poll (default 60s;
``connectivity_poll_interval=0`` disables it) continues even while WS is down.
Failed or empty ``get_modules`` responses never wipe every module to offline.
Degraded rows (empty ``gateway``, null ``connectedAt``) parse as offline
(``connectedAt == 0``) instead of being dropped from the listing.

While the client's Socket.IO session is down, the same poll **REST-primes**
parameters so Home Assistant entities keep receiving ``ParamUpdate`` events (WS
deltas only resume after reconnect + resubscribe + prime). An Engine.IO abort
that skips the Socket.IO disconnect callback still marks the session down before
reconnect, so that REST-prime path can run. If the session still reports up but
no **live** ``ParamUpdate`` is published for 180s (zombie transport), the poll REST-primes
anyway; after two consecutive zombie primes it forces a hard Socket.IO restart
(SPA parity: ``connect`` → ``ModulesService.connect`` + REST parameters), **awaiting**
namespace join + ``resubscribe()`` so module binding completes. After repeated failed
hard restarts it hard-resets the Socket.IO client, then rebuilds ``RealtimeManager``
(with forced re-login) and an exponential recovery cooldown (REST primes continue).
A subscribed module returning online while still zombie clears the cooldown and
triggers recovery immediately. Recovery is skipped
while every subscribed module is known offline. Numeric
event ``22`` (``SIGMA_NETWORK_EVENT_MODULE_MEMORY_UPDATED``) also triggers a
per-module REST prime. ``BragerOneGateway.last_param_update_age_s()`` returns that gap for
diagnostics.

Connection **labels** are not hardcoded: resolve them from the live ``module``
i18n namespace (same keys the SPA uses):

.. code-block:: python

   from pybragerone.models.i18n import I18nResolver

   labels = await I18nResolver(assets).resolve_module_connection_labels(lang="pl")
   # labels["serverConnection"], labels["connection.status"],
   # labels["connection.connected"], labels["connection.notConnected"], ...

Stable grouping key for the HA connection child device: ``module.connection``
(i18n namespace path — **not** a menu-router route).

.. important::
   **After WebSocket reconnect:** Always re-fetch parameters via REST!

   .. code-block:: python

      # On reconnect, the gateway performs modules.connect + subscribe + prime again.
      # Make sure your ParamStore subscriber is active before starting the gateway.

Entity Naming
-------------

Route vs parameter visibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Everyday web-UI side-menu routes may be gated separately from individual
parameters:

- ``ParamResolver.route_visibility_diagnostics`` — static SPA route gates
  (installer denylist, ``isVisibleOnSideMenu``, ``displayDropdown`` leftovers).
- ``ParamResolver.parameter_visibility_diagnostics`` — per-parameter status bits
  (``INVISIBLE``, ``DEVICE_AVAILABLE``).

Static menu shells (e.g. ``MAINMENU_STREFY_CZASOWE`` / path ``timezones``) load
parameter tokens from ``deviceMenu/static/<path>.ts`` chunks referenced in
``index-*.js``. Use ``LiveAssetsCatalog.discover_static_route_tokens`` and pass
``static_route_symbols`` into ``build_panel_groups_from_menu`` (or call
``build_panel_groups`` with a primed ``ParamStore`` so overlays are resolved
automatically).

.. code-block:: python

   # Recommended unique_id format for HA entities
   unique_id = f"bragerone_{device_id}_{pool}_{chan}{idx}"

   # For binary sensors from status bits
   unique_id = f"bragerone_{device_id}_{pool}_{chan}{idx}_bit{bit_index}"

   # Examples:
   # - bragerone_ABC123_P4_v1
   # - bragerone_ABC123_P5_s40_bit3
