
pybragerone
===========

.. image:: https://img.shields.io/badge/status-Alpha-yellow
   :alt: Alpha status
.. image:: https://img.shields.io/badge/python-3.13.2+-blue
   :alt: Python 3.13.2+
.. image:: https://img.shields.io/badge/license-MIT-green
   :alt: MIT License

**pybragerone** is an alpha-stage Python library for integrating with **Brager One**.
It provides an async REST client, a Socket.IO realtime client, an internal event bus,
and two complementary state layers (**ParamStore** and **StateStore**) so you can
build efficient automations and a clean Home Assistant integration.

Highlights
----------

- **REST (aiohttp)**: login, user & permissions, objects, modules, ``modules.connect``,
  snapshot endpoints (``modules/parameters``, ``modules/activity/quantity``).
- **Realtime (python-socketio)**: namespace ``/ws``; subscribes to
  ``app:modules:parameters:listen`` and ``app:modules:activity:quantity:listen``.
- **EventBus**: in-process async fan-out of structured updates.
- **ParamStore** (light): key→value view (e.g. ``"P4.v1" -> 20.5``) ideal for runtime.
- **StateStore** (heavy): structured families/channels (``v/s/u/n/x/...``) for setup.
- **Online asset parsers**: i18n translations, parameter mappings, ``module.menu`` features.
- **CLI**: quick diagnostics, raw WS debug, and snapshot prime helpers.
- **HA-ready**: designed so HA runtime relies on ParamStore; config flow uses StateStore.

Architecture
------------

.. mermaid::

   flowchart LR
     subgraph Client["pybragerone package"]
       API["BragerApiClient (REST)"]
       WS["RealtimeManager (Socket.IO)"]
       GW["BragerGateway"]
       BUS["EventBus"]
       PS["ParamStore (light)"]
       SS["StateStore (heavy)"]
       API -- "login, lists, prime" --> GW
       WS -- "connect, subscribe" --> GW
       GW -- "ParamUpdate events" --> BUS
       BUS --> PS
       BUS --> SS
     end
     CLOUD["Brager One Cloud"]
     CLOUD -- "/v1/*" --> API
     CLOUD -- "/socket.io (/ws)" --> WS
     PS -- "runtime" --> HA["Home Assistant integration"]
     SS -- "config flow" --> HA

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

Optional extras (you can define them in ``pyproject.toml``)::

  pip install "pybragerone[core]"
  pip install "pybragerone[cli]"
  pip install "pybragerone[ha]"
  pip install "pybragerone[all]"

Quick Start (CLI)
-----------------

Run the CLI for a guided session (object & module selection, WS link, prime)::

  pybragerone-cli --email YOU@example.com --password "***" --debug

Press ``Ctrl+C`` to stop. Use ``--raw-ws`` for raw payload logging.

Minimal Example – Light Store
-----------------------------

.. code-block:: python

   import asyncio
   from pybragerone.core.client import BragerApiClient
   from pybragerone.gateway import BragerGateway
   from pybragerone.store.param import ParamStore

   async def main() -> None:
       api = BragerApiClient()
       await api.login("you@example.com", "secret")

       user = await api.get_user()
       object_id = user["objects"][0]["id"]
       mods = await api.modules_list(object_id=object_id)
       devids = [m.get("devid") or m.get("code") or str(m["id"]) for m in mods["data"]]

       gw = BragerGateway(api=api, object_id=object_id, modules=devids)

       pstore = ParamStore()
       asyncio.create_task(pstore.run(gw.bus))

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

Minimal Example – Heavy Store
-----------------------------

.. code-block:: python

   import asyncio
   from pybragerone.core.client import BragerApiClient
   from pybragerone.gateway import BragerGateway
   from pybragerone.store.state import StateStore

   async def main() -> None:
       api = BragerApiClient()
       await api.login("you@example.com", "secret")

       user = await api.get_user()
       object_id = user["objects"][0]["id"]
       mods = await api.modules_list(object_id=object_id)
       devids = [m.get("devid") or m.get("code") or str(m["id"]) for m in mods["data"]]

       gw = BragerGateway(api=api, object_id=object_id, modules=devids)

       sstore = StateStore()
       asyncio.create_task(sstore.run(gw.bus))

       def snapshot_logger(_: str, __: dict) -> None:
           flat = sstore.flatten()
           print(f"Prime completed. Devices: {list(flat.keys())}")

       gw.on_snapshot(snapshot_logger)
       await gw.start()
       try:
           await asyncio.sleep(60)
       finally:
           await gw.stop()

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

Example of flattening prime payloads (gateway helper)::

  for key, val, meta, devid in gateway.flatten_parameters(payload):
      # key = "P4.v1", val = 20.5, meta = {...}, devid = "FTTCTBSLCE"

Light vs Heavy Store
--------------------

- **ParamStore**
  - Tracks only the latest value per key (``"P4.v1"``)
  - Tiny memory footprint
  - Perfect for HA runtime entities & frequent updates
- **StateStore**
  - Groups channels into families (e.g. ``P4:1`` → ``v/s/u/n/x``)
  - Keeps metadata for setup/config flows
  - Preferred for building entities with resolved labels/units

Online Asset Parsers
--------------------

pybragerone can resolve labels, units, and visibility rules directly from online assets:

- **i18n JSON**: language packs (e.g. ``.../resources/languages/pl/parameters.json``)
- **parameters bundles**: e.g. ``PARAM_0`` to map pools (``P6.v0/s0/u0/...``)
- **module.menu**: sections, required permission levels, and parameter visibility

Sessions are shared with the REST client, so fetching assets respects authentication and CORS.

Home Assistant Integration
--------------------------

- **Runtime**: subscribe to the EventBus and source states from **ParamStore**.
- **Config Flow**: enumerate entities and their metadata via **StateStore** (labels, units).
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
