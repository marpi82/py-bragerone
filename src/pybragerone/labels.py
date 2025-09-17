"""
LabelFetcher - pobiera assety z frontu (live), parsuje i wystawia w RAM:
- ParamCatalog (etykiety, jednostki, meta PARAM_*)
- touch_param_unit() - podpinane przez Gateway przy snapshot/ws
- pretty_label(), format_value() - cienkie wrapy na ParamCatalog
- bootstrap_from_frontend() - główny entrypoint; skorzysta z zewn. sesji jeśli podana
Działa wyłącznie w pamięci (bez plików).
"""

from __future__ import annotations

from logging import Logger, getLogger

from aiohttp import ClientSession

from .assets_client import AssetClient
from .const import ONE_BASE
from .param_catalog import ParamCatalog
from .types import JSON


class LabelFetcher:
    def __init__(
        self,
        lang: str = "pl",
        base_url: str = ONE_BASE,
        debug: bool = False,
        logger: Logger | None = None,
        session: ClientSession | None = None,
    ):
        self.lang: str = lang
        self.base_url: str = base_url
        self.debug = debug
        self.log: Logger = logger or getLogger("BragerOne")
        self.catalog: ParamCatalog = ParamCatalog()

        # sesja może być zewnętrzna (np. self.api.session); wtedy jej nie zamykamy
        self._session_ext: ClientSession | None = session
        self._session_own: ClientSession | None = None

    def _ensure_session(self) -> ClientSession:
        if self._session_ext is not None:
            return self._session_ext
        if self._session_own is None:
            self._session_own = ClientSession()
        return self._session_own

    @property
    def session(self) -> ClientSession:
        return self._ensure_session()

    async def _session_close(self) -> None:
        if self._session_own is not None and not self._session_own.closed:
            await self._session_own.close()

    # ——— bootstrap ————————————————————————————————————————————————

    async def bootstrap_from_frontend(self) -> None:
        """
        Pobiera index → wyciąga URL-e lang/units & lang/parameters → parsuje w RAM,
        dociąga meta z no-lang PARAM_*.js. NIC nie zapisuje na dysk.
        Użyje sesji z konstruktora, a jeśli jej nie było - stworzy tymczasową.
        """
        client = AssetClient(self.session, self.base_url)
        await self._do_bootstrap(client)
        await self._session_close()

    async def _do_bootstrap(self, client: AssetClient) -> None:
        # 1) index.js
        await (
            client.fetch_index_js()
        )  # We ensure index bundle is reachable; no local use of content.

        # 2) units + parameters dla self.lang
        units, labels = await client.fetch_lang_units_and_params(self.lang)

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
            "aliases": len(self.catalog.labels),
            "param_alias": 0,
            "param_unit": len(self.catalog.param_units),
            "unit_defs": len(self.catalog.units),
        }

    def count_vars(self) -> int:
        """Ilu mamy „PARAM_*” opisanych etykietą (pod log w gateway)."""
        return 0 if not self.catalog else len(self.catalog.labels)

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
            label = self.catalog.labels.get(f"PARAM_{pid}")
            if label:
                return label
        return name

    def format_value(self, pool: str, var: str, value: object, lang: str | None = None) -> object:
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
        self.catalog.set_units(units)

        if self.log:
            self.log.debug("[labels] units-only loaded: %d top-level keys", len(units))

    async def bootstrap_param_meta(self) -> None:
        """
        Fetch & parse PARAM_*.js (param meta: unit/command/status/componentType, etc.).
        Safe to call before/after snapshot; no unit binding here.
        """
        client = AssetClient(self.session, self.base_url)
        meta = await client.fetch_all_param_meta()
        self.catalog.set_meta(meta)

        if self.log:
            self.log.debug("[labels] param-meta loaded: %d keys", len(meta))

    def bind_units_from_snapshot(self, snapshot: dict[str, JSON]) -> int:
        """
        Cienki wrapper - wywołuje logikę katalogu.
        Nie robi HTTP, działa wyłącznie na pamięci.
        """
        if not self.catalog:
            return 0
        return self.catalog.bind_units_from_snapshot(snapshot)
