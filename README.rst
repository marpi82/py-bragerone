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

Python library for integrating with **BragerOne** cloud and realtime API.

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

Development Dependencies
------------------------

For building documentation with architectural diagrams::

  # Ubuntu/Debian
  sudo apt-get install graphviz

  # macOS
  brew install graphviz

  # Windows (via Chocolatey)
  choco install graphviz

CLI usage
---------

Run the CLI for guided login and WS session::

  pybragerone-cli --email YOU@example.com --password "***"

Examples
--------

Basic login and device listing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Minimal async example showing login and listing objects/modules:

.. code-block:: python

   import asyncio
   import os
   from pybragerone.api import BragerOneApiClient

   async def main() -> None:
       email = os.getenv("PYBO_EMAIL", "user@example.com")
       password = os.getenv("PYBO_PASSWORD", "password")
       client = BragerOneApiClient()
       try:
           print(f"Logging in as {email}...")
           await client.ensure_auth(email, password)
           print("✓ Login successful")

           objects = await client.get_objects()
           print(f"Found {len(objects)} heating system(s)")
           for obj in objects:
               print(f"- {obj.name} (id={obj.id})")
               modules = await client.get_modules(obj.id)
               for m in modules:
                   devid = m.devid or f"id:{m.id}"
                   version = m.moduleVersion or (m.gateway.version if m.gateway else "unknown")
                   print(f"  • {m.name} (devid={devid}, version={version})")
       finally:
           await client.close()

   if __name__ == "__main__":
       asyncio.run(main())

Real-time parameter monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Subscribing to updates via ``BragerOneGateway`` and printing changes:

.. code-block:: python

   import asyncio
   import os
   from contextlib import suppress
   from pybragerone import BragerOneGateway

   async def main() -> None:
       email = os.getenv("PYBO_EMAIL")
       password = os.getenv("PYBO_PASSWORD")
       object_id = int(os.getenv("PYBO_OBJECT_ID", "0"))
       modules = [m.strip() for m in os.getenv("PYBO_MODULES", "").split(",") if m.strip()]

       if not (email and password and object_id and modules):
           print("Set PYBO_EMAIL, PYBO_PASSWORD, PYBO_OBJECT_ID, PYBO_MODULES")
           return

       gateway = BragerOneGateway(email=email, password=password, object_id=object_id, modules=modules)

       async def monitor() -> None:
           async for ev in gateway.bus.subscribe():
               if ev.value is None:
                   continue
               key = f"{ev.pool}.{ev.chan}{ev.idx}"
               print(f"{ev.devid:12} {key:15} = {ev.value}")

       try:
           await gateway.start()
           task = asyncio.create_task(monitor())
           await asyncio.sleep(10)   # demo run
       finally:
           task.cancel()
           with suppress(asyncio.CancelledError):
               await task
           await gateway.stop()

   if __name__ == "__main__":
       asyncio.run(main())

ParamStore lightweight mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attaching ``ParamStore`` to the EventBus and reading values:

.. code-block:: python

   import asyncio
   import os
   from contextlib import suppress
   from pybragerone import BragerOneGateway
   from pybragerone.models.param import ParamStore

   async def main() -> None:
       email = os.getenv("PYBO_EMAIL")
       password = os.getenv("PYBO_PASSWORD")
       object_id = int(os.getenv("PYBO_OBJECT_ID", "0"))
       modules = [m.strip() for m in os.getenv("PYBO_MODULES", "").split(",") if m.strip()]

       if not (email and password and object_id and modules):
           print("Set PYBO_EMAIL, PYBO_PASSWORD, PYBO_OBJECT_ID, PYBO_MODULES")
           return

       gateway = BragerOneGateway(email=email, password=password, object_id=object_id, modules=modules)
       store = ParamStore()

       task = asyncio.create_task(store.run_with_bus(gateway.bus))
       try:
           await gateway.start()
           await asyncio.sleep(2)
           params = store.flatten()
           print(f"Total params: {len(params)}")
           for k, v in list(params.items())[:10]:
               print(f"{k:20} = {v}")
       finally:
           task.cancel()
           with suppress(asyncio.CancelledError):
               await task
           await gateway.stop()

   if __name__ == "__main__":
       asyncio.run(main())

Documentation
-------------

Full documentation: https://marpi82.github.io/py-bragerone

Security
--------

For information about security policies, vulnerability reporting, and known security exceptions, see `SECURITY.md <SECURITY.md>`_.
