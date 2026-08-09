Testing guidelines
==================

This doc explains how we test the frontend parsers and the online API.

Local unit tests
----------------

- Use pytest + pytest-asyncio (``asyncio_mode = "auto"``).
- Mock HTTP (no network) with **pytest-httpx** (``httpx_mock`` fixture); in catalog tests, fake or mock the injected API client's ``get_bytes()`` method.

Example layout::

   tests/
     test_api.py
     test_api_get_bytes_retry.py
     test_catalog_permissions.py
     test_parser_resilience.py
     test_i18n_parser.py
     test_param_map_parser.py
     test_gateway_prime_reconnect.py
     conftest.py

conftest.py (live toggle + session)
-----------------------------------

Tests that need real network access are marked ``@pytest.mark.needs_internet`` and are skipped by default; opt in with ``pytest --run-live`` or ``RUN_LIVE_TESTS=1``.

.. literalinclude:: ../../tests/conftest.py
   :language: python
   :caption: conftest.py

Example Test File
-----------------

See the existing test files in the ``tests/`` directory for examples of proper test structure and patterns.
