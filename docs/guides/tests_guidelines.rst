Testing guidelines
==================

This doc explains how we test the frontend parsers and the online API.

Local unit tests
----------------

- Use pytest + pytest-asyncio (``asyncio_mode = "auto"``).
- Mock HTTP (no network) with **pytest-httpx** (``httpx_mock`` fixture); in catalog tests, fake or mock the injected API client's ``get_bytes()`` method.
- Coverage: ``poe cov`` reports project coverage; **pre-push** enforces **80%** on ``pybragerone`` (CLI entrypoints omitted) and **100% patch** vs ``merge-base(origin/main)`` via ``scripts/check_patch_coverage.sh`` (``diff-cover`` — same diff basis as Codecov PR patch). CI uploads the XML report to Codecov.
- Optional captured UI dumps: drop ``*.js`` from ``one.brager.pl`` into ``tests/assets/index``, ``tests/assets/params``, ``tests/assets/menus``, or ``tests/assets/i18n``. Files matching ``tests/assets/**/*.js`` are gitignored (do not commit vendor JS). ``tests/test_catalog_captured_assets.py`` parses every file; empty directories skip. This does not hit the network.
- Scheduled public catalog watch (no login, not a PR gate): ``.github/workflows/upstream-assets.yml`` compares ``GET /v1/system/version`` plus the homepage ``index-*.js`` filename, then tree-sitter-parses the live index only when that fingerprint changes. When it parses, it also asserts a non-empty language config, units descriptor table, and ``units`` i18n namespace, rejects leftover JS ``\\x`` / ``\\u`` escapes, and — when the index maps ``deviceMenu`` 0 — that a gated parse with API ``DISPLAY_*`` strings yields tokens and that ``permissionModule`` values are not leftover ``_0x…['NAME']`` text. Local equivalent: ``uv run --group test python scripts/check_upstream_assets.py --always-parse`` or ``pytest --run-live tests/test_catalog_live_upstream.py``.

Example layout::

   tests/
     test_api.py
     test_api_rest.py
     test_api_get_bytes_retry.py
     test_catalog_permissions.py
     test_catalog_asset_index.py
     test_parser_resilience.py
     test_i18n_parser.py
     test_param_map_parser.py
     test_gateway_prime_reconnect.py
     test_gateway_dispatch.py
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
