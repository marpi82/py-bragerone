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
- In EventBus consumers (e.g., :class:`ParamStore`), **never** let exceptions kill the task:
  catch and log, continue processing.

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
