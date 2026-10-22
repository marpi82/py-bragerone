Core Components
===============

EventBus
--------

``EventBus.subscribe()`` stays **ParamUpdate-only**: multicast fan-out of
parameter deltas for ``ParamStore`` / Home Assistant parameter entities
(per-subscriber queue, FIFO). Additive typed channels are available via
``subscribe_channel(*BusChannel)`` / ``publish_event`` (#386 Phase C / #408 / #409):

- ``MODULE_CONNECTIVITY`` — module ↔ cloud (SPA ``connectedAt``)
- ``CLOUD_SESSION`` — library ↔ cloud Socket.IO session
- ``LIVE_PUSH`` — live push health (zombie)
- ``ALARM_QUANTITY`` — alarm badge quantity
- ``ALARM_FEED`` / ``ACTIVITY_FEED`` — list invalidate (re-fetch from REST)

Gateway ``on_*`` callbacks remain as a compatibility path; the gateway
**dual-writes** the same dataclasses to channels and callbacks.

Alarm/activity **row lists** stay REST; Socket.IO only signals that a refresh is
needed. See :doc:`ha_integration` for the HA-facing boundary.

.. code-block:: python

   from pybragerone.models.events import BusChannel, EventBus, ModuleConnectivity, ParamUpdate

   event_bus = EventBus()

   # ParamUpdate path (unchanged)
   async for event in event_bus.subscribe():
       print(f"Parameter {event.pool}.{event.chan}{event.idx} = {event.value}")

   # Additive channels
   async for event in event_bus.subscribe_channel(BusChannel.MODULE_CONNECTIVITY):
       assert isinstance(event, ModuleConnectivity)
       print(event.devid, event.online)

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
