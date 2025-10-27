Core Components
===============

EventBus
--------

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
------------------

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
