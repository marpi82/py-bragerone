"""Module src/pybragerone/parsers/__init__.py.

Live asset resolvers and parsers for Brager One web assets.

Public entrypoints:
- dump_i18n(session, lang, out_dir, namespaces)
- dump_param_mappings(session, filenames, out_dir)
- dump_module_menu(session, out_path)
"""
from __future__ import annotations

from .parsers import dump_i18n, dump_module_menu, dump_param_mappings

__all__ = [
    "dump_i18n",
    "dump_module_menu",
    "dump_param_mappings",
]
