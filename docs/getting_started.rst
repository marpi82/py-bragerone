
Getting Started
===============

.. image:: https://img.shields.io/badge/status-Alpha-yellow
   :alt: Alpha status
.. image:: https://img.shields.io/badge/python-3.13.2+-blue
   :alt: Python 3.13.2+
.. image:: https://img.shields.io/badge/license-MIT-green
   :alt: MIT License

**pybragerone** is an alpha-stage Python library for integrating with **BragerOne**.
It provides an async REST client, a Socket.IO realtime client, an internal event bus,
and **ParamStore** (with optional rich metadata via LiveAssetsCatalog) so you can
build efficient automations and a clean Home Assistant integration.

Highlights
----------

- **REST (httpx)**: login, user & permissions, objects, modules, ``modules.connect``,
  snapshot endpoints (``modules/parameters``, ``modules/activity/quantity``).
- **Realtime (python-socketio)**: namespace ``/ws``; subscribes to
  ``app:modules:parameters:listen`` and ``app:modules:activity:quantity:listen``.
- **EventBus**: in-process async fan-out of structured updates.
- **ParamStore**: lightweight key→value view (e.g. ``"P4.v1" -> 20.5``) for runtime.
  - Optional: ``init_with_api()`` enables rich metadata (i18n labels, units, enums) via LiveAssetsCatalog.
- **Online asset parsers**: i18n translations, parameter mappings, ``module.menu`` features.
- **CLI**: quick diagnostics, raw WS debug, and snapshot prime helpers.
- **HA-ready**: designed so HA runtime relies on ParamStore; config flow uses asset catalog.

Architecture
------------

The library consists of several key components working together:

.. mermaid::

   flowchart TB
     subgraph cloud["☁️ BragerOne Cloud"]
       REST["/v1/* REST API"]
       WS["/socket.io WebSocket"]
     end

     subgraph pybragerone["📦 pybragerone Package"]
       direction TB
       API["🔌 BragerOneApiClient<br/>(httpx)"]
       REALTIME["⚡ RealtimeManager<br/>(Socket.IO)"]
       GATEWAY["🚪 BragerOneGateway<br/>(orchestration)"]
       EVENTBUS["📡 EventBus<br/>(pub/sub)"]
       STORE["💾 ParamStore<br/>(key→value)"]
       CATALOG["📚 LiveAssetsCatalog<br/>(metadata)"]

       API --> GATEWAY
       REALTIME --> GATEWAY
       GATEWAY --> EVENTBUS
       EVENTBUS --> STORE
       API -.metadata.-> CATALOG
       CATALOG -.labels/units.-> STORE
     end

     subgraph integration["🏠 Home Assistant"]
       CONFIG["Config Flow<br/>(uses metadata)"]
       RUNTIME["Runtime<br/>(lightweight mode)"]
     end

     REST --> API
     WS --> REALTIME
     STORE --> CONFIG
     STORE --> RUNTIME
     CATALOG --> CONFIG

.. note::
   **Data Flow:**

   1. **REST API** provides initial state and snapshots
   2. **WebSocket** delivers real-time updates
   3. **Gateway** orchestrates connection and subscriptions
   4. **EventBus** broadcasts updates to all subscribers
   5. **ParamStore** maintains current parameter values

Version & Python
----------------

- **Alpha**: APIs may still evolve.
- **Python**: **3.13.2+** (aligned with Home Assistant 2025).

Installation
------------

Stable (PyPI, when published)::

  pip install pybragerone

Pre-release (TestPyPI)::

  pip install -i https://test.pypi.org/simple/ pybragerone

Optional extras::

  pip install "pybragerone[cli]"      # CLI with typer, rich, aiofiles
  pip install "pybragerone[keyring]"  # Secure token storage with keyring

Quick Start (CLI)
-----------------

Run the CLI for a guided session (object & module selection, WS link, prime)::

  pybragerone-cli --email YOU@example.com --password "***" --debug

Press ``Ctrl+C`` to stop. Use ``--raw-ws`` for raw payload logging.

Minimal Example – Lightweight (runtime)
---------------------------------------

.. code-block:: python

   import asyncio
   from pybragerone import BragerOneApiClient, BragerOneGateway
   from pybragerone.models.param import ParamStore

   async def main() -> None:
       # Gateway handles API client internally
       gw = BragerOneGateway(
           email="you@example.com",
           password="secret",
           object_id=12345,  # Your object ID
           modules=["ABC123", "DEF456"]  # Your device IDs (devids)
       )

       pstore = ParamStore()
       asyncio.create_task(pstore.run_with_bus(gw.bus))

       async def printer():
           async for upd in gw.bus.subscribe():
               if upd.value is None:
                   continue
               key = f"{upd.pool}.{upd.chan}{upd.idx}"
               print(f"↺ {upd.devid} {key} = {upd.value}")
       asyncio.create_task(printer())

       await gw.start()
       try:
           await asyncio.sleep(60)
       finally:
           await gw.stop()

   if __name__ == "__main__":
       asyncio.run(main())

Advanced Example – With Rich Metadata (config flow)
----------------------------------------------------

.. code-block:: python

   import asyncio
   from pybragerone import BragerOneApiClient, BragerOneGateway
   from pybragerone.models.param import ParamStore

   async def main() -> None:
       # For config flow or when you need i18n/labels/enums
       api = BragerOneApiClient()
       await api.ensure_auth("you@example.com", "secret")

       user = await api.get_user()
       object_id = user.objects[0].id
       modules_resp = await api.get_modules(object_id=object_id)
       devids = [m.devid for m in modules_resp if m.devid]

       pstore = ParamStore()
       pstore.init_with_api(api, lang="pl")  # Enables LiveAssetsCatalog

       gw = BragerOneGateway(
           email="you@example.com",
           password="secret",
           object_id=object_id,
           modules=devids
       )
       asyncio.create_task(pstore.run_with_bus(gw.bus))

       await gw.start()
       try:
           # Now you can use rich metadata methods
           menu = await pstore.get_menu("device123", ["param.edit"])
           print(f"Available parameters: {len(menu.items)}")

           # Get translated label
           label = await pstore.get_label("device123", "P4", 1, "v")
           print(f"Label for P4.v1: {label}")

           await asyncio.sleep(60)
       finally:
           await gw.stop()
           await api.close()

   if __name__ == "__main__":
       asyncio.run(main())

Event Bus & Update Model
------------------------

``ParamUpdate`` carries atomic updates:

- ``devid`` – device code (e.g. ``"FTTCTBSLCE"``)
- ``pool`` – parameter group (``P4``, ``P5``, ...)
- ``chan`` – channel (``v``, ``s``, ``u``, ``n``, ``x``, ...)
- ``idx`` – index within the pool
- ``value`` – parsed value (int/float/str/bool) or ``None`` for meta-only frames
- ``meta`` – timestamps, storable flag, averages, etc.
- ``seq`` – monotonically increasing sequence assigned by the EventBus

Example of flattening parameters (gateway helper)::

  updates = gateway.flatten_parameters(payload)
  for upd in updates:
      print(f"{upd.devid} {upd.pool}.{upd.chan}{upd.idx} = {upd.value}")

ParamStore Details
------------------

**ParamStore** provides two modes of operation:

- **Lightweight mode** (default):
  - Simple key→value storage (e.g. ``"P4.v1" -> 20.5``)
  - Minimal memory footprint
  - Perfect for HA runtime entities & frequent updates

- **Asset-aware mode** (with ``init_with_api()``):
  - Connects to LiveAssetsCatalog for rich metadata
  - Provides i18n labels, units, enums, and visibility rules
  - Used during HA config flow to build entity descriptors
  - Methods: ``get_menu()``, ``get_label()``, ``get_unit()``, etc.

Choose lightweight for runtime performance, asset-aware for config/bootstrap when you need metadata.

Online Asset Parsers
--------------------

pybragerone can resolve labels, units, and visibility rules directly from online assets via LiveAssetsCatalog:

- **i18n JSON**: language packs (e.g. ``.../resources/languages/pl/parameters.json``)
- **parameters bundles**: e.g. ``PARAM_0`` to map pools (``P6.v0/s0/u0/...``)
- **module.menu**: sections, required permission levels, and parameter visibility

Sessions are shared with the REST client, so fetching assets respects authentication and CORS.

Home Assistant Integration
--------------------------

- **Runtime**: subscribe to the EventBus and source states from **ParamStore** (lightweight mode).
- **Config Flow**: enumerate entities and their metadata via **ParamStore** with ``init_with_api()``
  (asset-aware mode provides labels, units, enums).
- **Units mapping**: a helper maps Brager unit codes (or i18n unit text) to HA canonical
  units (e.g. ``°C`` → ``temperature``, ``%`` → ``percentage``).

Security Notes
--------------

- Store and refresh the bearer token responsibly (e.g. OS keyring in real deployments).
- Always pass ``Origin`` and ``Referer`` headers consistent with the official UI.
- Use TLS (HTTPS) for all requests; the realtime client upgrades via the engine automatically.

Troubleshooting
---------------

- **403 Forbidden** on REST requests:
  - check ``Authorization: Bearer <token>``
  - ensure your ``Origin`` and ``Referer`` headers match the UI domain
- **No WS events** after connecting:
  - verify ``modules.connect`` succeeded
  - re-check your namespace SID versus engine SID when passing to ``modules.connect``
- **CORS preflight (OPTIONS)**:
  - required by the browser; not needed when calling from Python unless API enforces it

Development
-----------

- Python **3.13.2+**
- **Ruff** as formatter and linter (``line-length = 100``)
- **mypy --strict** with ``pydantic.mypy`` plugin
- Type hints are shipped (``py.typed``)

Common tasks::

  ruff format
  ruff check src/pybragerone --fix
  mypy src/pybragerone --strict

Release flow (suggestion)::

  1. Bump version in pyproject
  2. Tag & GitHub release
  3. Build:  python -m build
  4. Publish: twine upload dist/*   (or TestPyPI first)

Contributing
------------

Issues and PRs are welcome. Please follow:
- Conventional commits (optional but helpful)
- Keep public methods fully typed & documented (Google docstrings)
- Keep runtime lightweight; push heavy mapping to setup/config-time

License
-------

MIT – see ``LICENSE``.
