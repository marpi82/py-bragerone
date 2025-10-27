py-bragerone Documentation
==========================

.. image:: https://img.shields.io/pypi/v/py-bragerone?color=blue
   :target: https://pypi.org/project/py-bragerone/
   :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/py-bragerone
   :target: https://pypi.org/project/py-bragerone/
   :alt: Python Versions

.. image:: https://img.shields.io/github/actions/workflow/status/marpi82/py-bragerone/ci.yml?branch=main&label=CI
   :target: https://github.com/marpi82/py-bragerone/actions/workflows/ci.yml
   :alt: CI Status

.. image:: https://img.shields.io/badge/docs-GitHub%20Pages-blue
   :target: https://marpi82.github.io/py-bragerone/
   :alt: Documentation

.. image:: https://img.shields.io/github/license/marpi82/py-bragerone?color=green
   :target: https://github.com/marpi82/py-bragerone/blob/main/LICENSE
   :alt: License

**py-bragerone** is an async Python library for integrating with the BragerOne heating system API.
It provides REST and WebSocket clients, real-time parameter updates, and everything you need
to build Home Assistant integrations or custom automation solutions.

.. important::
   **Status:** Alpha - APIs may still evolve

   **Requirements:** Python 3.13.2+ (aligned with Home Assistant 2025)

Quick Example
=============

.. code-block:: python

   from pybragerone.api import BragerOneApiClient
   from pybragerone.gateway import BragerOneGateway

   # Create API client
   async with BragerOneApiClient() as client:
       # Login
       await client.login("user@example.com", "password")

       # Get devices and modules
       objects = await client.get_objects()
       modules = await client.get_modules(objects[0].id)

       # Start gateway for real-time updates
       gateway = BragerOneGateway(client)
       await gateway.start(objects[0].deviceId, [m.id for m in modules])

       # Subscribe to parameter updates
       async for event in gateway.event_bus.subscribe():
           print(f"Update: {event.pool}.{event.chan}{event.idx} = {event.value}")

Key Features
============

🔌 **Async REST Client**
   Built on ``httpx`` with automatic token refresh and HTTP caching

⚡ **Real-time WebSocket**
   Socket.IO client with automatic reconnection and event streaming

📊 **ParamStore**
   Dual-mode storage: lightweight for runtime, asset-aware for discovery

🏠 **Home Assistant Ready**
   Designed from the ground up for HA integration patterns

🎯 **Type Safe**
   Full Pydantic models with mypy strict mode compliance

Documentation
=============

.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   guides/quickstart
   guides/getting_started
   guides/typing
   guides/tests_guidelines

.. toctree::
   :maxdepth: 2
   :caption: Quick Reference

   reference/core_components
   reference/paramstore_usage
   reference/param_store_metadata
   reference/ha_integration
   reference/parameter_format
   reference/best_practices

.. toctree::
   :maxdepth: 2
   :caption: API Documentation

   api/api_reference
   api/pydantic_models
   architecture/overview
   architecture/operations

.. toctree::
   :maxdepth: 1
   :caption: Project

   GitHub Releases <https://github.com/marpi82/py-bragerone/releases>

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
