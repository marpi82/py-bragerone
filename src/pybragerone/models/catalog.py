"""Unified live access to i18n, parameter-mapping assets and module.menu."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ..api import BragerOneApiClient
from ..parsers.index_resolver import IndexResolver
from ..parsers.js_extract import extract_embedded_json


def _collect_symbols_from_menu(
    menu: dict[str, Any] | list[Any], permissions: Iterable[str]
) -> set[str]:
    """Return a set of symbols (PARAM_* and others) that are visible for the given permissions."""
    perms = set(permissions or [])
    out: set[str] = set()

    def _consume(node: Any) -> None:
        if isinstance(node, dict):
            pm = node.get("permissionModule")
            params = node.get("parameters") or node.get("params") or node.get("keys")
            # bez permissionModule albo z dozwolonym → zbieramy
            if ((pm is None) or (pm in perms)) and isinstance(params, list):
                for s in params:
                    if isinstance(s, str):
                        out.add(s)
            # rekurencja po standardowych polach
            for k in ("children", "items", "sections", "groups"):
                ch = node.get(k)
                if isinstance(ch, list):
                    for sub in ch:
                        _consume(sub)
        elif isinstance(node, list):
            for sub in node:
                _consume(sub)

    _consume(menu)
    return out


@dataclass
class TranslationConfig:
    """Configuration of available translations."""
    translations: list[dict[str, Any]]
    default_translation: str


class LiveAssetCatalog:
    """Unified live access to i18n, parameter-mapping assets and module.menu."""

    def __init__(self, api: BragerOneApiClient) -> None:
        """Initialize with a BragerOneApiClient instance."""
        self._api = api
        self.resolver = IndexResolver(self._api)

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, str]:
        """Return the i18n dictionary for a given language and namespace."""
        url = await self.resolver.url_for_i18n(lang, namespace)
        status, js = await self._api.fetch_text_one(url)
        if status != 200:
            raise RuntimeError(f"i18n fetch failed: {status} {url}")
        data = extract_embedded_json(js)
        if not isinstance(data, dict):
            raise TypeError("i18n chunk did not decode to a dict.")
        return data

    async def get_param_mapping(self, symbol: str) -> dict[str, Any]:
        """Return the parameter mapping for a given symbol (e.g. PARAM_X)."""
        url = await self.resolver.url_for_param(symbol)
        status, js = await self._api.fetch_text_one(url)
        if status != 200:
            raise RuntimeError(f"mapping fetch failed: {status} {url}")
        data = extract_embedded_json(js)
        if not isinstance(data, dict):
            raise TypeError("parameter mapping did not decode to a dict.")
        return data

    async def get_module_menu(self) -> dict[str, Any]:
        """Return the module.menu structure as a dict."""
        url = await self.resolver.url_for_module_menu()
        status, js = await self._api.fetch_text_one(url)
        if status != 200:
            raise RuntimeError(f"module.menu fetch failed: {status} {url}")
        data = extract_embedded_json(js)
        if not isinstance(data, dict):
            raise TypeError("module.menu did not decode to a dict.")
        return data

    async def list_language_config(self) -> TranslationConfig | None:
        """Return the configuration of available translations (or None if not found)."""
        txt = await self.resolver._fetch_index_text()
        m = re.search(r"var\s+YL\s*=\s*(\{.*?\})\s*;", txt, re.DOTALL)
        if not m:
            return None
        try:
            obj = json.loads(re.sub(r",\s*(?=[}\]])", "", m.group(1)))
        except Exception:
            return None
        translations = obj.get("translations") or []
        default = obj.get("defaultTranslation") or "en"
        return TranslationConfig(translations=translations, default_translation=default)

    async def list_symbols_for_permissions(
        self, permissions: Iterable[str]
    ) -> set[str]:
        """Zwróć zbiór symboli (PARAM_* oraz inne), które są widoczne dla podanych uprawnień."""
        menu = await self.get_module_menu()
        return _collect_symbols_from_menu(menu, permissions)
