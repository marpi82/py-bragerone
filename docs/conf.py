"""Configuration file for the Sphinx documentation builder."""

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
    "sphinx.ext.coverage",  # documentation coverage analysis
    "sphinx.ext.doctest",  # test code examples in docstrings
    "myst_parser",  # Markdown + mdinclude (CHANGELOG.md),
    "sphinx.ext.mathjax",
    "sphinx_copybutton",
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
exclude_patterns = []

# --- Autodoc / typing ---
# Autosummary configuration to avoid duplicates from re-exports
autosummary_generate = True
autosummary_generate_overwrite = True
autosummary_imported_members = False  # Key: Don't document imported members to avoid duplicates

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

# --- Warnings suppression ---
# Only minimal necessary warnings
suppress_warnings = [
    "ref.python",  # Suppress "more than one target found" for cross-references
    "sphinx_autodoc_typehints.forward_reference",  # Suppress forward reference warnings (e.g., Pydantic's JsonValue)
    "sphinx_autodoc_typehints.guarded_import",  # Suppress guarded import warnings
]


# --- HTML theme ---
html_theme = "furo"

# Furo theme options for better readability and navigation
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#2962ff",
        "color-brand-content": "#2962ff",
        "font-stack": "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif",
        "font-stack--monospace": "Consolas, Monaco, 'Courier New', monospace",
        "font-size--normal": "17px",
        "font-size--small": "15px",
        "sidebar-width": "280px",
    },
    "dark_css_variables": {
        "color-brand-primary": "#448aff",
        "color-brand-content": "#448aff",
        "font-size--normal": "17px",
        "font-size--small": "15px",
        "sidebar-width": "280px",
    },
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
}

# Static path for custom CSS/JS (if needed)
html_static_path = ["_static"]

# Syntax highlighting style
# 'friendly' for light mode - clean, readable, works well with Furo's light theme
# 'monokai' for dark mode - dark background, bright colors, works well with Furo
pygments_style = "friendly"
pygments_dark_style = "monokai"

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
        release = "dev"

version = release

# --- New Extensions Configuration ---

# Documentation coverage settings
coverage_show_missing_items = True
coverage_skip_undoc_in_source = True

# Doctest settings
doctest_default_flags = 1  # ELLIPSIS flag for ... in output
doctest_global_setup = """
import asyncio
import json
from pybragerone.models.param import ParamStore
from pybragerone.utils import json_preview, summarize_top_level
"""

# --- Misc quality knobs ---
# Set to True if you want Sphinx to complain about missing references (sometimes too strict)
# nitpicky = True

# If you want literalinclude to catch files from tests/, make sure paths are relative
# to the docs/ directory (e.g. ../../tests/test_live_api.py) - you already have this in .rst files
