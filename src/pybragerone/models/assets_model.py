from __future__ import annotations

from logging import Logger, getLogger

from aiohttp import ClientSession

from ..assets_client import AssetClient  # existing module in your repo
from ..const import ONE_BASE  # existing constant in your repo
from ..parsers import jsparse
from .catalog import ParamCatalog
from .labels import Labels
from .param_meta import ParamMeta
from .types import JSON
from .units import Units


class AssetsModel:
    """Frontend aggregator: fetch labels/units/meta and fill ParamCatalog."""

    def __init__(
        self,
        *,
        lang: str = "pl",
        base_url: str = ONE_BASE,
        logger: Logger | None = None,
        session: ClientSession | None = None,
        debug: bool = False,
    ) -> None:
        self.lang = lang
        self.base_url = base_url
        self.log = logger or getLogger("pybragerone")
        self.debug = debug

        self.catalog = ParamCatalog()
        self._session_ext = session
        self._session_own: ClientSession | None = None

    @property
    def session(self) -> ClientSession:
        if self._session_ext:
            return self._session_ext
        if self._session_own is None:
            self._session_own = ClientSession()
        return self._session_own

    async def aclose(self) -> None:
        if self._session_own and not self._session_own.closed:
            await self._session_own.close()

    async def bootstrap_all(self) -> None:
        """Fetch index + localized assets + PARAM_* meta; populate catalog."""
        client = AssetClient(self.session, self.base_url)
        try:
            await client.fetch_index_js()

            units_raw, labels_raw = await client.fetch_lang_units_and_params(self.lang)
            meta_raw = await client.fetch_all_param_meta()

            # --- tolerancja: jeżeli assets_client oddał już modele, użyj je bezpośrednio
            if isinstance(labels_raw, Labels):
                labels_model = labels_raw
            else:
                assert isinstance(labels_raw, dict), f"labels_raw not dict: {type(labels_raw)}"
                labels_model = jsparse.parse_labels(labels_raw)

            if isinstance(units_raw, Units):
                units_model = units_raw
            else:
                assert isinstance(units_raw, dict), f"units_raw not dict: {type(units_raw)}"
                units_model = jsparse.parse_units(units_raw)

            if isinstance(meta_raw, ParamMeta):
                meta_model = meta_raw
            else:
                assert isinstance(meta_raw, dict), f"meta_raw not dict: {type(meta_raw)}"
                meta_model = jsparse.parse_param_meta(meta_raw)

            self.catalog.set_labels(labels_model)
            self.catalog.set_units(units_model)
            self.catalog.set_meta(meta_model)

            if self.debug:
                self.log.debug(
                    "[assets] loaded: labels=%d units=%d meta=%d",
                    len(self.catalog.labels.items),
                    len(self.catalog.units.items),
                    len(self.catalog.meta.items),
                )
        finally:
            # domknij tylko własną sesję - zapobiega "Unclosed client session"
            await self.aclose()

    # Convenience delegates
    def pretty_label(self, pool: str, var: str) -> str:
        return self.catalog.pretty_param_key(pool, var)

    def format_value(self, pool: str, var: str, value: object, lang: str | None = None) -> object:
        return self.catalog.format_value(pool, var, value, lang=lang or self.lang)

    def bind_units_from_snapshot(self, snapshot: dict[str, JSON]) -> int:
        return self.catalog.bind_units_from_snapshot(snapshot)

    def touch_param_unit(self, pool: str, param_id: int, unit_id_str: str) -> None:
        self.catalog.touch_param_unit(pool, param_id, unit_id_str)
