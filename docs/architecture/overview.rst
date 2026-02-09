Architecture Overview
=====================

``pybragerone`` integrates with the BragerOne backend using a lean runtime architecture.
The key idea is to **prime** the state via REST, then keep it **fresh** via WebSocket deltas.
In HA, we run as light as possible; rich metadata (via LiveAssetsCatalog) is used only at config time.

Core Principles
---------------

- **Prime is mandatory** at startup and after reconnect. WebSocket does **not** provide a snapshot.
- Runtime is **event-driven** with a **multicast EventBus** (per-subscriber queue, FIFO).
- **ParamStore** provides two usage modes:

  - **Lightweight mode** (runtime): Simple key→value store, minimal overhead, ignores meta-only events.
  - **Asset-aware mode** (config): Integration with LiveAssetsCatalog for rich metadata (labels/units/enums).

- Consistent, explicit parameter addressing: ``P<n>.<chan><idx>`` (e.g. ``P4.v1``).
- Minimal coupling between WS flow and HA entities; HA entities rely on immutable references.

High-Level Architecture
-----------------------

.. code-block:: text

   BragerOne Backend (io.brager.pl)
    ^    \
    |     \
    REST     WS deltas
    |        \
   BragerOneApiClient  --->  BragerOneGateway  --->  EventBus  --->  ParamStore (runtime)
      |                                  \                     \
      |                                   \                     ---> Printer/CLI (optional)
      |                                    \
      +--> LiveAssetsCatalog (config only)  --->  ParamStore (asset-aware)
                             \
                            ---> HA entity descriptors (config only)

Data Model & Semantics
----------------------

Parameter Key Format
~~~~~~~~~~~~~~~~~~~~

- ``P<n>.<chan><idx>`` – examples: ``P4.v1``, ``P5.s40``, ``P6.u13``
- Channels:

  - ``v`` – value (primary reading / setpoint)
  - ``s`` – status (bitmask; per-bit entities possible)
  - ``u`` – unit code or enum index
  - ``n`` / ``x`` – min / max
  - ``t`` – type (when present)
  - additional channels may appear; treat them generically

- Status bit handling: read mask from ``P*.s*`` and map a single bit to a binary entity.

Prime Responses
~~~~~~~~~~~~~~~

- ``POST /v1/modules/parameters`` (prime parameters) returns a **full snapshot**.
- ``POST /v1/modules/activity/quantity`` (prime activity) returns activity counters; useful for logs/diagnostics.
- Some entries may be **meta-only** (e.g. ``{"storable": 1}``); treat these as *meta*, not as values.

Event Normalization
~~~~~~~~~~~~~~~~~~~

- Gateway flattens any payload to :class:`ParamUpdate` with **two parts**:

  - ``value`` – actual value or ``None`` if not present
  - ``meta`` – everything else (timestamps, ``storable``, averages, ...)

- :class:`ParamStore` in **lightweight mode** ignores events with ``value is None``.
- :class:`ParamStore` in **asset-aware mode** can process metadata when integrated with LiveAssetsCatalog.
