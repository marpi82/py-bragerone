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

*Note: Requires Graphviz to be installed for diagram generation.*

ParamStore and Family Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. inheritance-diagram:: pybragerone.models.param.ParamStore pybragerone.models.param.ParamFamilyModel
   :parts: 1

Token Store Classes
~~~~~~~~~~~~~~~~~~~

.. inheritance-diagram:: pybragerone.models.token.TokenStore pybragerone.models.token.CLITokenStore pybragerone.models.token.HATokenStore
   :parts: 1

API Response Models
~~~~~~~~~~~~~~~~~~~

.. inheritance-diagram:: pybragerone.models.api.auth.AuthResponse pybragerone.models.api.common.ApiResponse
   :parts: 1

Menu Navigation Models
~~~~~~~~~~~~~~~~~~~~~~

.. inheritance-diagram:: pybragerone.models.menu.MenuRoute pybragerone.models.menu.MenuResult
   :parts: 1
