Core Components
===============

EventBus
--------

The EventBus is **ParamUpdate-only**: multicast fan-out of parameter deltas for
``ParamStore`` / Home Assistant parameter entities (per-subscriber queue, FIFO).

Non-parameter signals use dedicated gateway callbacks instead (so typed
``async for`` subscribers stay unbroken):

- module ↔ cloud connectivity — ``on_module_connectivity``
- library ↔ cloud Socket.IO session — ``on_cloud_session``
- live push health (zombie) — ``on_live_push``
- alarm badge quantity — ``on_alarm_quantity``

Alarm/activity **row lists** stay REST; a future typed multi-event bus is tracked
under GitHub issue #386 (Phase C) and must not break today's ParamUpdate loops.
See :doc:`ha_integration` for the HA-facing boundary.

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
