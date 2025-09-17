import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath("../src"))

project = "pybragerone"
author = "MarPi82"
copyright = f"{datetime.now():%Y}, {author}"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",  # Google/NumPy docstrings
    "sphinx_autodoc_typehints",
    "myst_parser",  # enable markdown support
]
autosummary_generate = True
napoleon_google_docstring = True
napoleon_numpy_docstring = False
html_theme = "alabaster"

# Spróbuj importu wersji z pakietu
try:
    from importlib.metadata import version as _pkg_version

    release = _pkg_version("pybragerone")
except Exception:
    # fallback: gdy budujesz z drzewa bez zainstalowanego pakietu,
    # próbuj wczytać plik write_to (setuptools-scm)
    ver_file = os.path.join(os.path.dirname(__file__), "../src/pybragerone/_version.py")
    _ns = {}
    if os.path.exists(ver_file):
        with open(ver_file, encoding="utf-8") as f:
            exec(f.read(), _ns)
        release = _ns.get("__version__", "0.0.0")
    else:
        release = "0.0.0"

version = release
