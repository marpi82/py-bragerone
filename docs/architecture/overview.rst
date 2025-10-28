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

.. mermaid::

   graph TB
       subgraph "External Services"
           Backend["🌐 BragerOne backend<br/>(io.brager.pl)"]
       end

       subgraph "pybragerone Core"
           API["📡 BragerOneApiClient<br/>(httpx)"]
           Gateway["🚪 BragerOneGateway"]
           Bus["📢 EventBus<br/>(multicast; per-subscriber queues)"]
       end

       subgraph "Data Layer"
           ParamStore["💾 ParamStore<br/>(runtime lightweight)<br/>OR (config asset-aware)"]
           Catalog["📋 LiveAssetsCatalog<br/>(optional; for i18n/metadata)"]
       end

       subgraph "Consumers"
           HA["🏠 Home Assistant Entities<br/>(binary_sensor, number, ...)"]
           Printer["🖨️ Printer<br/>(optional debug/CLI)"]
       end

       %% Main data flow
       API <-->|"REST<br/>prime parameters"| Backend
       API -->|"WS (socket.io)<br/>subscribe"| Gateway
       Backend -->|"WS change events"| Gateway
       Gateway -->|"publish()"| Bus

       %% Store connections
       Bus --> ParamStore
       Bus --> Printer

       %% Asset catalog (optional)
       API -.-> Catalog
       Catalog -.-> ParamStore

       %% HA integration
       ParamStore --> HA
       Catalog -.->|"descriptors built<br/>(config only)"| HA

       %% Styling
       classDef external fill:#e1f5fe
       classDef core fill:#f3e5f5
       classDef store fill:#e8f5e8
       classDef consumer fill:#fff3e0

       class Backend external
       class API,Gateway,Bus core
       class ParamStore,Catalog store
       class HA,Printer consumer

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
