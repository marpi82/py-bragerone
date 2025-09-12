"""
LabelFetcher – pobiera assety z frontu (live), parsuje i wystawia w RAM:
- ParamCatalog (etykiety, jednostki, meta PARAM_*)
- touch_param_unit() – podpinane przez Gateway przy snapshot/ws
- pretty_label(), format_value() – cienkie wrapy na ParamCatalog
- bootstrap_from_frontend() – główny entrypoint; skorzysta z zewn. sesji jeśli podana
Działa wyłącznie w pamięci (bez plików).
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .assets_client import AssetClient
from .const import ONE_BASE
from .param_catalog import ParamCatalog


class LabelFetcher:
    def __init__(
        self,
        lang: str = "pl",
        base_url: str = ONE_BASE,
        debug: bool = False,
        logger: logging.Logger | None = None,
        session: aiohttp.ClientSession | None = None,  # <<— NEW
    ):
        self.lang = lang
        self.base_url = base_url
        self.debug = debug
        self.log = logger or logging.getLogger("BragerOne")
        self.catalog: ParamCatalog | None = None

        # sesja może być zewnętrzna (np. self.api.http); wtedy jej nie zamykamy
        self._session_ext: aiohttp.ClientSession | None = session

    # ——— bootstrap ————————————————————————————————————————————————

    async def bootstrap_from_frontend(self) -> None:
        """
        Pobiera index → wyciąga URL-e lang/units & lang/parameters → parsuje w RAM,
        dociąga meta z no-lang PARAM_*.js. NIC nie zapisuje na dysk.
        Użyje sesji z konstruktora, a jeśli jej nie było – stworzy tymczasową.
        """
        if self._session_ext is not None:
            # używamy dostarczonej sesji (nie zamykamy jej)
            client = AssetClient(self._session_ext, self.base_url)
            await self._do_bootstrap(client)
        else:
            # tworzymy własną sesję i po bootstrapie ją zamykamy
            async with aiohttp.ClientSession() as session:
                client = AssetClient(session, self.base_url)
                await self._do_bootstrap(client)

    async def _do_bootstrap(self, client: AssetClient) -> None:
        # 1) index.js
        await (
            client.fetch_index_js()
        )  # We ensure index bundle is reachable; no local use of content.

        # 2) units + parameters dla self.lang
        units, labels = await client.fetch_lang_units_and_params(self.lang)

        self.ensure_catalog()
        self.catalog.set_labels(labels)
        self.catalog.set_units(units)

        if self.debug:
            a = len(labels)
            u = len(units)
            self.log.debug("[labels] bootstrap ok (aliases=%d, unit_defs=%d)", a, u)

    # ——— zgodność / statystyki ——————————————————————————————————————

    async def ensure_populated(self, *args, **kwargs) -> dict[str, int]:
        """Zwraca statystyki podobne do poprzedniej implementacji."""
        if not self.catalog:
            return {"aliases": 0, "param_alias": 0, "param_unit": 0, "unit_defs": 0}
        return {
            "aliases": len(self.catalog.labels_by_param),
            "param_alias": 0,
            "param_unit": len(self.catalog.param_units),
            "unit_defs": len(self.catalog.units),
        }

    def ensure_catalog(self) -> None:
        if self.catalog is None:
            # pusty katalog; pozwala dokładać częściowo
            self.catalog = ParamCatalog(units={}, labels={}, meta={})

    def count_vars(self) -> int:
        """Ilu mamy „PARAM_*” opisanych etykietą (pod log w gateway)."""
        return 0 if not self.catalog else len(self.catalog.labels_by_param)

    def count_langs(self) -> int:
        """Placeholder (mamy jeden aktywny język na raz)."""
        return 1

    # ——— runtime (wywoływane przez Gateway) ———————————————————————

    def touch_param_unit(self, pool: str, param_id: int, unit_id_str: str) -> None:
        """Automapowanie P?.uN → unit_id na podstawie snapshot/ws."""
        if not self.catalog:
            return
        self.catalog.touch_param_unit(pool, param_id, unit_id_str)

    # ——— API do użytku w Gateway/CLI ——————————————————————————————

    def pretty_label(self, pool: str, var: str) -> str:
        """
        Zwraca przyjazną etykietę:
        - jeśli rozpoznajemy jako parameters.PARAM_<id>, zwracamy tłumaczenie z labels
        - w przeciwnym wypadku: fallback do klucza
        """
        if not self.catalog:
            return f"{pool}.{var}"

        name = self.catalog.pretty_param_key(pool, var)  # np. "parameters.PARAM_6"
        if name.startswith("parameters.PARAM_"):
            pid = name.rsplit("_", 1)[-1]
            label = self.catalog.labels_by_param.get(f"PARAM_{pid}")
            if label:
                return label
        return name

    def format_value(self, pool: str, var: str, value: Any, lang: str | None = None) -> Any:
        """
        Formatuje wartość:
        - enumy → tekst po polsku (lub lang, jeśli przekażesz)
        - wartości liczbowe + jednostki → „wartość + symbol”
        - fallback: surowa wartość
        """
        if not self.catalog:
            return value
        return self.catalog.format_value(pool, var, value, lang=lang or self.lang)

    async def bootstrap_labels(self) -> None:
        """
        Fetch & parse parameters-*.js (labels) for self.lang.
        Does NOT bind any units.
        """
        client = AssetClient(self.session, self.base_url)
        _, labels = await client.fetch_lang_units_and_params(self.lang)
        self.ensure_catalog()
        self.catalog.set_labels(labels)

        if self.log:
            self.log.debug("[labels] labels-only loaded: %d", len(labels))

    async def bootstrap_units(self) -> None:
        """
        Fetch & parse units-*.js (unit dictionary/enums) for self.lang.
        Does NOT bind any units.
        """
        client = AssetClient(self.session, self.base_url)
        units, _ = await client.fetch_lang_units_and_params(self.lang)
        self.ensure_catalog()
        self.catalog.set_units(units)

        if self.log:
            self.log.debug("[labels] units-only loaded: %d top-level keys", len(units))

    async def bootstrap_param_meta(self) -> None:
        """
        Fetch & parse PARAM_*.js (param meta: unit/command/status/componentType, etc.).
        Safe to call before/after snapshot; no unit binding here.
        """
        client = AssetClient(self.http, self.base_url)
        meta = await client.fetch_all_param_meta()
        self.ensure_catalog()
        self.catalog.set_meta(meta)

        if self.log:
            self.log.debug("[labels] param-meta loaded: %d keys", len(meta))

    def bind_units_from_snapshot(self, snapshot: dict[str, Any]) -> int:
        """
        Cienki wrapper – wywołuje logikę katalogu.
        Nie robi HTTP, działa wyłącznie na pamięci.
        """
        if not self.catalog:
            return 0
        return self.catalog.bind_units_from_snapshot(snapshot)
