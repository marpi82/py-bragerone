"""Module src/pybragerone/parsers/__init__.py.

Live asset resolvers and parsers for Brager One web assets.

Public entrypoints:
- build_module_model_live(session, module_code, lang="pl", base_url="https://one.brager.pl")
- build_ha_blueprint_live(session, module_code, lang="pl", base_url="https://one.brager.pl")
"""
from __future__ import annotations

from ..parsers.live_glue import build_ha_blueprint_live, build_module_model_live

__all__ = [
    "build_ha_blueprint_live",
    "build_module_model_live",
]
