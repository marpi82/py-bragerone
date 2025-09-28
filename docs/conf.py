import os
import sys
from datetime import datetime

# --- Paths ---
# Allows autodoc from package in ../src/pybragerone
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
    "sphinx_autodoc_typehints",  # nice types in descriptions
    "sphinx.ext.todo",  # .. todo:: in documentation
    "sphinx.ext.viewcode",  # links to sources
    "sphinx.ext.intersphinx",  # links to external docs (optional)
    "myst_parser",  # Markdown + mdinclude (CHANGELOG.md),
    "sphinx.ext.mathjax",
    "sphinx_copybutton",
    "sphinxcontrib.mermaid",  # mermaid diagrams
]

# --- Sources ---
# Allows mixing .rst and .md. Use .md for mdinclude CHANGELOG.md
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# MyST extensions (if you want to use ::: fences etc.)
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "smartquotes",
    "substitution",
    "tasklist",
]
# Automatic anchors for Markdown headings (easier references)
myst_heading_anchors = 3

# --- Source discovery ---
exclude_patterns = [
    "tests_guidelines.rst",
    "typing.rst",
]

# --- Autodoc / typing ---
autosummary_generate = True
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_ivar = True
autodoc_typehints = "description"  # show types next to parameters in description
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
# sphinx_autodoc_typehints additional (depending on extension version)
typehints_use_rtype = False
typehints_use_signature = True
autodoc_type_aliases = {
    "BragerOneApiClient": "pybragerone.api.BragerOneApiClient",
}

# --- Intersphinx (optional, useful for linking to Python docs) ---
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
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
# Set to True if you want Sphinx to complain about missing references (sometimes too strict)
# nitpicky = True

# If you want literalinclude to catch files from tests/, make sure paths are relative
# to the docs/ directory (e.g. ../../tests/test_live_api.py) – you already have this in .rst files
