"""Parameter store with asset-aware helpers for BragerOne."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

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


@dataclass(slots=True)
class ResolvedValue:
    """Unified value resolution for a symbolic parameter.

    The `value` field is the display value:
    - for direct mappings it is the current register value
    - for computed rule-based mappings it is the computed result (often a string like `e.ON`)
    """

    symbol: str
    kind: Literal["direct", "computed"]
    address: str | None
    value: Any
    value_label: str | None
    unit: str | dict[str, str] | None


@dataclass(slots=True)
class _ComputedSpec:
    symbol: str
    mapping_raw: Mapping[str, Any]
    mapping_paths: Mapping[str, Any] | None
    mapping_name_key: str | None
    use_component: str | None
    inputs: frozenset[str]
    computed_value: str | None = None
    computed_value_label: str | None = None


def _addr_key(pool: str, chan: str, idx: int) -> str:
    return f"{pool}.{chan}{idx}"


def _parse_addr_key(key: str) -> tuple[str, str, int] | None:
    try:
        pool, rest = key.split(".", 1)
        chan = rest[0]
        idx = int(rest[1:])
    except Exception:
        return None
    return pool, chan, idx


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

    # Computed-value cache for rule-based mappings (reactive updates)
    _computed_specs: dict[str, _ComputedSpec] = PrivateAttr(default_factory=dict)
    _computed_by_input: dict[str, set[str]] = PrivateAttr(default_factory=dict)
    _computed_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    def init_with_api(self, api: BragerOneApiClient, *, lang: str | None = None) -> None:
        """Preferred way: connects ParamStore with ApiClient and LiveAssetCatalog."""
        self._assets = LiveAssetsCatalog(api)
        self._lang = None if lang is None else str(lang).strip().lower()

    async def run_with_bus(self, bus: EventBus) -> None:
        """Consume ParamUpdate events from EventBus and upsert into ParamStore (lightweight adapter)."""
        async for upd in bus.subscribe():
            # Skip metadata-only events that do not provide a value
            if getattr(upd, "value", None) is None:
                continue
            await self.upsert_async(f"{upd.pool}.{upd.chan}{upd.idx}", upd.value)

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

    async def upsert_async(self, key: str, value: Any) -> ParamFamilyModel | None:
        """Async upsert that also recomputes dependent computed values.

        Prefer this method in async contexts (EventBus consumption, HA runtime)
        when you want computed STATUS values to update reactively.
        """
        fam = self.upsert(key, value)
        await self._recompute_dependents_for_key(key)
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

    # ---------- computed values (reactive cache) ----------

    def _read_channel_value(self, *, pool: str, chan: str, idx: int) -> Any:
        fam = self.get_family(pool, idx)
        if fam is None:
            return None
        return fam.get(chan)

    @staticmethod
    def _mapping_has_computed_rules(mapping: ParamMap | None) -> bool:
        if mapping is None:
            return False
        raw = mapping.raw
        if isinstance(raw, Mapping):
            any_rules = raw.get("any")
            if isinstance(any_rules, list) and any_rules:
                return True
            value_rules = raw.get("value")
            if isinstance(value_rules, list) and value_rules:
                return True
        paths = mapping.paths
        if isinstance(paths, Mapping):
            v = paths.get("value")
            if isinstance(v, list) and v:
                return True
        return False

    @classmethod
    def _mapping_canonical_address(cls, symbol: str, mapping: ParamMap | None) -> tuple[str, str, int] | None:
        computed_addr = cls._mapping_primary_address(mapping.raw if mapping else None, symbol=symbol)
        addr = computed_addr
        status_match = _STATUS_POOL_RE.match(symbol)
        if status_match:
            status_pool = f"P{status_match.group('pool')}"
            status_idx = int(status_match.group("idx"))
            addr = (status_pool, "s", status_idx)
        return addr

    @staticmethod
    def _extract_mapping_rule_inputs_addresses(raw: Any) -> set[str]:
        inputs: set[str] = set()
        for item in ParamStore._extract_mapping_rule_inputs(raw):
            addr = item.get("address")
            if isinstance(addr, str) and addr:
                inputs.add(addr)
        return inputs

    async def _ensure_computed_registered(self, symbol: str, mapping: ParamMap) -> _ComputedSpec:
        async with self._computed_lock:
            existing = self._computed_specs.get(symbol)
            if existing is not None:
                return existing

            mapping_name_key: str | None = None
            raw_name = mapping.raw.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                mapping_name_key = raw_name.strip()

            raw_component = mapping.raw.get("useComponent")
            use_component = raw_component if isinstance(raw_component, str) and raw_component.strip() else None

            inputs = self._extract_mapping_rule_inputs_addresses(mapping.raw)
            if isinstance(mapping.paths, Mapping) and mapping.paths:
                inputs |= self._extract_mapping_rule_inputs_addresses({"paths": mapping.paths})

            spec = _ComputedSpec(
                symbol=symbol,
                mapping_raw=mapping.raw,
                mapping_paths=mapping.paths if isinstance(mapping.paths, Mapping) else None,
                mapping_name_key=mapping_name_key,
                use_component=use_component,
                inputs=frozenset(inputs),
            )
            self._computed_specs[symbol] = spec
            for addr in spec.inputs:
                self._computed_by_input.setdefault(addr, set()).add(symbol)
            return spec

    async def _compute_value_and_label_from_spec(self, spec: _ComputedSpec) -> tuple[str | None, str | None]:
        computed_value = self._evaluate_computed_value(spec.mapping_raw)
        if computed_value is None and spec.mapping_paths:
            computed_value = self._evaluate_computed_value({"paths": spec.mapping_paths})
        if computed_value is None:
            return None, None

        computed_value_label: str | None = None
        lang_eff = await self._ensure_lang()

        if self._assets is not None and spec.mapping_name_key is not None:
            computed_value_label = await self._assets.resolve_app_one_value_label(
                name_key=spec.mapping_name_key,
                value=computed_value,
                lang=str(lang_eff),
            )

        if (
            computed_value_label is None
            and self._assets is not None
            and isinstance(computed_value, str)
            and computed_value.startswith("e.")
        ):
            computed_value_label = await self._assets.resolve_app_enum_value_label(
                value=computed_value,
                lang=str(lang_eff),
            )

        if (
            computed_value_label is None
            and self._assets is not None
            and isinstance(computed_value, str)
            and computed_value.startswith("e.")
            and spec.use_component is not None
        ):
            component_clean = self._clean_symbolic_tag(spec.use_component) or spec.use_component
            base_lower = component_clean.strip().lower()
            app_table_key = f"app.one.{base_lower}State"
            computed_value_label = await self._assets.resolve_app_one_value_label(
                name_key=app_table_key,
                value=computed_value,
                lang=str(lang_eff),
            )

            enum_tail = computed_value[2:]
            parts = [p for p in enum_tail.split("_") if p]
            snake_key = "_".join(p.lower() for p in parts) if parts else enum_tail.lower()
            camel_key = parts[0].lower() + "".join(p.lower().title() for p in parts[1:]) if parts else enum_tail
            key_candidates = [camel_key, snake_key, enum_tail, enum_tail.lower()]

            if computed_value_label is None:
                for ns in (base_lower, f"{base_lower}state"):
                    tbl = await self._assets.get_i18n(str(lang_eff), ns)
                    if not isinstance(tbl, dict) or not tbl:
                        continue
                    for k in key_candidates:
                        v = tbl.get(k)
                        if isinstance(v, str):
                            computed_value_label = v
                            break
                    if computed_value_label is not None:
                        break

        return computed_value, computed_value_label

    async def _recompute_dependents_for_key(self, key: str) -> None:
        parsed = _parse_addr_key(key)
        if parsed is None:
            return
        pool, chan, idx = parsed
        addr = _addr_key(pool, chan, idx)

        async with self._computed_lock:
            dependents = set(self._computed_by_input.get(addr, set()))

        for sym in dependents:
            async with self._computed_lock:
                spec = self._computed_specs.get(sym)
            if spec is None:
                continue
            value, label = await self._compute_value_and_label_from_spec(spec)
            async with self._computed_lock:
                spec.computed_value = value
                spec.computed_value_label = label

    async def resolve_value(self, symbol: str) -> ResolvedValue:
        """Resolve a symbol to a unified display value (direct or computed)."""
        mapping = await self.get_param_mapping(symbol)
        addr_tuple = self._mapping_canonical_address(symbol, mapping)

        address_key: str | None = None
        unit: str | dict[str, str] | None = None
        if addr_tuple is not None:
            address_key = _addr_key(addr_tuple[0], addr_tuple[1], addr_tuple[2])
            fam = self.get_family(addr_tuple[0], addr_tuple[2])
            if fam is not None:
                unit = await self.resolve_unit(fam.unit_code)
            if unit is None and mapping is not None and mapping.units is not None:
                unit = await self.resolve_unit(mapping.units)
                if unit is None:
                    unit = self._normalize_unit_value(mapping.units)

        if mapping is not None and self._mapping_has_computed_rules(mapping):
            spec = await self._ensure_computed_registered(symbol, mapping)

            async with self._computed_lock:
                cached_value = spec.computed_value
                cached_label = spec.computed_value_label

            if cached_value is None:
                value, label = await self._compute_value_and_label_from_spec(spec)
                async with self._computed_lock:
                    spec.computed_value = value
                    spec.computed_value_label = label
                cached_value, cached_label = value, label

            if cached_value is None and addr_tuple is not None:
                raw_val = self._read_channel_value(pool=addr_tuple[0], chan=addr_tuple[1], idx=addr_tuple[2])
                return ResolvedValue(
                    symbol=symbol, kind="direct", address=address_key, value=raw_val, value_label=None, unit=unit
                )

            return ResolvedValue(
                symbol=symbol,
                kind="computed",
                address=address_key,
                value=cached_value,
                value_label=cached_label,
                unit=unit,
            )

        val = None
        if addr_tuple is not None:
            val = self._read_channel_value(pool=addr_tuple[0], chan=addr_tuple[1], idx=addr_tuple[2])
        return ResolvedValue(symbol=symbol, kind="direct", address=address_key, value=val, value_label=None, unit=unit)

    async def get_value(self, symbol: str) -> Any:
        """Convenience wrapper returning only the resolved display value."""
        return (await self.resolve_value(symbol)).value

    # ---------- assets lifecycle ----------

    def init_assets(self, *, api: BragerOneApiClient, lang: str | None = None) -> None:
        """Alternative way to init assets if not using init_with_api()."""
        self._assets = LiveAssetsCatalog(api)
        self._lang = None if lang is None else str(lang).strip().lower()

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
        if len(parts) == 2 and parts[0].lower() in {"a", "e", "u", "t", "s", "r", "o", "p", "m"}:
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

    @staticmethod
    def _extract_mapping_rule_inputs(raw: Any) -> list[dict[str, Any]]:
        """Extract referenced addresses/bits/masks from rule-based mapping payloads.

        The BragerOne assets include some computed/derived mappings (notably STATUS_*),
        where the visible label/value is derived from a chain of conditional rules.
        We do not attempt to evaluate the rules here; we only extract the set of
        underlying parameter addresses that are referenced.

        Supported shapes:
        - normalized rule model with targets: {"rules": [{"conditions": [{"targets": [{"address": "P5.s0", ...}]}]}]}
        - raw menu-like model: {"any": [{"if": [{"value": [{"group": "P5", "number": 0, "use": "s", ...}]}]}]}
        """
        if not isinstance(raw, dict):
            return []

        out: list[dict[str, Any]] = []
        seen: set[tuple[str, int | None, int | None]] = set()

        def _add(address: str, *, bit: Any = None, mask: Any = None) -> None:
            if not isinstance(address, str) or not address:
                return
            bit_i: int | None = bit if isinstance(bit, int) else None
            mask_i: int | None = mask if isinstance(mask, int) else None
            key = (address, bit_i, mask_i)
            if key in seen:
                return
            seen.add(key)
            entry: dict[str, Any] = {"address": address}
            if bit_i is not None:
                entry["bit"] = bit_i
            if mask_i is not None:
                entry["mask"] = mask_i
            out.append(entry)

        # Shape 1: normalized rules with targets[].address
        rules = raw.get("rules")
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                conditions = rule.get("conditions")
                if not isinstance(conditions, list):
                    continue
                for cond in conditions:
                    if not isinstance(cond, dict):
                        continue
                    targets = cond.get("targets")
                    if not isinstance(targets, list):
                        continue
                    for tgt in targets:
                        if not isinstance(tgt, dict):
                            continue
                        addr = tgt.get("address")
                        if isinstance(addr, str) and addr:
                            _add(addr, bit=tgt.get("bit"), mask=tgt.get("mask"))

        # Shape 2: raw "any" rules with value[] selectors
        any_rules = raw.get("any")
        if isinstance(any_rules, list):
            for rule in any_rules:
                if not isinstance(rule, dict):
                    continue
                for key in ("if", "elseif"):
                    conds = rule.get(key)
                    if not isinstance(conds, list):
                        continue
                    for cond in conds:
                        if not isinstance(cond, dict):
                            continue
                        values = cond.get("value")
                        if not isinstance(values, list):
                            continue
                        for sel in values:
                            if not isinstance(sel, dict):
                                continue
                            group = sel.get("group")
                            number = sel.get("number")
                            use = sel.get("use")
                            if not isinstance(group, str) or not isinstance(number, int) or not isinstance(use, str) or not use:
                                continue
                            address = f"{group}.{use[0]}{number}"
                            _add(address, bit=sel.get("bit"), mask=sel.get("mask"))

        # Shape 3: computed rules under `paths.value` (same condition structure)
        paths = raw.get("paths")
        if isinstance(paths, dict):
            value_rules = paths.get("value")
            if isinstance(value_rules, list):
                for rule in value_rules:
                    if not isinstance(rule, dict):
                        continue
                    for key in ("if", "elseif"):
                        conds = rule.get(key)
                        if not isinstance(conds, list):
                            continue
                        for cond in conds:
                            if not isinstance(cond, dict):
                                continue
                            values = cond.get("value")
                            if not isinstance(values, list):
                                continue
                            for sel in values:
                                if not isinstance(sel, dict):
                                    continue
                                group = sel.get("group")
                                number = sel.get("number")
                                use = sel.get("use")
                                if (
                                    not isinstance(group, str)
                                    or not isinstance(number, int)
                                    or not isinstance(use, str)
                                    or not use
                                ):
                                    continue
                                address = f"{group}.{use[0]}{number}"
                                _add(address, bit=sel.get("bit"), mask=sel.get("mask"))

        return out

    @staticmethod
    def _extract_mapping_rule_values(raw: Any) -> list[str]:
        """Extract possible output values from rule-based mapping payloads."""
        if not isinstance(raw, dict):
            return []
        values: list[str] = []
        seen: set[str] = set()
        rules = raw.get("rules")
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                v = rule.get("value")
                if isinstance(v, str) and v and v not in seen:
                    seen.add(v)
                    values.append(v)
        return values

    def _read_address_value(self, address: str) -> Any:
        """Read a live value from ParamStore by full address (e.g. 'P5.s0')."""
        try:
            pool, rest = address.split(".", 1)
            chan = rest[0]
            idx = int(rest[1:])
        except Exception:
            return None
        fam = self.get_family(pool, idx)
        if fam is None:
            return None
        return fam.get(chan)

    @staticmethod
    def _normalize_computed_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            if not v:
                return None
            # Minified bundles may encode enums as "o.WORK"; keep last segment.
            # Preserve the explicit enum namespace for values like "e.ON" so they
            # can be translated via `app` assets.
            if "." in v:
                head, tail = v.rsplit(".", 1)
                if head != "e":
                    v = tail
            return v
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, dict) and "value" in value:
            return ParamStore._normalize_computed_value(value.get("value"))
        return None

    @staticmethod
    def _operation_name(op: Any) -> str | None:
        if op is None:
            return None
        s = op.strip() if isinstance(op, str) else str(op).strip()
        if not s:
            return None
        if "." in s:
            s = s.split(".")[-1]
        return s

    def _eval_condition_any(self, cond: dict[str, Any]) -> bool:
        """Evaluate a single condition object.

        The STATUS assets encode conditions like:
            {expected: 1, operation: equalTo, value: [{group: 'P5', number: 0, use: 's', bit: 3}]}

        We treat multiple selectors in the "value" array as OR; a condition passes
        if ANY selector satisfies it.
        """
        expected = cond.get("expected")
        op = self._operation_name(cond.get("operation"))
        values = cond.get("value")
        if not isinstance(values, list) or not values or op is None:
            return False

        def _compare(actual: Any) -> bool:
            if op == "equalTo":
                return bool(actual == expected)
            if op == "notEqualTo":
                return bool(actual != expected)
            if op == "greaterThan":
                return actual is not None and expected is not None and actual > expected
            if op == "greaterThanOrEqualTo":
                return actual is not None and expected is not None and actual >= expected
            if op == "lessThan":
                return actual is not None and expected is not None and actual < expected
            if op == "lessThanOrEqualTo":
                return actual is not None and expected is not None and actual <= expected
            return False

        for sel in values:
            if not isinstance(sel, dict):
                continue
            group = sel.get("group")
            number = sel.get("number")
            use = sel.get("use")
            if not isinstance(group, str) or not isinstance(number, int) or not isinstance(use, str) or not use:
                continue
            addr = f"{group}.{use[0]}{number}"
            raw_val = self._read_address_value(addr)
            if raw_val is None:
                continue
            if not isinstance(raw_val, int):
                try:
                    raw_val = int(raw_val)
                except (TypeError, ValueError):
                    continue

            bit = sel.get("bit")
            mask = sel.get("mask")
            if isinstance(bit, int):
                actual = 1 if ((raw_val >> bit) & 1) else 0
            elif isinstance(mask, int):
                actual = raw_val & mask
            else:
                actual = raw_val

            if _compare(actual):
                return True
        return False

    def _eval_any_rules(self, any_rules: list[Any]) -> str | None:
        """Evaluate a rule-based mapping payload (raw['any'])."""
        for rule in any_rules:
            if not isinstance(rule, dict):
                continue
            conds = rule.get("if")
            if conds is None:
                conds = rule.get("elseif")
            if conds is None:
                continue
            if not isinstance(conds, list) or not conds:
                continue
            if all(isinstance(c, dict) and self._eval_condition_any(c) for c in conds):
                then = rule.get("then")
                if isinstance(then, dict):
                    return self._normalize_computed_value(then.get("value"))
                return self._normalize_computed_value(then)
        return None

    def _evaluate_computed_value(self, mapping_raw: Any) -> str | None:
        """Evaluate computed value for mappings with a rule engine (STATUS assets)."""
        if not isinstance(mapping_raw, dict):
            return None
        any_rules = mapping_raw.get("any")
        if isinstance(any_rules, list):
            return self._eval_any_rules(any_rules)

        value_rules = mapping_raw.get("value")
        if isinstance(value_rules, list):
            return self._eval_any_rules(value_rules)

        paths = mapping_raw.get("paths")
        if isinstance(paths, dict):
            value_rules = paths.get("value")
            if isinstance(value_rules, list):
                return self._eval_any_rules(value_rules)
        return None

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
        mapping_name_key: str | None = None
        if mapping is not None and isinstance(mapping.raw, Mapping):
            raw_name = mapping.raw.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                mapping_name_key = raw_name.strip()

        computed_addr = self._mapping_primary_address(mapping.raw if mapping else None, symbol=symbol)
        addr = computed_addr

        # STATUS_* tokens are not raw value channels; they represent status registers (P<n>.s<idx>)
        # with optional derived logic in the mapping asset. For these, prefer a stable canonical
        # address derived from the token itself.
        computed_primary: dict[str, Any] | None = None
        status_match = _STATUS_POOL_RE.match(symbol)
        if status_match:
            status_pool = f"P{status_match.group('pool')}"
            status_idx = int(status_match.group("idx"))
            addr = (status_pool, "s", status_idx)
            if computed_addr and computed_addr != addr:
                computed_primary = {"pool": computed_addr[0], "chan": computed_addr[1], "idx": computed_addr[2]}

        label = await self.resolve_label(symbol)
        if label is None and status_match:
            lang_eff = await self._ensure_lang()
            if self._assets is not None and mapping_name_key is not None:
                label = await self._assets.resolve_app_one_field_label(name_key=mapping_name_key, lang=str(lang_eff))
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
        computed_value: str | None = None
        computed_value_label: str | None = None
        if mapping:
            formatted_channels = self._format_channels(mapping.paths)
            formatted_conditions = self._format_status_conditions(mapping.status_conditions)
            formatted_flags = self._format_status_flags(mapping.status_flags)
            formatted_commands = self._format_command_rules(mapping.command_rules)
            component_type_clean = self._clean_symbolic_tag(mapping.component_type)
            units_source = mapping.units
            if isinstance(units_source, str):
                units_source = self._clean_symbolic_tag(units_source) or units_source

            # Extract dependencies for computed/rule-based mappings (e.g. STATUS_*).
            mapping_inputs = self._extract_mapping_rule_inputs(mapping.raw)
            mapping_values = self._extract_mapping_rule_values(mapping.raw)

            mapping_details = {
                "component_type": component_type_clean or mapping.component_type,
                "channels": formatted_channels,
                "paths": mapping.paths,
                "status_conditions": formatted_conditions,
                "limits": mapping.limits,
                "status_flags": formatted_flags,
                "command_rules": formatted_commands,
                "inputs": mapping_inputs,
                "values": mapping_values,
                "units_source": units_source,
                "origin": mapping.origin,
                "raw": mapping.raw,
            }
            computed_value = self._evaluate_computed_value(mapping.raw)
            if computed_value is None and isinstance(mapping.paths, dict) and mapping.paths:
                # Some STATUS assets encode computed mappings under `paths.value`.
                computed_value = self._evaluate_computed_value({"paths": mapping.paths})
            if computed_value is not None:
                lang_eff = await self._ensure_lang()
                if self._assets is not None and mapping_name_key is not None:
                    computed_value_label = await self._assets.resolve_app_one_value_label(
                        name_key=mapping_name_key,
                        value=computed_value,
                        lang=str(lang_eff),
                    )
                if (
                    computed_value_label is None
                    and self._assets is not None
                    and isinstance(computed_value, str)
                    and computed_value.startswith("e.")
                ):
                    computed_value_label = await self._assets.resolve_app_enum_value_label(
                        value=computed_value,
                        lang=str(lang_eff),
                    )

                # If `app.json` doesn't provide labels for enum-like values (e.g. `e.ON`),
                # the official app often uses component-specific translation tables
                # (e.g. `resources/languages/<lang>/diodeState.json`).
                if (
                    computed_value_label is None
                    and self._assets is not None
                    and isinstance(computed_value, str)
                    and computed_value.startswith("e.")
                    and isinstance(mapping.raw, Mapping)
                ):
                    raw_component = mapping.raw.get("useComponent")
                    component = raw_component if isinstance(raw_component, str) else None
                    if component:
                        component_clean = self._clean_symbolic_tag(component) or component
                        # Derive candidate namespaces without hardcoding: DIODE -> diodestate, diodeState.
                        base = component_clean.strip()
                        base_lower = base.lower()
                        ns_candidates = [base_lower, f"{base_lower}state"]

                        # Some enums are translated via `app.json` tables like `app.one.diodeState`.
                        # This is still asset-driven and avoids hardcoding labels.
                        app_table_key = f"app.one.{base_lower}State"
                        computed_value_label = await self._assets.resolve_app_one_value_label(
                            name_key=app_table_key,
                            value=computed_value,
                            lang=str(lang_eff),
                        )
                        if computed_value_label is not None:
                            # Resolved from app.json; skip component i18n bundles.
                            pass

                        enum_tail = computed_value[2:]
                        parts = [p for p in enum_tail.split("_") if p]
                        snake_key = "_".join(p.lower() for p in parts) if parts else enum_tail.lower()
                        camel_key = parts[0].lower() + "".join(p.lower().title() for p in parts[1:]) if parts else enum_tail
                        key_candidates = [camel_key, snake_key, enum_tail, enum_tail.lower()]

                        if computed_value_label is None:
                            for ns in ns_candidates:
                                tbl = await self._assets.get_i18n(str(lang_eff), ns)
                                if not isinstance(tbl, dict) or not tbl:
                                    continue
                                for k in key_candidates:
                                    v = tbl.get(k)
                                    if isinstance(v, str):
                                        computed_value_label = v
                                        break
                                if computed_value_label is not None:
                                    break
        return {
            "symbol": symbol,
            "pool": pool,
            "idx": idx,
            "chan": chan,
            "computed_primary": computed_primary,
            "label": label,
            "unit": unit,
            "value": value,
            "computed_value": computed_value,
            "computed_value_label": computed_value_label,
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
