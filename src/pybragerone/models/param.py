"""Parameter store with asset-aware helpers for BragerOne."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from ..models.catalog import LiveAssetsCatalog, ParamMap
from .events import EventBus
from .menu import MenuResult

MenuCacheKey = tuple[int, frozenset[str] | None]

_PARAM_POOL_RE = re.compile(r"^PARAM_P(?P<pool>\d+)_(?P<idx>\d+)$")
_STATUS_POOL_RE = re.compile(r"^STATUS_P(?P<pool>\d+)_(?P<idx>\d+)$")

if TYPE_CHECKING:
    from ..api import BragerOneApiClient
    from ..models.catalog import TranslationConfig


class ParamFamilyModel(BaseModel):
    """One parameter 'family' (e.g., P4 index 1) collecting channels: v/s/u/n/x..."""

    pool: str
    idx: int
    channels: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    def set(self, chan: str, value: Any) -> None:
        """Set raw channel value."""
        self.channels[chan] = value

    def get(self, chan: str, default: Any = None) -> Any:
        """Get raw channel value, or default if not present."""
        return self.channels.get(chan, default)

    @property
    def value(self) -> Any:
        """Raw value channel, if any."""
        return self.channels.get("v")

    @property
    def unit_code(self) -> Any:
        """Raw unit code channel, if any."""
        return self.channels.get("u")

    @property
    def status_raw(self) -> Any:
        """Raw status channel, if any."""
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
    _assets: LiveAssetsCatalog | None = PrivateAttr(default=None)
    _lang: str | None = PrivateAttr(default=None)
    _lang_cfg: TranslationConfig | None = PrivateAttr(default=None)
    _cache_i18n: dict[tuple[str, str], dict[str, Any]] = PrivateAttr(default_factory=dict)
    _cache_mapping: dict[str, ParamMap | None] = PrivateAttr(default_factory=dict)
    _cache_menu: dict[MenuCacheKey, MenuResult] = PrivateAttr(default_factory=dict)
    """Menu cache keyed by (device_menu, frozenset(permissions))."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    def init_with_api(self, api: BragerOneApiClient, *, lang: str | None = None) -> None:
        """Preferred way: connects ParamStore with ApiClient and LiveAssetCatalog."""
        self._assets = LiveAssetsCatalog(api)
        self._lang = lang

    async def run_with_bus(self, bus: EventBus) -> None:
        """Consume ParamUpdate events from EventBus and upsert into ParamStore (lightweight adapter)."""
        async for upd in bus.subscribe():
            # Skip metadata-only events that do not provide a value
            if getattr(upd, "value", None) is None:
                continue
            self.upsert(f"{upd.pool}.{upd.chan}{upd.idx}", upd.value)

    # ---------- basic updates ----------

    def _fid(self, pool: str, idx: int) -> str:
        """Unique family ID for (pool, idx), e.g. 'P4:1'."""
        return f"{pool}:{idx}"

    def upsert(self, key: str, value: Any) -> ParamFamilyModel | None:
        """Upsert a single parameter value by full key, e.g. 'P4.v1'."""
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
        """Get ParamFamilyModel by (pool, idx) address, or None if not found."""
        return self.families.get(self._fid(pool, idx))

    def flatten(self) -> dict[str, Any]:
        """Flattened view of all parameters as { 'P4.v1': value, ... }."""
        return {f"{fam.pool}.{ch}{fam.idx}": val for fam in self.families.values() for ch, val in fam.channels.items()}

    # ---------- ingest helpers ----------

    def ingest_prime_payload(self, payload: Mapping[str, Any]) -> None:
        """Ingest REST prime payload (modules/parameters) into the store."""
        for pools in payload.values():
            if not isinstance(pools, Mapping):
                continue
            for pool, entries in pools.items():
                if not isinstance(pool, str) or not isinstance(entries, Mapping):
                    continue
                for chan_idx, body in entries.items():
                    if not isinstance(chan_idx, str) or len(chan_idx) < 2:
                        continue
                    chan = chan_idx[0]
                    try:
                        idx = int(chan_idx[1:])
                    except ValueError:
                        continue
                    chan_key = f"{pool}.{chan}{idx}"
                    if isinstance(body, Mapping):
                        fam: ParamFamilyModel | None
                        if "value" in body:
                            fam = self.upsert(chan_key, body["value"])
                        else:
                            fam = self.get_family(pool, idx)
                            if fam is None:
                                fam = self.upsert(chan_key, None)
                        if fam is not None:
                            meta_keys = (
                                "storable",
                                "createdAt",
                                "previousCreatedAt",
                                "updatedAt",
                                "updatedAtClient",
                                "expire",
                                "average",
                            )
                            for meta_key in meta_keys:
                                if meta_key in body:
                                    fam.set(meta_key, body[meta_key])
                    else:
                        self.upsert(chan_key, body)

    # ---------- assets lifecycle ----------

    def init_assets(self, *, api: BragerOneApiClient, lang: str | None = None) -> None:
        """Alternative way to init assets if not using init_with_api()."""
        self._assets = LiveAssetsCatalog(api)
        self._lang = lang

    async def _ensure_lang(self) -> str:
        """Ensure self._lang is set, loading from assets if needed."""
        if self._lang:
            return self._lang
        if not self._assets:
            return "en"
        self._lang_cfg = await self._assets.list_language_config()
        self._lang = self._lang_cfg.default_translation if self._lang_cfg else "en"
        return self._lang

    # ---------- raw getters ----------

    async def get_i18n(self, namespace: str, *, lang: str | None = None) -> dict[str, Any]:
        """Get i18n mapping for a given namespace (cached)."""
        if not self._assets:
            return {}
        lang_eff = lang or await self._ensure_lang()
        key = (lang_eff, namespace)
        if key not in self._cache_i18n:
            self._cache_i18n[key] = await self._assets.get_i18n(lang_eff, namespace)
        return self._cache_i18n[key]

    async def get_i18n_parameters(self, *, lang: str | None = None) -> dict[str, Any]:
        """Get i18n parameters mapping (cached)."""
        return await self.get_i18n("parameters", lang=lang)

    async def get_i18n_units(self, *, lang: str | None = None) -> dict[str, Any]:
        """Get i18n units mapping (cached)."""
        return await self.get_i18n("units", lang=lang)

    async def get_param_mapping(self, symbol: str) -> ParamMap | None:
        """Get parameter mapping by symbolic name (cached)."""
        if not self._assets:
            return None
        if symbol not in self._cache_mapping:
            result = await self._assets.get_param_mapping([symbol])
            self._cache_mapping[symbol] = result.get(symbol)
        return self._cache_mapping.get(symbol)

    async def get_module_menu(
        self,
        device_menu: int = 0,
        *,
        permissions: Iterable[str] | None = None,
        debug_mode: bool = False,
    ) -> MenuResult:
        """Get full module menu structure (cached)."""
        if not self._assets:
            return MenuResult(routes=[], asset_url=None)
        if debug_mode:
            return await self._assets.get_module_menu(
                device_menu,
                permissions=permissions,
                debug_mode=True,
            )

        perm_key: frozenset[str] | None = None if permissions is None else frozenset(permissions)
        cache_key: MenuCacheKey = (device_menu, perm_key)

        cached: MenuResult | None = self._cache_menu.get(cache_key)
        if cached is not None:
            return cached

        result = await self._assets.get_module_menu(device_menu, permissions=perm_key, debug_mode=False)
        self._cache_menu[cache_key] = result
        return result

    # ---------- i18n helpers ----------

    async def resolve_label(self, symbol: str) -> str | None:
        """Resolve parameter symbol (e.g. 'PARAM_0') to a human-readable label."""
        params = await self.get_i18n_parameters()
        val = params.get(symbol)
        return val if isinstance(val, str) else None

    async def resolve_unit(self, unit_code: Any) -> str | dict[str, str] | None:
        """Resolve unit metadata to a human-readable label or enumeration mapping."""
        normalized_direct = self._normalize_unit_value(unit_code)
        if normalized_direct is not None:
            return normalized_direct

        units = await self.get_i18n_units()
        resolved = units.get(str(unit_code))
        normalized_resolved = self._normalize_unit_value(resolved)
        if normalized_resolved is not None:
            return normalized_resolved
        return None

    @staticmethod
    def _normalize_unit_label(raw: str | None) -> str | None:
        """Normalize a raw unit label from either i18n or mapping metadata."""
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
    def _normalize_unit_value(cls, raw: Any) -> str | dict[str, str] | None:
        """Normalize arbitrary unit metadata (string or mapping)."""
        if raw is None:
            return None
        if isinstance(raw, Mapping):
            return {str(key).strip(): str(val).replace("\r", " ").replace("\n", " ").strip() for key, val in raw.items()}
        if isinstance(raw, str):
            cleaned = raw.replace("\r", " ").replace("\n", " ").strip()
            if not cleaned or cleaned.isdigit():
                return None
            normalized = cls._normalize_unit_label(cleaned)
            return normalized if normalized is not None else cleaned
        return None

    @staticmethod
    def _clean_symbolic_tag(raw: Any) -> str | None:
        """Strip helper prefixes like e./u./[u.] and surrounding brackets."""
        if not isinstance(raw, str):
            return None
        cleaned = raw.strip()
        if not cleaned:
            return None
        if cleaned.startswith("[") and cleaned.endswith("]"):
            cleaned = cleaned[1:-1]
        parts = cleaned.split(".", 1)
        if len(parts) == 2 and parts[0].lower() in {"e", "u", "t", "s", "r", "o", "p", "m"}:
            cleaned = parts[1]
        return cleaned

    @classmethod
    def _format_channel_entries(cls, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert raw mapping entries into structured channel descriptors."""
        formatted: list[dict[str, Any]] = []
        for entry in entries:
            group = entry.get("group") or entry.get("pool")
            use_raw = entry.get("use") or entry.get("path") or entry.get("pathType")
            number_raw = entry.get("number") or entry.get("index")
            if not isinstance(group, str) or not isinstance(use_raw, str) or number_raw is None:
                continue
            try:
                number = int(number_raw)
            except (TypeError, ValueError):
                continue
            use_clean = use_raw.strip()
            if not use_clean:
                continue
            if len(use_clean) > 1:
                use_clean = use_clean[0]
            address = f"{group}.{use_clean}{number}"
            formatted_entry: dict[str, Any] = {"address": address, "channel": address}
            bit = entry.get("bit")
            if isinstance(bit, int):
                formatted_entry["bit"] = bit
            condition_val = entry.get("condition")
            condition_clean = cls._clean_symbolic_tag(condition_val)
            if condition_clean:
                formatted_entry["condition"] = condition_clean
            formatted.append(formatted_entry)
        return formatted

    @classmethod
    def _format_channels(cls, paths: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        """Format all channel paths into cleaned descriptor lists."""
        formatted: dict[str, list[dict[str, Any]]] = {}
        for channel_name, entries in paths.items():
            formatted_entries = cls._format_channel_entries(entries)
            if formatted_entries:
                formatted[channel_name] = formatted_entries
        return formatted

    @classmethod
    def _format_status_conditions(
        cls,
        status_conditions: dict[str, list[dict[str, Any]]] | None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return sanitized mapping for status conditions keyed by condition name."""
        formatted: dict[str, list[dict[str, Any]]] = {}
        if not status_conditions:
            return formatted
        for raw_name, entries in status_conditions.items():
            condition_name = cls._clean_symbolic_tag(raw_name) or str(raw_name)
            formatted_entries = cls._format_channel_entries(entries)
            if not formatted_entries:
                continue
            for entry in formatted_entries:
                entry.setdefault("condition", condition_name)
            formatted[condition_name] = formatted_entries
        return formatted

    @classmethod
    def _format_status_flags(cls, flags: list[Any] | None) -> list[Any]:
        """Normalize symbolic prefixes in status flag descriptors."""
        formatted: list[Any] = []
        for flag in flags or []:
            if isinstance(flag, str):
                formatted.append(cls._clean_symbolic_tag(flag) or flag)
            elif isinstance(flag, Mapping):
                cleaned = dict(flag)
                name_val = cleaned.get("name")
                if isinstance(name_val, str):
                    cleaned["name"] = cls._clean_symbolic_tag(name_val) or name_val
                formatted.append(cleaned)
            else:
                formatted.append(flag)
        return formatted

    @classmethod
    def _format_command_rules(cls, rules: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """Convert parsed command rules into address-aware descriptors."""
        formatted_rules: list[dict[str, Any]] = []
        if not rules:
            return formatted_rules
        for rule in rules:
            formatted_rule: dict[str, Any] = {}
            logic = rule.get("logic")
            if isinstance(logic, str):
                formatted_rule["logic"] = logic
            kind = rule.get("kind")
            if isinstance(kind, str):
                formatted_rule["kind"] = kind
            command = rule.get("command")
            if isinstance(command, str):
                formatted_rule["command"] = cls._clean_symbolic_tag(command) or command
            if "value" in rule:
                value = rule.get("value")
                if isinstance(value, str):
                    formatted_rule["value"] = cls._clean_symbolic_tag(value) or value
                else:
                    formatted_rule["value"] = value

            conditions_raw = rule.get("conditions")
            formatted_conditions: list[dict[str, Any]] = []
            if isinstance(conditions_raw, list):
                for condition in conditions_raw:
                    if not isinstance(condition, Mapping):
                        continue
                    condition_entry: dict[str, Any] = {}
                    operation = condition.get("operation")
                    if isinstance(operation, str):
                        condition_entry["operation"] = cls._clean_symbolic_tag(operation) or operation
                    if "expected" in condition:
                        condition_entry["expected"] = condition.get("expected")
                    targets_raw = condition.get("targets")
                    targets_formatted = cls._format_channel_entries(targets_raw) if isinstance(targets_raw, list) else []
                    for target in targets_formatted:
                        target.pop("condition", None)
                    if targets_formatted:
                        condition_entry["targets"] = targets_formatted
                    formatted_conditions.append(condition_entry)
            formatted_rule["conditions"] = formatted_conditions
            formatted_rules.append(formatted_rule)
        return formatted_rules

    # ---------- mapping helpers ----------

    @staticmethod
    def _mapping_primary_address(mapping: Any, *, symbol: str | None = None) -> tuple[str, str, int] | None:
        """Best-effort extraction of (pool, chan, idx) from a mapping object.

        Prefers 'value' entry, then falls back to status/unit/min/max/command.
        Mapping schema usually:
            { "value": [{"group":"P6","number":0,"use":"v"}], ... }
        """
        if isinstance(mapping, ParamMap):
            return ParamStore._mapping_primary_address(mapping.raw, symbol=symbol)

        def _collect(node: Any, acc: list[tuple[str, str | None, int]]) -> None:
            if isinstance(node, dict):
                pool = node.get("group") if "group" in node else node.get("pool")
                num_raw = node.get("number") if "number" in node else node.get("index")
                use = node.get("use") or node.get("path") or node.get("pathType")
                if isinstance(pool, str) and isinstance(num_raw, int):
                    acc.append((pool, str(use) if isinstance(use, str) else None, num_raw))
                for val in node.values():
                    _collect(val, acc)
            elif isinstance(node, list):
                for item in node:
                    _collect(item, acc)

        candidates: list[tuple[str, str | None, int]] = []
        if isinstance(mapping, dict):
            _collect(mapping, candidates)

        if not candidates:
            if symbol:
                match_param = _PARAM_POOL_RE.match(symbol)
                if match_param:
                    return f"P{match_param.group('pool')}", "v", int(match_param.group("idx"))
                match_status = _STATUS_POOL_RE.match(symbol)
                if match_status:
                    return f"P{match_status.group('pool')}", "s", int(match_status.group("idx"))
            return None

        def _chan_from_use(use: str | None) -> str:
            if not use:
                return "v"
            u = use.strip()
            alias = {
                "value": "v",
                "command": "v",
                "status": "s",
                "unit": "u",
                "minvalue": "n",
                "maxvalue": "x",
            }
            key = u.lower()
            if key in alias:
                return alias[key]
            if len(u) == 1 and u in {"v", "s", "u", "x", "n"}:
                return u
            if u.startswith("[t."):
                return "s"
            return u[0]

        normalized = [(pool, _chan_from_use(use), num) for pool, use, num in candidates]
        for preferred in ("v", "s", "u", "x", "n"):
            for pool, chan, num in normalized:
                if chan == preferred:
                    return pool, chan, num
        if normalized:
            return normalized[0]
        return None

    # ---------- describe ----------

    async def describe(
        self,
        pool: str,
        idx: int,
        *,
        param_symbol: str | None = None,
    ) -> tuple[str | None, str | dict[str, str] | None, Any]:
        """Describe a parameter by its (pool, idx) address, optionally with known symbol."""
        fam = self.get_family(pool, idx)
        if fam is None:
            return None, None, None
        label = await self.resolve_label(param_symbol) if param_symbol else None
        unit = await self.resolve_unit(fam.unit_code)
        if unit is None and param_symbol:
            mapping = await self.get_param_mapping(param_symbol)
            if mapping and mapping.units is not None:
                unit = await self.resolve_unit(mapping.units)
                if unit is None:
                    unit = self._normalize_unit_value(mapping.units)
        return label, unit, fam.value

    async def describe_symbol(self, symbol: str) -> dict[str, Any]:
        """Describe a parameter by its symbolic name (e.g. PARAM_0)."""
        mapping = await self.get_param_mapping(symbol)
        addr = self._mapping_primary_address(mapping.raw if mapping else None, symbol=symbol)
        label = await self.resolve_label(symbol)
        pool = idx = chan = None
        unit = value = None
        min_value = max_value = status_raw = unit_code = None
        mapping_unit = None
        if mapping and mapping.units is not None:
            mapping_unit = await self.resolve_unit(mapping.units)
            if mapping_unit is None:
                mapping_unit = self._normalize_unit_value(mapping.units)
        if addr:
            pool, chan, idx = addr
            fam = self.get_family(pool, idx)
            if fam:
                unit = await self.resolve_unit(fam.unit_code)
                value = fam.value
                unit_code = fam.unit_code
                min_value = fam.get("n")
                max_value = fam.get("x")
                status_raw = fam.status_raw
        if unit is None:
            unit = mapping_unit
        mapping_details: dict[str, Any] | None = None
        if mapping:
            formatted_channels = self._format_channels(mapping.paths)
            formatted_conditions = self._format_status_conditions(mapping.status_conditions)
            formatted_flags = self._format_status_flags(mapping.status_flags)
            formatted_commands = self._format_command_rules(mapping.command_rules)
            component_type_clean = self._clean_symbolic_tag(mapping.component_type)
            units_source = mapping.units
            if isinstance(units_source, str):
                units_source = self._clean_symbolic_tag(units_source) or units_source
            mapping_details = {
                "component_type": component_type_clean or mapping.component_type,
                "channels": formatted_channels,
                "paths": mapping.paths,
                "status_conditions": formatted_conditions,
                "limits": mapping.limits,
                "status_flags": formatted_flags,
                "command_rules": formatted_commands,
                "units_source": units_source,
                "origin": mapping.origin,
                "raw": mapping.raw,
            }
        return {
            "symbol": symbol,
            "pool": pool,
            "idx": idx,
            "chan": chan,
            "label": label,
            "unit": unit,
            "value": value,
            "unit_code": unit_code,
            "min": min_value,
            "max": max_value,
            "status": status_raw,
            "mapping_origin": getattr(mapping, "origin", None) if mapping else None,
            "mapping": mapping_details,
        }

    # ---------- merge assets with permissions ----------

    async def merge_assets_with_permissions(self, permissions: list[str], device_menu: int = 0) -> dict[str, dict[str, Any]]:
        """Merge i18n, mappings, menu layout, and live values filtered by permissions."""
        if not self._assets:
            return {}
        symbols = await self._assets.list_symbols_for_permissions(device_menu, permissions)
        out: dict[str, dict[str, Any]] = {}
        for sym in sorted(symbols):
            out[sym] = await self.describe_symbol(sym)
        return out

    # ---------- debug / dump ----------

    def debug_dump(self) -> None:
        """Debug dump of the ParamStore state."""
        import json
        import logging

        LOG = logging.getLogger("pybragerone.paramstore")
        flat = self.flatten()
        LOG.debug(
            "ParamStore dump (%d keys): %s",
            len(flat),
            json.dumps(flat, ensure_ascii=False)[:1000],
        )
