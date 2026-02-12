Documentation Quality
=====================

This page shows documentation analysis and class inheritance diagrams.

Code Examples Testing
---------------------

Run doctests manually with: ``sphinx-build -b doctest docs docs/_build/doctest``

This will test all code examples found in docstrings to ensure they work correctly.
Our utility functions include testable examples:

.. doctest::

   >>> from pybragerone.utils import json_preview, summarize_top_level
   >>> json_preview({"key": "value", "numbers": [1, 2, 3]})
   '{"key":"value","numbers":[1,2,3]}'
   >>> summarize_top_level({"a": 1, "b": 2})
   {'type': 'dict', 'keys': ['a', 'b'], 'len': 2}

Class Inheritance Diagrams
---------------------------

This project intentionally avoids Graphviz-only documentation features so the docs build cleanly in minimal environments.

If you want to explore class relationships, the most reliable sources are:

- :doc:`../api/api_reference`
- The module pages under ``pybragerone.models.*``
