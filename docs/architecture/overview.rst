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

.. graphviz::

   digraph overview {
       rankdir=TB;
       node [shape=box, style=filled];

       // External Services
       subgraph cluster_external {
           label="External Services";
           style=filled;
           fillcolor="#e1f5fe";

           Backend [label="BragerOne Backend\n(io.brager.pl)", fillcolor="#e1f5fe"];
       }

       // pybragerone Core
       subgraph cluster_core {
           label="pybragerone Core";
           style=filled;
           fillcolor="#f3e5f5";

           API [label="BragerOneApiClient\n(httpx)", fillcolor="#f3e5f5"];
           Gateway [label="BragerOneGateway", fillcolor="#f3e5f5"];
           Bus [label="EventBus\n(multicast; per-subscriber queues)", fillcolor="#f3e5f5"];
       }

       // Data Layer
       subgraph cluster_store {
           label="Data Layer";
           style=filled;
           fillcolor="#e8f5e8";

           ParamStore [label="ParamStore\n(runtime lightweight)\nOR (config asset-aware)", fillcolor="#e8f5e8"];
           Catalog [label="LiveAssetsCatalog\n(optional; for i18n/metadata)", fillcolor="#e8f5e8"];
       }

       // Consumers
       subgraph cluster_consumer {
           label="Consumers";
           style=filled;
           fillcolor="#fff3e0";

           HA [label="Home Assistant Entities\n(binary_sensor, number, ...)", fillcolor="#fff3e0"];
           Printer [label="Printer\n(optional debug/CLI)", fillcolor="#fff3e0"];
       }

       // Main data flow
       API -> Backend [dir=both, label="REST\nprime parameters", color=blue];
       API -> Gateway [label="WS (socket.io)\nsubscribe", color=darkgreen];
       Backend -> Gateway [label="WS change events", color=red];
       Gateway -> Bus [label="publish()", color=purple];

       // Store connections
       Bus -> ParamStore [color=orange];
       Bus -> Printer [color=orange];

       // Asset catalog (optional)
       API -> Catalog [style=dashed, color=gray];
       Catalog -> ParamStore [style=dashed, color=gray];

       // HA integration
       ParamStore -> HA [color=brown];
       Catalog -> HA [style=dashed, color=gray, label="descriptors built\n(config only)"];
   }

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
