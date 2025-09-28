import os
import sys
from datetime import datetime

# --- Paths ---
# Pozwala na autodoc z paczki w ../src/pybragerone
sys.path.insert(0, os.path.abspath("../src"))

# --- Project info ---
project = "pybragerone"
author = "MarPi82"
copyright = f"{datetime.now():%Y}, {author}"

# --- Sphinx extensions ---
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",  # Google/NumPy docstrings
    "sphinx_autodoc_typehints",  # ładne typy w opisach
    "sphinx.ext.todo",  # .. todo:: w dokumentacji
    "sphinx.ext.viewcode",  # linki do źródeł
    "sphinx.ext.intersphinx",  # linki do zewnętrznych docs (opcjonalnie)
    "myst_parser",  # Markdown + mdinclude (CHANGELOG.md),
    "sphinx.ext.graphviz",
    "sphinx.ext.mathjax",
    "sphinx_copybutton",
    "sphinxcontrib-mermaid",
]

# --- Sources ---
# Pozwala mieszać .rst i .md. .md użyjesz do mdinclude CHANGELOG.md
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Rozszerzenia MyST (jeśli kiedyś będziesz chciał użyć ::: fences itp.)
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "smartquotes",
    "substitution",
    "tasklist",
]
# Automatyczne anchors dla nagłówków Markdown (łatwiejsze odsyłacze)
myst_heading_anchors = 3

# --- Autodoc / typing ---
autosummary_generate = True
napoleon_google_docstring = True
napoleon_numpy_docstring = False
autodoc_typehints = "description"  # pokazuj typy obok parametrów w opisie
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
# sphinx_autodoc_typehints dodatkowe (zależnie od wersji rozszerzenia)
typehints_use_rtype = False
typehints_use_signature = True

# --- Intersphinx (opcjonalnie, przydatne do linkowania do Pythona) ---
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", {}),
}

# --- TODOs ---
todo_include_todos = True

# --- HTML theme ---
html_theme = "furo"  # or alabaster

# --- Version resolution ---
try:
    from importlib.metadata import version as _pkg_version

    release = _pkg_version("pybragerone")
except Exception:
    ver_file = os.path.join(os.path.dirname(__file__), "../src/pybragerone/_version.py")
    _ns: dict[str, str] = {}
    if os.path.exists(ver_file):
        with open(ver_file, encoding="utf-8") as f:
            exec(f.read(), _ns)
        release = _ns.get("__version__", "0.0.0")
    else:
        release = "0.0.0"

version = release

# --- Misc quality knobs ---
# Ustaw na True, jeśli chcesz, by Sphinx krzyczał na brakujące referencje (czasem zbyt surowe)
# nitpicky = True

# Jeśli chcesz, aby literalinclude łapał pliki z tests/, zadbaj by ścieżki były względne
# względem katalogu docs/ (np. ../../tests/test_live_api.py) – masz to już w plikach .rst
