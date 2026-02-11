Architecture Overview
=====================

``pybragerone`` integrates with the BragerOne backend using a lean runtime architecture.
The key idea is to **prime** the state via REST, then keep it **fresh** via WebSocket deltas.
In HA, we run as light as possible; rich metadata (via LiveAssetsCatalog) is used only at config time.

Core Principles
---------------

- **Prime is mandatory** at startup and after reconnect. WebSocket does **not** provide a snapshot.
- Runtime is **event-driven** with a **multicast EventBus** (per-subscriber queue, FIFO).

- **ParamStore** is runtime-light and stores raw parameter values only.
- **ParamResolver** (config/CLI) uses LiveAssetsCatalog to resolve rich metadata (labels/units/enums/menu/computed STATUS)
  without burdening HA runtime.

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
    +--> LiveAssetsCatalog (config only)  --->  ParamResolver (config/CLI) ---> ParamStore (runtime values)
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

- :class:`ParamStore` ignores events with ``value is None`` (meta-only frames).
- Asset-driven metadata and discovery are handled by :class:`ParamResolver` (LiveAssetsCatalog-backed).
