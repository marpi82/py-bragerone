pybragerone – Integration Notes
===============================

**Date:** 2025-09-20  
**Scope:** Library architecture (REST/WS, EventBus, stores), Home Assistant integration flow, debugging & ops.  
**Audience:** Developers of :mod:`pybragerone` and HA component maintainers.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
========

``pybragerone`` integrates with the Brager One backend using a lean runtime and a heavier
configuration-time modeling. The key idea is to **prime** the state via REST, then keep it **fresh**
via WebSocket deltas. In HA, we run as light as possible; rich modeling is used only at setup time.

Core Principles
===============

- **Prime is mandatory** at startup and after reconnect. WebSocket does **not** provide a snapshot.
- Runtime is **event-driven** with a **multicast EventBus** (per-subscriber queue, FIFO).
- Two stores with different purposes:

  - :class:`ParamStore` – *lightweight*, key→value, only real values (no meta). Used in HA runtime.
  - :class:`StateStore` – *rich*, per-device/per-family models + meta. Used in config flow/reconfigure.

- Consistent, explicit parameter addressing: ``P<n>.<chan><idx>`` (e.g. ``P4.v1``).
- Minimal coupling between WS flow and HA entities; HA entities rely on immutable references.

Architecture (High-Level)
=========================

.. code-block:: text

   +-------------------+        REST        +-------------------------+
   |   Brager API      |<------------------>|  Brager One backend     |
   |  (aiohttp)        |  prime parameters  |  (io.brager.pl)         |
   +-------------------+        +           +-------------------------+
           |                                ^
           | WS (socket.io) subscribe       | WS change events
           v                                |
   +-------------------+    publish()    +-------------------+
   |   Gateway         | --------------> |    EventBus       |  (multicast; per-subscriber queues)
   +-------------------+                 +-------------------+
           |                                      | \
           |                                      |  \    (debug/CLI)
           |                                      |   \--------------+
           |                                      v                  v
   +-------------------+                 +-------------------+  +-------------------+
   |   ParamStore      |  (runtime)      |    StateStore     |  |    Printer        |
   |   key->value      |                 |  rich model/meta  |  |  (optional)       |
   +-------------------+                 +-------------------+  +-------------------+
           |                                     ^
           v                                     |
   +-------------------------------+             |
   | Home Assistant Entities       |-------------+  (only during config/reconfigure)
   | (binary_sensor, number, ...)  |   descriptors built from StateStore
   +-------------------------------+

Data Model & Semantics
======================

Parameter key format
--------------------

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
---------------

- ``POST /v1/modules/parameters`` (prime parameters) returns a **full snapshot**.
- ``POST /v1/modules/activity/quantity`` (prime activity) returns activity counters; useful for logs/diagnostics.
- Some entries may be **meta-only** (e.g. ``{"storable": 1}``); treat these as *meta*, not as values.

Event Normalization
-------------------

- Gateway flattens any payload to :class:`ParamUpdate` with **two parts**:

  - ``value`` – actual value or ``None`` if not present
  - ``meta`` – everything else (timestamps, ``storable``, averages, ...)

- :class:`ParamStore` **ignores events with ``value is None``**.
- :class:`StateStore` applies ``value`` to the modeled field *only if present*, and merges ``meta`` separately.

Stores
======

ParamStore (runtime)
--------------------

- Responsibilities:

  - Maintain a dictionary ``"P4.v1" -> 20`` (lightweight).
  - Provide :meth:`flatten()` for diagnostics / exporting.
  - **Ignore meta-only updates**.

- Recommended usage in HA entities:

  - Numeric entity: ``native_value = param_store.get("P4.v1")``
  - Binary entity (status-bit): ``is_on = bool(param_store.get("P5.s40") & (1 << bit))``

StateStore (configuration-time)
-------------------------------

- Responsibilities:

  - Keep per-device/per-family rich models (Pydantic v2).
  - Merge meta (min/max/unit/enums/status bits) and i18n (labels/units).
  - Provide :meth:`flatten()` for quick human-oriented dumps (without overriding main fields with ``None``).

- Used in **config flow** and **reconfigure** to build **entity descriptors**:

  - ``unique_id`` (stable): ``bragerone_{devid}_{pool}_{chan}{idx}`` (``_bitN`` for bit entities).
  - ``label`` from i18n (e.g. ``parameters.PARAM_0`` → ``"Nastawa kotła"``).
  - ``unit`` from i18n (e.g. unit code → ``"°C"``) or **enum mapping** when unit is an enum.
  - ``min/max/step`` and status-bit annotations when applicable.
  - Immutable reference: ``pool, chan, idx`` (+ optional ``bit``).

EventBus
========

- Multicast: each subscriber gets its own :class:`asyncio.Queue`; :meth:`publish()` enqueues to **all**.
- FIFO ordering per subscriber.
- No history replay – subscribe **before** prime if you need to observe it.

HA Integration Flow
===================

Config Flow (no WS required)
----------------------------

1. Login via REST; user selects ``object_id`` and desired modules/devices.
2. ``prime parameters`` via REST; ingest into **StateStore** (no WS needed here).
3. Parse ``parameterSchemas`` and i18n assets to enrich metadata.
4. Build **entity descriptors** and store in ``config_entry.data`` (and/or options).

Runtime
-------

1. Create Gateway + **ParamStore** (no StateStore needed at runtime).
2. Connect WS, ``modules.connect``, subscribe (``parameters:listen``, ``activity:quantity:listen``).
3. **Prime via REST** → ingest into EventBus → ParamStore filled immediately.
4. WS delivers deltas; entities update on ``ParamUpdate`` (match by ref).

Reconnect
---------

- On WS reconnect: run the same sequence: subscribe → **prime via REST** → ingest → resume deltas.

Entity Patterns (HA)
====================

- **Sensors/Numbers**:

  - Read: ``param_store.get("P4.v1")``
  - Write (setters): POST to appropriate REST endpoint (group/number inferred from mapping, e.g. from parsed PARAM_*).

- **Binary Sensors** (status bits):

  - Read: mask from ``param_store.get("P5.s40")``
  - Computation: ``bool(mask & (1 << bit))``

- **Enums**:

  - If unit denotes enum: ``value`` is an **index** → map to localized text via enum map.

- **Unique IDs**:

  - ``bragerone_{devid}_{pool}_{chan}{idx}`` (``_bitN`` suffix for bit entities).

REST Endpoints (used by library)
================================

- Auth:
  - ``POST /v1/auth/user`` – login → returns ``accessToken``, ``refreshToken``, ``expiresAt``, and user objects list.
  - ``POST /v1/auth/revoke`` – logout (clean session).
- User & permissions:
  - ``GET /v1/user``, ``GET /v1/user/permissions``
- Objects:
  - ``GET /v1/objects``, ``GET /v1/objects/{id}``, ``GET /v1/objects/{id}/permissions``
- Modules:
  - ``GET /v1/modules?page=...&limit=...&group_id=...`` (module list incl. ``parameterSchemas``)
  - ``POST /v1/modules/connect`` (link WS ``sid`` + modules (+ group_id))
  - ``POST /v1/modules/parameters`` (**prime snapshot**)
  - ``POST /v1/modules/activity/quantity`` (diagnostics/metrics)

Error Handling & Robustness
===========================

- Treat **401/403** as token/session problems → refresh/login and retry once.
- For prime calls add a small retry with backoff (e.g. 200→500→800 ms).
- WS reconnect should **always** re-run prime via REST (no WS snapshot available).
- In EventBus consumers (:mod:`ParamStore`, :mod:`StateStore`), **never** let exceptions kill the task:
  catch and log, continue processing.

Logging & Debugging
===================

- For large JSONs use single-line preview and optional file dump:

  - ``json.dumps(..., separators=(',', ':'), ensure_ascii=False)`` to avoid linebreaks.
  - Save raw prime payloads to files for inspection.

- Useful diagnostics:

  - ``param_store.flatten()`` size and sample keys.
  - ``state_store.flatten()`` sample for a given device.
  - Diff helper between ParamStore and StateStore values, by matching keys.

Security & Headers
==================

- ``Authorization: Bearer <TOKEN>`` for authorized endpoints.
- Browser-origin headers (``Origin``, ``Referer``) sometimes expected by backend; replicate as needed.
- WS connects to ``/socket.io`` with namespace ``/ws``; link via ``/v1/modules/connect`` using the **namespace SID**.

Performance Notes
=================

- Runtime is driven by :class:`ParamStore`; O(1) updates and reads.
- Avoid holding heavy structures in HA runtime; keep enum/unit/i18n in entity attributes saved during config flow.
- Consider a small rate limiter (semaphore) for write commands to respect backend pacing.

Versioning & Types
==================

- Models target **Pydantic v2**.
- ``u`` type may be ``int | str | None`` (unit code or enum name/index), be tolerant in parsing.
- :class:`ParamUpdate` carries ``value`` (or ``None``) **and** ``meta`` (dict).

CLI (Developer Utility)
=======================

- Flags (example suggestions):

  - ``--debug`` – verbose logs
  - ``--raw-ws`` – log raw WS payloads
  - ``--dump-store`` – write ``param_store.json`` and ``state_store.json``

- Typical workflow:

  1. Login (REST), pick ``object_id``/modules.
  2. Start gateway → prime→ingest → observe ``↺ P*.v* = ...`` lines.
  3. (Optional) Dump stores to files to inspect current values.

Future Work / TODO
==================

- Confirm/write endpoints for commands (set ``v`` and toggle ``s`` bits).
- Formalize enum/unit maps from assets (parameterSchemas + i18n) into reusable descriptors.
- Optional persistence cache for descriptors to avoid re-parsing assets on every reconfigure.
- Structured diff tool between prime payloads and live WS states for diagnostics.
- Tests (unit & integration) for flatteners, stores, and gateway reconnect logic.

Appendix: Minimal Interfaces
============================

Event
-----

.. code-block:: python

   @dataclass(frozen=True)
   class ParamUpdate:
       devid: str
       pool: str    # "P4"
       chan: str    # "v" / "s" / "u" / ...
       idx: int     # 1
       value: Any | None
       meta: dict[str, Any] = field(default_factory=dict)
       ts: float = field(default_factory=time.time)
       seq: int = 0

ParamStore
----------

.. code-block:: python

   class ParamStore:
       async def run(self, bus: EventBus) -> None: ...
       def get(self, key: str, default: Any = None) -> Any: ...
       def flatten(self) -> dict[str, Any]: ...

StateStore
----------

.. code-block:: python

   class StateStore:
       async def run(self, bus: EventBus) -> None: ...
       def get_family(self, devid: str, pool: str, idx: int) -> ParamFamilyModel | None: ...
       def flatten(self) -> dict[str, Any]: ...  # safe: does not overwrite v/u/s with None from channels

Gateway
-------

.. code-block:: python

   class BragerGateway:
       bus: EventBus
       modules: list[str]
       object_id: int
       async def start(self) -> None: ...
       async def stop(self) -> None: ...
       async def ingest_prime_parameters(self, data: dict) -> None: ...
       def flatten_parameters(self, payload: dict) -> list[ParamUpdate]: ...

HA Entity Descriptor (example)
------------------------------

.. code-block:: json

   {
     "key": "P4.v1",
     "pool": "P4",
     "chan": "v",
     "idx": 1,
     "bit": null,
     "label": "Nastawa kotła",
     "unit": "°C",
     "enum": null,
     "min": 10,
     "max": 80,
     "step": 0.5,
     "devid": "FTTCTBSLCE"
   }

.. note::
   Updated on 2025-09-21 21:44 UTC

Parsers & Glue: Integration
===========================

This update documents the **parsers package**, the **glue layer** (menu+mappings+i18n),
and the **Home Assistant blueprint generator**.

Contents
--------
- Parsers overview
- Glue layer (build_module_model)
- HA glue (build_ha_blueprint)
- CLI usage
- Runtime flow with ParamStore/StateStore
- Units normalization and HA attributes

Parsers (``pybragerconnect.parsers``)
-------------------------------------

- ``i18n.py``
  Parses any minified JS asset with ``export default {{...}}`` or ``export {{x as default}}``.
  Returns ``dict[str, str]``. Works for *parameters*, *units*, and other i18n files.

- ``mappings.py``
  Parses parameter descriptor bundles (your ``parametry/*.js``). Produces ``ParamDescriptor``
  with references to ``P{{pool}}.{{chan}}{{idx}}`` plus optional bit for ``s`` (status).

- ``module_menu.py``
  Parses ``module.menu-*.js`` into a hierarchical ``MenuTree``. Extracts parameters and
  their operations (READ/WRITE/STATUS) with required permissions (``permissionModule: A.X``).
  Tolerant to minification. Reconstructs sections (``label``/``title``/``name`` and ``t("...")``).

Glue layer
----------

- Function: ``build_module_model(module_code, menu_js, mapping_js_list, i18n_parameters_js, i18n_units_js)``
- Output structure::

    {{
      "module": "<code>",
      "params": {{
        "<KEY>": {{
          "label": "...",                     # i18n label
          "operations": ["READ","WRITE","STATUS"],
          "descriptor": {{ ... ParamDescriptor ... }},
          "unit_labels": ["°C", ...]          # normalized symbols
        }}
      }},
      "sections": {{ ... MenuTree as JSON ... }}
    }}

- Purpose: single source for config flows (full metadata) and for mapping to HA entities.

Home Assistant glue
-------------------

- Function: ``build_ha_blueprint(module_model)``
- Produces a dict with entity groups: ``sensor``, ``number``, ``select``, ``switch``, ``binary_sensor``.
- Encodes references in attributes:
  - ``brager_value_ref: {{group, use:"v", number}}``
  - ``brager_unit_ref:  {{group, use:"u", number}}``
  - ``brager_status_ref:{{group, use:"s", number, bit}}`` (for each status bit)
- Classification:
  - ``WRITE`` + enum(2) → **switch**
  - ``WRITE`` + enum(>2) → **select**
  - ``WRITE`` + no enum → **number** (editable; step used if present; min/max left for runtime)
  - READ-only + value → **sensor**
  - any ``s`` bit → **binary_sensor**

CLI tools
---------

The package includes three CLIs (see ``pyproject-snippet.toml``):

- ``pybragerconnect-parsers`` – debug single parsers.
- ``pybragerconnect-glue`` – menu + mappings + i18n → unified module JSON.
- ``pybragerconnect-ha`` – unified module JSON → HA blueprint entities.

Examples::

  pybragerconnect-parsers --i18n i18n/parameters-pl.js
  pybragerconnect-parsers --bundle parametry/PARAM_0.js
  pybragerconnect-parsers --menu module.menu-FTTCTBSLCE.js --module-code FTTCTBSLCE

  pybragerconnect-glue --module-code FTTCTBSLCE \
      --menu module.menu-FTTCTBSLCE.js \
      --mappings parametry/PARAM_0.js parametry/PARAM_4.js \
      --i18n-parameters i18n/parameters-pl.js \
      --i18n-units i18n/units-pl.js \
      --out module_model.json

  pybragerconnect-ha --module-code FTTCTBSLCE \
      --menu module.menu-FTTCTBSLCE.js \
      --mappings parametry/PARAM_0.js parametry/PARAM_4.js \
      --i18n-parameters i18n/parameters-pl.js \
      --i18n-units i18n/units-pl.js \
      --out ha_blueprint.json

Runtime flow
------------

- Config Flow (heavy): use ``build_module_model`` (sections + labels + units + enum) and
  ``build_ha_blueprint`` to create entities and persist their *brager_* references.
- Runtime (light): update states via ``ParamStore`` (key→value) and WS changes.
  ``StateStore`` can be skipped at runtime to keep it lightweight.

Units normalization
-------------------

- ``normalize_unit`` maps common symbols (``°C``, ``%``, ``kWh``, ``W``…) to HA-friendly strings.
- If deeper integration is needed, map them to ``homeassistant.const`` in the HA integration layer.
