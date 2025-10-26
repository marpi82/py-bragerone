pybragerone
===========

.. image:: https://img.shields.io/github/v/tag/marpi82/py-bragerone?label=version&color=blue
   :target: https://github.com/marpi82/py-bragerone/tags
   :alt: Latest Tag

.. image:: https://img.shields.io/pypi/v/pybragerone?color=blue
   :target: https://pypi.org/project/pybragerone/
   :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/pybragerone
   :target: https://pypi.org/project/pybragerone/
   :alt: Python Versions

.. image:: https://img.shields.io/github/license/marpi82/py-bragerone?color=green
   :target: https://github.com/marpi82/py-bragerone/blob/main/LICENSE
   :alt: License

.. image:: https://img.shields.io/github/actions/workflow/status/marpi82/py-bragerone/ci.yml?branch=main&label=CI
   :target: https://github.com/marpi82/py-bragerone/actions/workflows/ci.yml
   :alt: CI Status

.. image:: https://img.shields.io/github/actions/workflow/status/marpi82/py-bragerone/codeql.yml?branch=main&label=CodeQL
   :target: https://github.com/marpi82/py-bragerone/security/code-scanning
   :alt: CodeQL Status

.. image:: https://img.shields.io/github/actions/workflow/status/marpi82/py-bragerone/docs.yml?branch=main&label=docs
   :target: https://github.com/marpi82/py-bragerone/actions/workflows/docs.yml
   :alt: Docs Status

.. image:: https://img.shields.io/badge/docs-GitHub%20Pages-blue
   :target: https://marpi82.github.io/py-bragerone/
   :alt: Documentation

.. image:: https://img.shields.io/badge/code%20style-ruff-000000.svg
   :target: https://github.com/astral-sh/ruff
   :alt: Code Style: Ruff

.. image:: https://img.shields.io/badge/type%20checked-mypy-blue.svg
   :target: https://github.com/python/mypy
   :alt: Type Checked: mypy

.. image:: https://img.shields.io/badge/security-bandit-yellow.svg
   :target: https://github.com/PyCQA/bandit
   :alt: Security: Bandit

.. image:: https://img.shields.io/github/actions/workflow/status/marpi82/py-bragerone/release.yml?label=release
   :target: https://github.com/marpi82/py-bragerone/actions/workflows/release.yml
   :alt: Release Status

.. image:: https://img.shields.io/github/last-commit/marpi82/py-bragerone
   :target: https://github.com/marpi82/py-bragerone/commits/main
   :alt: Last Commit

.. image:: https://img.shields.io/github/repo-size/marpi82/py-bragerone
   :target: https://github.com/marpi82/py-bragerone
   :alt: Repo Size

.. image:: https://img.shields.io/pypi/dm/pybragerone?color=blue
   :target: https://pypi.org/project/pybragerone/
   :alt: PyPI Downloads

----

**Status:** Alpha | Python 3.13.2+ required

Python library for integrating with **Brager One** cloud and realtime API.

Features:
- Async REST client (httpx, not aiohttp)
- Realtime updates (python-socketio, namespace ``/ws``)
- Event bus for updates
- **ParamStore** (lightweight, key→value with optional rich metadata via LiveAssetsCatalog)
- CLI for diagnostics
- Home Assistant ready

Installation
------------

Stable (PyPI)::

  pip install pybragerone

Pre-release (TestPyPI)::

  pip install -i https://test.pypi.org/simple/ pybragerone

Optional extras::

  pip install "pybragerone[cli]"      # CLI with typer, rich, aiofiles
  pip install "pybragerone[keyring]"  # Secure token storage with keyring

CLI usage
---------

Run the CLI for guided login and WS session::

  pybragerone-cli --email YOU@example.com --password "***"

Examples
--------

ParamStore (lightweight) example::

  import asyncio
  from pybragerone import BragerOneApiClient, BragerOneGateway
  from pybragerone.models.param import ParamStore

  async def main():
      # Gateway handles API client internally
      gw = BragerOneGateway(
          email="you@example.com",
          password="secret",
          object_id=12345,  # Your object ID
          modules=["ABC123", "DEF456"]  # Your device IDs
      )

      pstore = ParamStore()
      asyncio.create_task(pstore.run_with_bus(gw.bus))

      async def printer():
          async for upd in gw.bus.subscribe():
              if upd.value is not None:
                  print(f"{upd.devid} {upd.pool}.{upd.chan}{upd.idx} = {upd.value}")
      asyncio.create_task(printer())

      await gw.start()
      try:
          await asyncio.sleep(30)
      finally:
          await gw.stop()

  asyncio.run(main())

Advanced: Using ParamStore with API for rich metadata::

  import asyncio
  from pybragerone import BragerOneApiClient, BragerOneGateway
  from pybragerone.models.param import ParamStore

  async def main():
      # For config flow or when you need i18n/labels
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
          # Now you can use pstore.get_menu(), get_label(), etc.
          menu = await pstore.get_menu("device123", ["param.edit"])
          print(f"Available parameters: {len(menu.items)}")
          await asyncio.sleep(30)
      finally:
          await gw.stop()
          await api.close()

  await asyncio.sleep(30)
      finally:
          await gw.stop()
          await api.close()

  asyncio.run(main())

Documentation
-------------

Full documentation: https://marpi82.github.io/py-bragerone

Documentation
-------------

Full documentation: https://marpi82.github.io/py-bragerone
