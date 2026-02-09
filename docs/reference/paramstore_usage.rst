ParamStore Usage
================

Lightweight Mode (Runtime)
--------------------------

For production use, lightweight mode provides fast access to parameter values.

.. code-block:: python

   from pybragerone.models.param import ParamStore

   # Create store
   param_store = ParamStore()

   # Subscribe to EventBus
   async for event in event_bus.subscribe():
         if event.value is None:
            continue
         param_store.upsert(f"{event.pool}.{event.chan}{event.idx}", event.value)

   # Read values
   fam = param_store.get_family("P4", 1)
   temperature = fam.value if fam else None
   status_fam = param_store.get_family("P5", 40)
   status = status_fam.status_raw if status_fam else 0

.. note::
   **Binary sensor pattern** for status bits:

   .. code-block:: python

      status_fam = param_store.get_family("P5", 40)
      status_value = status_fam.status_raw if status_fam else 0
      bit_index = 3
      is_active = bool(status_value & (1 << bit_index))

Asset-Aware Mode (Setup)
-------------------------

For config flow and entity discovery, enable rich metadata support.

.. code-block:: python

   # Initialize with API client
   param_store.init_with_api(api_client, lang="en")

   # Access metadata
   label = await param_store.resolve_label("PARAM_0")
   mapping = await param_store.get_param_mapping("PARAM_0")
   print(f"label={label} mapping={mapping}")

.. warning::
   Asset-aware mode requires fetching JavaScript assets from BragerOne web app.
   Use only during setup, not in production runtime!
