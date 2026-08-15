"""Asset-driven i18n helpers.

This module centralizes translation/unit resolution logic so `ParamStore` can stay
lightweight and other components (MenuProcessor, HA config compiler, CLI) can
reuse the same behavior.

Design notes:
- No hardcoded translations.
- Language selection is driven by BragerOne app assets (index-driven bundles).
- Callers may override language explicitly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from .catalog import LiveAssetsCatalog

if TYPE_CHECKING:
    from .catalog import TranslationConfig


class I18nResolver:
    """Resolve labels/units/enums using official BragerOne assets.

    The resolver caches fetched namespaces in-memory. It is safe to use in async
    contexts; concurrent requests are serialized via a lock to reduce duplicate
    network calls.
    """

    def __init__(self, assets: LiveAssetsCatalog, *, lang: str | None = None) -> None:
        """Create a resolver bound to a LiveAssetsCatalog instance."""
        self._assets = assets
        self._lang: str | None = None if lang is None else str(lang).strip().lower()
        self._lang_cfg: TranslationConfig | None = None
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def ensure_lang(self) -> str:
        """Return effective language code (asset-driven default if not set)."""
        async with self._lock:
            if self._lang:
                return self._lang
            self._lang_cfg = await self._assets.list_language_config()
            self._lang = self._lang_cfg.default_translation if self._lang_cfg else "en"
            return self._lang

    async def get_namespace(self, namespace: str, *, lang: str | None = None) -> dict[str, Any]:
        """Fetch and cache a single i18n namespace (e.g. 'parameters', 'units')."""
        lang_eff = (lang.strip().lower() if isinstance(lang, str) and lang.strip() else None) or await self.ensure_lang()
        key = (lang_eff, namespace)
        if key in self._cache:
            return self._cache[key]
        async with self._lock:
            if key in self._cache:
                return self._cache[key]
            data = await self._assets.get_i18n(lang_eff, namespace)
            # Assets may return non-dicts; normalize to dict.
            result = data if isinstance(data, dict) else {}
            self._cache[key] = result
            return result

    async def resolve_param_label(self, symbol: str, *, lang: str | None = None) -> str | None:
        """Resolve `PARAM_*` / `STATUS_*` symbol to a display label via i18n."""
        params = await self.get_namespace("parameters", lang=lang)
        val = params.get(symbol)
        return val if isinstance(val, str) else None

    async def resolve_module_connection_labels(self, *, lang: str | None = None) -> dict[str, str]:
        """Return SPA connection-panel labels from the ``module`` i18n namespace.

        These are the same keys the official web UI uses for the module card and
        connection modal (``Index-*.js`` / ``ModuleStateModal``), for example:

        - ``serverConnection`` — card field title
        - ``connection.status`` / ``connection.connected`` / ``connection.notConnected``
        - ``connection.index`` — modal title (display label only)

        The stable HA child-device grouping key is the i18n path ``module.connection``
        (not a menu-router route and not the ``connection.index`` label string).

        Labels come from live assets only — never hardcoded.
        """
        module = await self.get_namespace("module", lang=lang)
        out: dict[str, str] = {}
        for key in ("serverConnection", "noConnection", "authorizationStatus", "authorized", "notAuthorized"):
            val = module.get(key)
            if isinstance(val, str) and val.strip():
                out[key] = val.strip()
        connection = module.get("connection")
        if isinstance(connection, Mapping):
            for key, raw in connection.items():
                if isinstance(key, str) and isinstance(raw, str) and raw.strip():
                    out[f"connection.{key}"] = raw.strip()
        return out

    async def resolve_unit(self, unit_code: Any, *, lang: str | None = None) -> str | dict[str, str] | None:
        """Resolve unit metadata to a human-readable label or enumeration mapping."""
        normalized_direct = self.normalize_unit_value(unit_code)
        if normalized_direct is not None:
            return normalized_direct

        units = await self.get_namespace("units", lang=lang)
        resolved = units.get(str(unit_code))
        normalized_resolved = self.normalize_unit_value(resolved)
        if normalized_resolved is not None:
            return normalized_resolved
        return None

    @staticmethod
    def normalize_unit_label(raw: str | None) -> str | None:
        """Normalize common unit spellings."""
        if raw is None:
            return None
        u = raw.strip()
        if not u:
            return None
        if u in {"°C", "C", "degC"}:
            return "°C"
        if u in {"°F", "F", "degF"}:
            return "°F"
        return u

    @classmethod
    def normalize_unit_value(cls, raw: Any) -> str | dict[str, str] | None:
        """Normalize arbitrary unit metadata (string or mapping)."""
        if raw is None:
            return None
        if isinstance(raw, Mapping):
            return {str(key).strip(): str(val).replace("\r", " ").replace("\n", " ").strip() for key, val in raw.items()}
        if isinstance(raw, str):
            cleaned = raw.replace("\r", " ").replace("\n", " ").strip()
            if not cleaned or cleaned.isdigit():
                return None
            # Bootstrap sometimes probes ``wn.<code>``; that is an unresolved symbolic
            # token, not a display unit or enum table.
            if cleaned.casefold().startswith("wn.") and cleaned[3:].isdigit():
                return None
            normalized = cls.normalize_unit_label(cleaned)
            return normalized if normalized is not None else cleaned
        return None
