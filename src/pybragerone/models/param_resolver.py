"""Asset-aware parameter resolution (computed values, mappings, and describe helpers).

This module intentionally keeps heavy logic (asset parsing, rule evaluation, i18n
lookup, menu/mapping caching) *out* of :class:`pybragerone.models.param.ParamStore`.

The goal is to keep ParamStore lean for Home Assistant runtime, while allowing
CLI/config-time tooling to opt into richer behavior.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from .catalog import LiveAssetsCatalog, ParamMap
from .i18n import I18nResolver
from .menu import MenuResult
from .param import ParamStore

if TYPE_CHECKING:
    from ..api import BragerOneApiClient


_PARAM_POOL_RE = re.compile(r"^PARAM_P(?P<pool>\d+)_(?P<idx>\d+)$")
_STATUS_POOL_RE = re.compile(r"^STATUS_P(?P<pool>\d+)_(?P<idx>\d+)$")


class AssetsProtocol(Protocol):
    """Minimal async API used by ParamResolver.

    LiveAssetsCatalog satisfies this protocol, and tests may provide stubs.
    """

    async def get_param_mapping(self, tokens: Iterable[str]) -> dict[str, ParamMap]:
        """Return ParamMap objects for successfully resolved tokens."""
        raise NotImplementedError

    async def get_module_menu(
        self,
        device_menu: int,
        permissions: Iterable[str] | None = None,
        *,
        debug_mode: bool = False,
    ) -> MenuResult:
        """Return processed module menu tree for the given device_menu."""
        raise NotImplementedError

    async def list_symbols_for_permissions(self, device_menu: int, permissions: Iterable[str]) -> set[str]:
        """Return tokens visible for the provided permission set."""
        raise NotImplementedError

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        """Return translations for a given language and namespace."""
        raise NotImplementedError

    async def list_language_config(self) -> Any:
        """Return upstream translation configuration (or None)."""
        raise NotImplementedError

    async def resolve_app_one_field_label(self, *, name_key: str, lang: str) -> str | None:
        """Resolve app.json field label for a key."""
        raise NotImplementedError

    async def resolve_app_one_value_label(self, *, name_key: str, value: str, lang: str) -> str | None:
        """Resolve app.json value label for a key/value pair."""
        raise NotImplementedError

    async def resolve_app_enum_value_label(self, *, value: str, lang: str) -> str | None:
        """Resolve enum-like app values (e.g. e.ON) to human labels."""
        raise NotImplementedError


@dataclass
class ResolvedValue:
    """Unified display value resolution for a symbolic parameter."""

    symbol: str
    kind: Literal["direct", "computed"]
    address: str | None
    value: Any
    value_label: str | None
    unit: str | dict[str, str] | None


class ComputedValueEvaluator:
    """Evaluate rule-based computed mappings (primarily STATUS assets)."""

    def __init__(self, store: ParamStore) -> None:
        """Create an evaluator bound to a ParamStore instance."""
        self._store = store

    def _read_address_value(self, address: str) -> Any:
        try:
            pool, rest = address.split(".", 1)
            chan = rest[0]
            idx = int(rest[1:])
        except Exception:
            return None
        fam = self._store.get_family(pool, idx)
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
            # Preserve the explicit enum namespace for values like "e.ON".
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
            return ComputedValueEvaluator._normalize_computed_value(value.get("value"))
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

    def evaluate(self, mapping_raw: Any) -> str | None:
        """Evaluate computed value for mappings with a rule engine."""
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


MenuCacheKey = tuple[int, frozenset[str] | None]


class ParamResolver:
    """Asset-aware resolver for ParamStore values."""

    def __init__(
        self,
        *,
        store: ParamStore,
        assets: AssetsProtocol,
        lang: str | None = None,
        i18n: I18nResolver | None = None,
    ) -> None:
        """Create an asset-aware resolver for an existing ParamStore."""
        self._store = store
        self._assets = assets
        self._lang = None if lang is None else str(lang).strip().lower()
        self._i18n = i18n or I18nResolver(self._assets, lang=self._lang)  # type: ignore[arg-type]
        self._evaluator = ComputedValueEvaluator(store)

        self._cache_mapping: dict[str, ParamMap | None] = {}
        self._cache_menu: dict[MenuCacheKey, MenuResult] = {}

    @classmethod
    def from_api(
        cls,
        *,
        api: BragerOneApiClient,
        store: ParamStore,
        lang: str | None = None,
    ) -> ParamResolver:
        """Convenience constructor using a live BragerOneApiClient."""
        assets = LiveAssetsCatalog(api)
        return cls(store=store, assets=assets, lang=lang)

    async def ensure_lang(self) -> str:
        """Return effective language code (asset-driven default if not set)."""
        if self._lang:
            return self._lang
        self._lang = await self._i18n.ensure_lang()
        return self._lang

    async def get_param_mapping(self, symbol: str) -> ParamMap | None:
        """Fetch and cache parameter mapping by symbolic name."""
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
        """Fetch and cache the processed menu for a module/device_menu."""
        if debug_mode:
            return await self._assets.get_module_menu(device_menu, permissions=permissions, debug_mode=True)

        perm_key: frozenset[str] | None = None if permissions is None else frozenset(permissions)
        cache_key: MenuCacheKey = (device_menu, perm_key)

        cached = self._cache_menu.get(cache_key)
        if cached is not None:
            return cached

        result = await self._assets.get_module_menu(device_menu, permissions=perm_key, debug_mode=False)
        self._cache_menu[cache_key] = result
        return result

    async def resolve_label(self, symbol: str) -> str | None:
        """Resolve a symbol to a human-readable label via i18n assets."""
        return await self._i18n.resolve_param_label(symbol)

    async def resolve_unit(self, unit_code: Any) -> str | dict[str, str] | None:
        """Resolve unit metadata to a human-readable label or enumeration mapping."""
        return await self._i18n.resolve_unit(unit_code)

    @staticmethod
    def _addr_key(pool: str, chan: str, idx: int) -> str:
        return f"{pool}.{chan}{idx}"

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

    @staticmethod
    def _mapping_primary_address(mapping: Any, *, symbol: str | None = None) -> tuple[str, str, int] | None:
        """Best-effort extraction of (pool, chan, idx) from a mapping object."""

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
    def _clean_symbolic_tag(raw: Any) -> str | None:
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
    def _format_channels(cls, paths: Any) -> dict[str, list[dict[str, Any]]]:
        formatted: dict[str, list[dict[str, Any]]] = {}
        if not isinstance(paths, dict):
            return formatted
        for channel_name, entries in paths.items():
            if not isinstance(entries, list):
                continue
            formatted_entries = cls._format_channel_entries([e for e in entries if isinstance(e, dict)])
            if formatted_entries:
                formatted[str(channel_name)] = formatted_entries
        return formatted

    @classmethod
    def _format_status_conditions(cls, status_conditions: Any) -> dict[str, list[dict[str, Any]]]:
        formatted: dict[str, list[dict[str, Any]]] = {}
        if not status_conditions:
            return formatted
        for raw_name, entries in status_conditions.items():
            condition_name = cls._clean_symbolic_tag(raw_name) or str(raw_name)
            formatted_entries = cls._format_channel_entries([e for e in entries if isinstance(e, dict)])
            if not formatted_entries:
                continue
            for entry in formatted_entries:
                entry.setdefault("condition", condition_name)
            formatted[condition_name] = formatted_entries
        return formatted

    @classmethod
    def _format_status_flags(cls, flags: list[Any] | None) -> list[Any]:
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
                    targets_formatted = (
                        cls._format_channel_entries([t for t in targets_raw if isinstance(t, dict)])
                        if isinstance(targets_raw, list)
                        else []
                    )
                    for target in targets_formatted:
                        target.pop("condition", None)
                    if targets_formatted:
                        condition_entry["targets"] = targets_formatted
                    formatted_conditions.append(condition_entry)
            formatted_rule["conditions"] = formatted_conditions
            formatted_rules.append(formatted_rule)
        return formatted_rules

    @staticmethod
    def _extract_mapping_rule_inputs(raw: Any) -> list[dict[str, Any]]:
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

    async def resolve_value(self, symbol: str) -> ResolvedValue:
        """Resolve a symbol to a unified display value (direct or computed)."""
        mapping = await self.get_param_mapping(symbol)
        addr_tuple = self._mapping_canonical_address(symbol, mapping)

        address_key: str | None = None
        unit: str | dict[str, str] | None = None
        if addr_tuple is not None:
            address_key = self._addr_key(addr_tuple[0], addr_tuple[1], addr_tuple[2])
            fam = self._store.get_family(addr_tuple[0], addr_tuple[2])
            if fam is not None:
                unit = await self.resolve_unit(fam.unit_code)
            if unit is None and mapping is not None and mapping.units is not None:
                unit = await self.resolve_unit(mapping.units)

        if mapping is not None and self._mapping_has_computed_rules(mapping):
            computed_value = self._evaluator.evaluate(mapping.raw)
            if computed_value is None and isinstance(mapping.paths, Mapping) and mapping.paths:
                computed_value = self._evaluator.evaluate({"paths": mapping.paths})

            if computed_value is None and addr_tuple is not None:
                raw_val = None
                fam = self._store.get_family(addr_tuple[0], addr_tuple[2])
                if fam is not None:
                    raw_val = fam.get(addr_tuple[1])
                return ResolvedValue(
                    symbol=symbol,
                    kind="direct",
                    address=address_key,
                    value=raw_val,
                    value_label=None,
                    unit=unit,
                )

            computed_value_label: str | None = None
            lang_eff = await self.ensure_lang()

            mapping_name_key: str | None = None
            if mapping is not None and isinstance(mapping.raw, Mapping):
                raw_name = mapping.raw.get("name")
                if isinstance(raw_name, str) and raw_name.strip():
                    mapping_name_key = raw_name.strip()

            if mapping_name_key is not None and computed_value is not None:
                computed_value_label = await self._i18n.resolve_app_one_value_label(
                    name_key=mapping_name_key,
                    value=str(computed_value),
                    lang=str(lang_eff),
                )

            if computed_value_label is None and isinstance(computed_value, str) and computed_value.startswith("e."):
                computed_value_label = await self._i18n.resolve_app_enum_value_label(
                    value=computed_value,
                    lang=str(lang_eff),
                )

            if (
                computed_value_label is None
                and isinstance(computed_value, str)
                and computed_value.startswith("e.")
                and mapping is not None
                and isinstance(mapping.raw, Mapping)
            ):
                raw_component = mapping.raw.get("useComponent")
                component = raw_component if isinstance(raw_component, str) else None
                if component:
                    component_clean = self._clean_symbolic_tag(component) or component
                    base_lower = component_clean.strip().lower()
                    app_table_key = f"app.one.{base_lower}State"
                    computed_value_label = await self._i18n.resolve_app_one_value_label(
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

            return ResolvedValue(
                symbol=symbol,
                kind="computed",
                address=address_key,
                value=computed_value,
                value_label=computed_value_label,
                unit=unit,
            )

        val = None
        if addr_tuple is not None:
            fam = self._store.get_family(addr_tuple[0], addr_tuple[2])
            if fam is not None:
                val = fam.get(addr_tuple[1])

        return ResolvedValue(symbol=symbol, kind="direct", address=address_key, value=val, value_label=None, unit=unit)

    async def get_value(self, symbol: str) -> Any:
        """Convenience wrapper returning only the resolved display value."""
        return (await self.resolve_value(symbol)).value

    async def describe(
        self,
        pool: str,
        idx: int,
        *,
        param_symbol: str | None = None,
    ) -> tuple[str | None, str | dict[str, str] | None, Any]:
        """Describe a parameter by its (pool, idx) address, optionally with known symbol."""
        fam = self._store.get_family(pool, idx)
        if fam is None:
            return None, None, None
        label = await self.resolve_label(param_symbol) if param_symbol else None
        unit = await self.resolve_unit(fam.unit_code)
        if unit is None and param_symbol:
            mapping = await self.get_param_mapping(param_symbol)
            if mapping and mapping.units is not None:
                unit = await self.resolve_unit(mapping.units)
        return label, unit, fam.value

    async def describe_symbol(self, symbol: str) -> dict[str, Any]:
        """Describe a parameter by its symbolic name (e.g. PARAM_0 / STATUS_P5_0)."""
        mapping = await self.get_param_mapping(symbol)
        mapping_name_key: str | None = None
        if mapping is not None and isinstance(mapping.raw, Mapping):
            raw_name = mapping.raw.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                mapping_name_key = raw_name.strip()

        computed_addr = self._mapping_primary_address(mapping.raw if mapping else None, symbol=symbol)
        addr = computed_addr

        computed_primary: dict[str, Any] | None = None
        status_match = _STATUS_POOL_RE.match(symbol)
        if status_match:
            status_pool = f"P{status_match.group('pool')}"
            status_idx = int(status_match.group("idx"))
            addr = (status_pool, "s", status_idx)
            if computed_addr and computed_addr != addr:
                computed_primary = {"pool": computed_addr[0], "chan": computed_addr[1], "idx": computed_addr[2]}

        label = await self.resolve_label(symbol)
        if label is None and status_match and mapping_name_key is not None:
            lang_eff = await self.ensure_lang()
            label = await self._i18n.resolve_app_one_field_label(name_key=mapping_name_key, lang=str(lang_eff))

        pool = idx = chan = None
        unit = value = None
        min_value = max_value = status_raw = unit_code = None
        mapping_unit = None
        if mapping and mapping.units is not None:
            mapping_unit = await self.resolve_unit(mapping.units)
        if addr:
            pool, chan, idx = addr
            fam = self._store.get_family(pool, idx)
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

            computed_value = self._evaluator.evaluate(mapping.raw)
            if computed_value is None and isinstance(mapping.paths, dict) and mapping.paths:
                computed_value = self._evaluator.evaluate({"paths": mapping.paths})

            if computed_value is not None:
                lang_eff = await self.ensure_lang()
                if mapping_name_key is not None:
                    computed_value_label = await self._i18n.resolve_app_one_value_label(
                        name_key=mapping_name_key,
                        value=str(computed_value),
                        lang=str(lang_eff),
                    )
                if computed_value_label is None and isinstance(computed_value, str) and computed_value.startswith("e."):
                    computed_value_label = await self._i18n.resolve_app_enum_value_label(
                        value=computed_value,
                        lang=str(lang_eff),
                    )

                if (
                    computed_value_label is None
                    and isinstance(computed_value, str)
                    and computed_value.startswith("e.")
                    and isinstance(mapping.raw, Mapping)
                ):
                    raw_component = mapping.raw.get("useComponent")
                    component = raw_component if isinstance(raw_component, str) else None
                    if component:
                        component_clean = self._clean_symbolic_tag(component) or component
                        base_lower = component_clean.strip().lower()
                        ns_candidates = [base_lower, f"{base_lower}state"]

                        app_table_key = f"app.one.{base_lower}State"
                        computed_value_label = await self._i18n.resolve_app_one_value_label(
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

    async def merge_assets_with_permissions(self, permissions: list[str], device_menu: int = 0) -> dict[str, dict[str, Any]]:
        """Merge menu-visible symbols with mappings and live values for a permission set."""
        symbols = await self._assets.list_symbols_for_permissions(device_menu, permissions)
        out: dict[str, dict[str, Any]] = {}
        for sym in sorted(symbols):
            out[sym] = await self.describe_symbol(sym)
        return out
