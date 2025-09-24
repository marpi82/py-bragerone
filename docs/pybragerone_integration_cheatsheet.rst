
=============================
pybragerone – Quick Cheatsheet
=============================

**Date:** 2025-09-20

.. contents:: :local:

TL;DR
=====

- **Prime via REST is mandatory** at startup and after WS reconnect.
- **Runtime** uses **ParamStore** (light, key→value) + EventBus.
- **Config/Reconfigure** uses **StateStore** (rich model + meta) to build entity descriptors.
- WebSocket does **not** provide a snapshot; always re-prime after resubscribe.

Key Objects
===========

EventBus
--------

- Multicast with per-subscriber queues (FIFO).
- ``publish(ParamUpdate)`` → delivered to *all* subscribers.
- No history replay; subscribe **before** prime if you need those events.

ParamUpdate
-----------

- Key fields: ``devid``, ``pool`` (e.g. ``"P4"``), ``chan`` (``"v" / "s" / "u"``), ``idx`` (int)
- ``value`` – real value or ``None`` if missing
- ``meta`` – dict with extra info (timestamps, ``storable``, averages, ...)

Stores
======

ParamStore (runtime)
--------------------

- Holds only **real values** (meta-only events ignored).
- Flatten format: ``{"P4.v1": 20, "P5.s40": 1, ...}``.
- Use in HA entities:
  - Sensor/Number: ``param_store.get("P4.v1")``
  - Binary (bit): ``bool(param_store.get("P5.s40") & (1 << bit))``

StateStore (config-time)
------------------------

- Rich Pydantic models per-devid/per-family + meta.
- Used to build **entity descriptors** (label/unit/enum/min/max/step/bit).
- ``flatten()`` safe – does not overwrite main fields with ``None`` from channels.

HA Integration Flow
===================

Config Flow (no WS required)
----------------------------

1. REST login; choose ``object_id`` + modules.
2. REST **prime parameters** → ingest into **StateStore**.
3. Parse **parameterSchemas** + i18n (labels/units/enums).
4. Build and store **descriptors** in ``config_entry.data``.

Runtime
-------

1. Start Gateway + **ParamStore** subscriber(s).
2. WS connect → ``modules.connect`` → **subscribe** (``parameters:listen`` + ``activity:quantity:listen``).
3. **REST prime** → ingest to EventBus → ParamStore filled.
4. Entities update on ParamUpdate matches.

Reconnect
---------

- Repeat: subscribe → **prime via REST** → ingest → continue.

Parameter Semantics
===================

- Key format: ``P<n>.<chan><idx>`` e.g. ``P4.v1``, ``P5.s40``, ``P6.u13``.
- Channels:
  - ``v`` value, ``s`` status (bitmask), ``u`` unit/enum, ``n`` min, ``x`` max, ``t`` type.
- Meta-only entries (e.g. ``{"storable":1}``) → **not** values.

Entity Guidelines
=================

- **unique_id**: ``bragerone_{devid}_{pool}_{chan}{idx}`` (``_bitN`` for bit entities).
- **label/unit**: from i18n; enum index → enum text.
- Writes:
  - Numbers: POST new ``v``.
  - Bits: read mask, set/clear bit, POST new ``s``.

Operational Tips
================

- Use single-line JSON previews for logs; dump large payloads to files.
- Catch and log exceptions in store consumers; **never** let tasks die.
- Add small retry/backoff for prime (e.g. 200/500/800 ms).
- Rate-limit write commands with a small semaphore.

CLI Hints
=========

- ``--debug`` – verbose logs
- ``--raw-ws`` – raw WebSocket payloads
- ``--dump-store`` – save ``param_store.json`` and ``state_store.json``
- Typical dev loop:
  1) login & select object/modules
  2) start gateway (subscribe → prime)
  3) watch ``↺ P*.v* = ...`` or dump stores

.. note::
   Updated on 2025-09-21 21:44 UTC

======================
Parsers + HA Glue TL;DR
======================

Build unified model
-------------------

::

  pybragerconnect-glue --module-code FTTCTBSLCE \
    --menu module.menu-FTTCTBSLCE.js \
    --mappings parametry/PARAM_0.js parametry/PARAM_4.js ... \
    --i18n-parameters i18n/parameters-pl.js \
    --i18n-units i18n/units-pl.js \
    --out module_model.json

Generate HA blueprint
---------------------

::

  pybragerconnect-ha --module-code FTTCTBSLCE \
    --menu module.menu-FTTCTBSLCE.js \
    --mappings parametry/PARAM_0.js parametry/PARAM_4.js ... \
    --i18n-parameters i18n/parameters-pl.js \
    --i18n-units i18n/units-pl.js \
    --out ha_blueprint.json

Entities mapping (rules of thumb)
---------------------------------

- WRITE + enum(2) → switch
- WRITE + enum(>2) → select
- WRITE + no enum → number
- READ-only + value → sensor
- any status bit (``s``) → binary_sensor

Attributes stored in entities
-----------------------------

- ``brager_value_ref: {{group, use:"v", number}}``
- ``brager_unit_ref:  {{group, use:"u", number}}``
- ``brager_status_ref:{{group, use:"s", number, bit}}``

Runtime
-------

- Setup uses full metadata (sections/labels/units/enums).
- After setup: only WS updates → ``ParamStore`` (fast path).
- ``StateStore`` optional at runtime.
