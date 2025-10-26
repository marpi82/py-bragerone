pybragerone
===========

**Status:** Alpha | Python 3.13.2+ required

Python library for integrating with **Brager One** cloud and realtime API.

Features:
- Async REST client (aiohttp)
- Realtime updates (python-socketio, namespace ``/ws``)
- Event bus for updates
- Two stores:
  - **ParamStore** (lightweight, key→value)
  - **StateStore** (structured, with metadata)
- CLI for diagnostics
- Home Assistant ready

Installation
------------

Stable (PyPI)::

  pip install pybragerone

Pre-release (TestPyPI)::

  pip install -i https://test.pypi.org/simple/ pybragerone

Optional extras::

  pip install "pybragerone[core]"
  pip install "pybragerone[cli]"
  pip install "pybragerone[ha]"
  pip install "pybragerone[all]"

CLI usage
---------

Run the CLI for guided login and WS session::

  pybragerone-cli --email YOU@example.com --password "***"

Examples
--------

ParamStore (light) example::

  import asyncio
  from pybragerone.core.client import BragerApiClient
  from pybragerone.gateway import BragerGateway
  from pybragerone.store.param import ParamStore

  async def main():
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
              if upd.value is not None:
                  print(f"{upd.devid} {upd.pool}.{upd.chan}{upd.idx} = {upd.value}")
      asyncio.create_task(printer())

      await gw.start()
      await asyncio.sleep(30)
      await gw.stop()

  asyncio.run(main())

StateStore (heavy) example::

  import asyncio
  from pybragerone.core.client import BragerApiClient
  from pybragerone.gateway import BragerGateway
  from pybragerone.store.state import StateStore

  async def main():
      api = BragerApiClient()
      await api.login("you@example.com", "secret")
      user = await api.get_user()
      object_id = user["objects"][0]["id"]
      mods = await api.modules_list(object_id=object_id)
      devids = [m.get("devid") or m.get("code") or str(m["id"]) for m in mods["data"]]

      gw = BragerGateway(api=api, object_id=object_id, modules=devids)
      sstore = StateStore()
      asyncio.create_task(sstore.run(gw.bus))

      gw.on_snapshot(lambda *_: print("Prime snapshot ready"))

      await gw.start()
      await asyncio.sleep(30)
      await gw.stop()

  asyncio.run(main())

Documentation
-------------

Full documentation: https://marpi82.github.io/py-bragerone
