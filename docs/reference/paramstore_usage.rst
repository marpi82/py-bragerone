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
-------------------------

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
