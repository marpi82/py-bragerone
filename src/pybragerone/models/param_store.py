from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from ..events import EventBus
from ..api import BragerOneApiClient
from .catalog import LiveAssetCatalog, TranslationConfig


class ParamFamilyModel(BaseModel):
    """One parameter 'family' (e.g., P4 index 1) collecting channels: v/s/u/n/x..."""

    pool: str
    idx: int
    channels: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    def set(self, chan: str, value: Any) -> None:
        self.channels[chan] = value

    def get(self, chan: str, default: Any = None) -> Any:
        return self.channels.get(chan, default)

    @property
    def value(self) -> Any:
        return self.channels.get("v")

    @property
    def unit_code(self) -> Any:
        return self.channels.get("u")

    @property
    def status_raw(self) -> Any:
        return self.channels.get("s")


class ParamStore(BaseModel):
    """Heavy parameter store + asset-aware helpers.

    - Keep raw P?.v?/u?/s? values for HA fast-path.
    - Resolve labels/units on demand via LiveAssetCatalog.
    - Support both addressing modes:
        * known address: (pool, idx)  -> describe()
        * symbolic name:  'PARAM_0'   -> describe_symbol()
    - Merge assets + permissions into a single view for UI/bootstrap.
    """

    families: dict[str, ParamFamilyModel] = Field(default_factory=dict)

    # Live assets and caches
    _assets = PrivateAttr(default=None)  # type: LiveAssetCatalog | None
    _lang = PrivateAttr(default=None)  # type: str | None
    _lang_cfg = PrivateAttr(default=None)  # type: TranslationConfig | None
    _cache_i18n = PrivateAttr(
        default_factory=dict
    )  # type: dict[tuple[str, str], dict[str, Any]]
    _cache_mapping = PrivateAttr(
        default_factory=dict
    )  # type: dict[str, dict[str, Any]]
    _cache_menu = PrivateAttr(default=None)  # type: dict[str, Any] | None

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    def init_with_api(
        self, api: BragerOneApiClient, *, lang: str | None = None
    ) -> None:
        """Preferowany sposób: spina ParamStore z ApiClient i LiveAssetCatalog."""
        self._assets = LiveAssetCatalog(api)
        self._lang = lang

    async def run_with_bus(self, bus: EventBus) -> None:
        """Consume ParamUpdate events from EventBus and upsert into ParamStore (lekki adapter)."""
        async for upd in bus.subscribe():
            # pomijamy eventy bez wartości (np. czyste meta)
            if getattr(upd, "value", None) is None:
                continue
            self.upsert(f"{upd.pool}.{upd.chan}{upd.idx}", upd.value)

    # ---------- basic updates ----------

    def _fid(self, pool: str, idx: int) -> str:
        return f"{pool}:{idx}"

    def upsert(self, key: str, value: Any) -> ParamFamilyModel | None:
        try:
            pool, rest = key.split(".", 1)
            chan = rest[0]
            idx = int(rest[1:])
        except Exception:
            return None
        fid = self._fid(pool, idx)
        fam = self.families.get(fid)
        if fam is None:
            fam = ParamFamilyModel(pool=pool, idx=idx)
            self.families[fid] = fam
        fam.set(chan, value)
        return fam

    def get_family(self, pool: str, idx: int) -> ParamFamilyModel | None:
        return self.families.get(self._fid(pool, idx))

    def flatten(self) -> dict[str, Any]:
        return {
            f"{fam.pool}.{ch}{fam.idx}": val
            for fam in self.families.values()
            for ch, val in fam.channels.items()
        }

    # ---------- assets lifecycle ----------

    def init_assets(self, *, api: BragerOneApiClient, lang: str | None = None) -> None:
        self._assets = LiveAssetCatalog(api)
        self._lang = lang

    async def _ensure_lang(self) -> str:
        if self._lang:
            return self._lang
        if not self._assets:
            return "en"
        self._lang_cfg = await self._assets.list_language_config()
        self._lang = self._lang_cfg.default_translation if self._lang_cfg else "en"
        return self._lang

    # ---------- raw getters ----------

    async def get_i18n(
        self, namespace: str, *, lang: str | None = None
    ) -> dict[str, Any]:
        if not self._assets:
            return {}
        lang_eff = lang or await self._ensure_lang()
        key = (lang_eff, namespace)
        if key not in self._cache_i18n:
            self._cache_i18n[key] = await self._assets.get_i18n(lang_eff, namespace)
        return self._cache_i18n[key]

    async def get_i18n_parameters(self, *, lang: str | None = None) -> dict[str, Any]:
        return await self.get_i18n("parameters", lang=lang)

    async def get_i18n_units(self, *, lang: str | None = None) -> dict[str, Any]:
        return await self.get_i18n("units", lang=lang)

    async def get_param_mapping(self, symbol: str) -> dict[str, Any]:
        if not self._assets:
            return {}
        if symbol not in self._cache_mapping:
            self._cache_mapping[symbol] = await self._assets.get_param_mapping(symbol)
        return self._cache_mapping[symbol]

    async def get_module_menu(self) -> dict[str, Any]:
        if not self._assets:
            return {}
        if self._cache_menu is None:
            self._cache_menu = await self._assets.get_module_menu()
        return self._cache_menu

    # ---------- i18n helpers ----------

    async def resolve_label(self, symbol: str) -> str | None:
        params = await self.get_i18n_parameters()
        val = params.get(symbol)
        return val if isinstance(val, str) else None

    async def resolve_unit(self, unit_code: Any) -> str | None:
        if unit_code is None:
            return None
        units = await self.get_i18n_units()
        unit = units.get(str(unit_code))
        if not isinstance(unit, str):
            return None
        u = unit.strip()
        if u in ("°C", "C", "degC"):
            return "°C"
        if u in ("°F", "F", "degF"):
            return "°F"
        return u

    # ---------- mapping helpers ----------

    @staticmethod
    def _mapping_primary_address(
        mapping: dict[str, Any],
    ) -> tuple[str, str, int] | None:
        """Best-effort extraction of (pool, chan, idx) from a mapping object.

        Prefers 'value' entry, then falls back to status/unit/min/max/command.
        Mapping schema usually:
            { "value": [{"group":"P6","number":0,"use":"v"}], ... }
        """
        for key in ("value", "command", "status", "unit", "minValue", "maxValue"):
            arr = mapping.get(key)
            if isinstance(arr, list) and arr:
                ent = arr[0]
                pool = ent.get("group")
                use = ent.get("use")
                num = ent.get("number")
                if (
                    isinstance(pool, str)
                    and isinstance(use, str)
                    and isinstance(num, int)
                ):
                    return pool, use, num
        return None

    # ---------- describe ----------

    async def describe(
        self, pool: str, idx: int, *, param_symbol: str | None = None
    ) -> tuple[str | None, str | None, Any]:
        fam = self.get_family(pool, idx)
        if fam is None:
            return None, None, None
        label = await self.resolve_label(param_symbol) if param_symbol else None
        unit = await self.resolve_unit(fam.unit_code)
        return label, unit, fam.value

    async def describe_symbol(self, symbol: str) -> dict[str, Any]:
        mapping = await self.get_param_mapping(symbol)
        addr = self._mapping_primary_address(mapping) if mapping else None
        label = await self.resolve_label(symbol)
        pool = idx = chan = None
        unit = value = None
        if addr:
            pool, chan, idx = addr
            fam = self.get_family(pool, idx)
            if fam:
                unit = await self.resolve_unit(fam.unit_code)
                value = fam.value
        return {
            "symbol": symbol,
            "pool": pool,
            "idx": idx,
            "chan": chan,
            "label": label,
            "unit": unit,
            "value": value,
        }

    # ---------- merge assets with permissions ----------

    async def merge_assets_with_permissions(
        self, permissions: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Scal i18n + selective mappings + menu + bieżące wartości, filtrowane po perms."""
        if not self._assets:
            return {}
        symbols = await self._assets.list_symbols_for_permissions(permissions)
        out: dict[str, dict[str, Any]] = {}
        for sym in sorted(symbols):
            out[sym] = await self.describe_symbol(sym)
        return out

    # ---------- debug / dump ----------

    def debug_dump(self) -> None:
        import json
        import logging

        LOG = logging.getLogger("pybragerone.paramstore")
        flat = self.flatten()
        LOG.debug(
            "ParamStore dump (%d keys): %s",
            len(flat),
            json.dumps(flat, ensure_ascii=False)[:1000],
        )
