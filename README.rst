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

CLI usage
---------

Run the CLI for guided login and WS session::

  pybragerone-cli --email YOU@example.com --password "***"

Examples
--------

Basic login and device listing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See `examples/basic_login.py <examples/basic_login.py>`_ for a complete example:

.. literalinclude:: examples/basic_login.py
   :language: python
   :lines: 30-65
   :emphasize-lines: 11-12, 21-22

Real-time parameter monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See `examples/realtime_updates.py <examples/realtime_updates.py>`_ for WebSocket monitoring:

.. literalinclude:: examples/realtime_updates.py
   :language: python
   :lines: 68-92
   :emphasize-lines: 6-7, 14-16

ParamStore lightweight mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See `examples/paramstore_usage.py <examples/paramstore_usage.py>`_ for ParamStore usage:

.. literalinclude:: examples/paramstore_usage.py
   :language: python
   :lines: 65-90
   :emphasize-lines: 5-6, 14-18

All examples use ``PYBO_*`` environment variables. See `examples/README.md <examples/README.md>`_ for details.

Documentation
-------------

Full documentation: https://marpi82.github.io/py-bragerone
