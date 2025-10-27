Testing guidelines
==================

This doc explains how we test the frontend parsers and the online API.

Local unit tests
----------------

- Use pytest + pytest-asyncio.
- Mock HTTP (no network) by monkeypatching ``_fetch_text`` and ``_autodetect_index_url``.

Example layout::

   tests/
     test_utils.py
     test_resolver.py
     test_parser.py
     test_parser_i18n.py
     test_api.py
     test_api_live.py
     conftest.py

conftest.py (live toggle + session)
-----------------------------------

.. literalinclude:: ../tests/conftest.py
   :language: python
   :caption: conftest.py

test_live_api.py (real HTTP)
----------------------------

.. literalinclude:: ../tests/test_api_live.py
   :language: python
   :caption: test_api_live.py
