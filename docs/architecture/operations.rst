Operations & Debugging
======================

REST Endpoints
--------------

The library uses the following REST endpoints:

Authentication
~~~~~~~~~~~~~~

- ``POST /v1/auth/user`` – login → returns ``accessToken``, ``refreshToken``, ``expiresAt``, and user objects list.
- ``POST /v1/auth/revoke`` – logout (clean session).

User & Permissions
~~~~~~~~~~~~~~~~~~

- ``GET /v1/user``
- ``GET /v1/user/permissions``

Objects
~~~~~~~

- ``GET /v1/objects``
- ``GET /v1/objects/{id}``
- ``GET /v1/objects/{id}/permissions``

Modules
~~~~~~~

- ``GET /v1/modules?page=...&limit=...&group_id=...`` (module list incl. ``parameterSchemas``)
- ``POST /v1/modules/connect`` (link WS ``sid`` + modules (+ group_id))
- ``POST /v1/modules/parameters`` (**prime snapshot**)
- ``POST /v1/modules/activity/quantity`` (diagnostics/metrics)

Error Handling & Robustness
----------------------------

Best Practices
~~~~~~~~~~~~~~

- Treat **401/403** as token/session problems → refresh/login and retry once.
- For prime calls add a small retry with backoff (e.g. 200→500→800 ms).
- WS reconnect should **always** re-run prime via REST (no WS snapshot available).
- Treat **module↔cloud** (``connectedAt``) and **library↔cloud** (Socket.IO session)
  as separate signals: observe/wait for the former; detect + self-heal the latter
  (``on_cloud_session`` / ``ws_session_up``). Session and module online flips track
  outage duration (``down_since`` / ``down_for_s`` / ``reason`` while down;
  ``last_down_for_s`` / ``last_reason`` after restore) via
  ``cloud_session_outage()`` / ``module_outage(devid)`` — ``reason`` is the
  observation source, not plant diagnostics; zombie / live-stale push health is
  separate.
- While the Socket.IO session is down, the gateway REST-primes on the connectivity
  poll interval so consumers are not stuck on the last WS delta.
- Engine.IO abort (for example aiohttp ``WSMsgType.CLOSED`` / packet type 257) can
  skip the Socket.IO ``disconnect`` callback and deadlock ``disconnect()``. The
  supervisor notifies session-down immediately, bounds leftover teardown, and
  replaces the client if disconnect hangs.
- If no **live** ``ParamUpdate`` arrives for 180s while the session still reports up, the
  same poll REST-primes (zombie socket). After two consecutive zombie primes the
  gateway forces a hard Socket.IO restart (SPA parity: reconnect →
  ``ModulesService.connect`` + REST ``/modules/parameters``), awaiting
  ``resubscribe()`` after the namespace join. After repeated failed hard restarts it
  hard-resets the Socket.IO client; after repeated failed resets it rebuilds
  ``RealtimeManager``. Each of those three stages (hard reconnect, transport recycle,
  and manager rebuild) attempts a fresh login first when credentials are available;
  without a ``creds_provider`` or explicit login args the gateway keeps the current
  access token so reconnect is not left unauthenticated. Transport recycle and
  manager rebuild then back off with an exponential cooldown (REST primes continue).
  A successful hard reconnect does not arm cooldown; an aborted hard reconnect
  (forced re-login failed) does arm cooldown to avoid thrash. After the rebuild cap
  (default 3 rebuilds without live traffic), the gateway enters **REST-only quarantine**
  (default 6 h): WS recovery pauses entirely while REST primes continue. Quarantine
  is cleared by a live ``ParamUpdate`` (``_touch_param_publish(live=True)``) or a
  module-online recovery path. If a subscribed module returns online while still
  zombie, cooldown or quarantine is cleared and recovery runs immediately
  (failed auth/resubscribe re-arms cooldown). Recovery is
  skipped while every subscribed module is known offline.
- ``modules.connect`` caches only the successful body **shape** (``wsid`` vs ``sid``,
  optional ``group_id``) — never a stale SID. After a WS reconnect the gateway
  always posts the **current** namespace SID. Field logs showed that caching the
  entire body (including the SID) could silently re-bind the old dead session while
  the new socket received no deltas.
- ``resubscribe()`` is serialized with ``asyncio.Lock`` and deduped per namespace SID
  (``_bound_ns_sid``). This prevents races between the spawned ``on_connected``
  callback and the zombie recovery ``await resubscribe()``.
  Numeric Socket.IO event ``22`` (``SIGMA_NETWORK_EVENT_MODULE_MEMORY_UPDATED``)
  also REST-primes that module. ``last_param_update_age_s()`` and
  ``last_live_param_update_age_s()`` expose the gaps for diagnostics.
- In EventBus consumers (e.g., :class:`ParamStore`), **never** let exceptions kill the task:
  catch and log, continue processing.

Gateway package layout
~~~~~~~~~~~~~~~~~~~~~~

``BragerOneGateway`` remains the public facade (``from pybragerone import BragerOneGateway``).
Internally the implementation lives under ``pybragerone.gateway``:

- ``_gateway.py`` — lifecycle (``start`` / ``stop``), EventBus wiring, ingest / WS dispatch
- ``connectivity.py`` — module↔cloud and library↔cloud session flips, outage snapshots, REST poll
- ``session.py`` — ``resubscribe`` / SID bind, REST prime orchestration
- ``recovery.py`` — zombie ladder, cooldown, quarantine, module-online recovery
- ``helpers.py`` / ``protocols.py`` — pure helpers and client Protocols

Behavior is unchanged; the split is for reviewability and focused tests.

Logging & Debugging
-------------------

JSON Formatting
~~~~~~~~~~~~~~~

For large JSONs use single-line preview and optional file dump:

.. code-block:: python

   # Single-line compact format
   json.dumps(..., separators=(',', ':'), ensure_ascii=False)

   # Save raw prime payloads to files for inspection
   with open("prime_payload.json", "w") as f:
       json.dump(payload, f, indent=2)

Useful Diagnostics
~~~~~~~~~~~~~~~~~~

- ``param_store.flatten()`` size and sample keys.
- Compare values between different parameter families using ParamStore keys.

Security & Headers
------------------

- ``Authorization: Bearer <TOKEN>`` for authorized endpoints.
- Browser-origin headers (``Origin``, ``Referer``) sometimes expected by backend; replicate as needed.
- WS connects to ``/socket.io`` with namespace ``/ws``; link via ``/v1/modules/connect`` using the **namespace SID**.

Performance Notes
-----------------

- Runtime is driven by :class:`ParamStore`; O(1) updates and reads.
- Avoid holding heavy structures in HA runtime; keep enum/unit/i18n in entity attributes saved during config flow.
- Consider a small rate limiter (semaphore) for write commands to respect backend pacing.

Versioning & Types
------------------

- Models target **Pydantic v2**.
- ``u`` type may be ``int | str | None`` (unit code or enum name/index), be tolerant in parsing.
- :class:`ParamUpdate` carries ``value`` (or ``None``) **and** ``meta`` (dict).

CLI (Developer Utility)
-----------------------

Flags
~~~~~

Example suggestions:

- ``--debug`` – verbose logs
- ``--raw-ws`` – log raw WS payloads
- ``--dump-store`` – write ``param_store.json`` and ``state_store.json``

Typical Workflow
~~~~~~~~~~~~~~~~

1. Login (REST), pick ``object_id``/modules.
2. Start gateway → prime→ingest → observe ``↺ P*.v* = ...`` lines.
3. (Optional) Dump stores to files to inspect current values.

CLI Tools
~~~~~~~~~

The package includes three CLIs:

- ``pybragerone-cli`` – Interactive gateway session
- ``pybragerconnect-parsers`` – Debug single parsers
- ``pybragerconnect-glue`` – Menu + mappings + i18n → unified module JSON
- ``pybragerconnect-ha`` – Unified module JSON → HA blueprint entities

Examples:

.. code-block:: bash

   # Parser debugging
   pybragerconnect-parsers --i18n i18n/parameters-pl.js
   pybragerconnect-parsers --bundle parametry/PARAM_0.js
   pybragerconnect-parsers --menu module.menu-FTTCTBSLCE.js --module-code FTTCTBSLCE

   # Build module model
   pybragerconnect-glue --module-code FTTCTBSLCE \
       --menu module.menu-FTTCTBSLCE.js \
       --mappings parametry/PARAM_0.js parametry/PARAM_4.js \
       --i18n-parameters i18n/parameters-pl.js \
       --i18n-units i18n/units-pl.js \
       --out module_model.json

   # Generate HA blueprint
   pybragerconnect-ha --module-code FTTCTBSLCE \
       --menu module.menu-FTTCTBSLCE.js \
       --mappings parametry/PARAM_0.js parametry/PARAM_4.js \
       --i18n-parameters i18n/parameters-pl.js \
       --i18n-units i18n/units-pl.js \
       --out ha_blueprint.json

Future Work / TODO
------------------

- Confirm/write endpoints for commands (set ``v`` and toggle ``s`` bits).
- Formalize enum/unit maps from assets (parameterSchemas + i18n) into reusable descriptors.
- Optional persistence cache for descriptors to avoid re-parsing assets on every reconfigure.
- Structured diff tool between prime payloads and live WS states for diagnostics.
- Tests (unit & integration) for flatteners, stores, and gateway reconnect logic.
