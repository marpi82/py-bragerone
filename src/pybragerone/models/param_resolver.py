"""Asset-aware parameter resolution (computed values, mappings, and describe helpers).

This module intentionally keeps heavy logic (asset parsing, rule evaluation, i18n
lookup, menu/mapping caching) *out* of :class:`pybragerone.models.param.ParamStore`.

The goal is to keep ParamStore lean for Home Assistant runtime, while allowing
CLI/config-time tooling to opt into richer behavior.
"""

from __future__ import annotations

import logging
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

LOG = logging.getLogger(__name__)


_PARAM_POOL_RE = re.compile(r"^PARAM_P(?P<pool>\d+)_(?P<idx>\d+)$")
_STATUS_POOL_RE = re.compile(r"^STATUS_P(?P<pool>\d+)_(?P<idx>\d+)$")

# Obfuscated builds write `x['toFixed'](0x1)` where readable ones write `x.toFixed(1)`.
_JS_BRACKET_MEMBER_RE = re.compile(r"\[\s*['\"]([A-Za-z_$][\w$]*)['\"]\s*\]")
# Radix literals only; the lookbehind keeps mangled identifiers such as `_0x4fdb4d` intact.
_JS_RADIX_LITERAL_RE = re.compile(r"(?<![\w$.])0(?:[xX][0-9a-fA-F]+|[oO][0-7]+|[bB][01]+)")
# Unit 66: HH:MM formatter. Identifiers and quotes vary; these two pieces do not.
_UNIT66_PADSTART_RE = re.compile(r"padStart\(2,['\"]0['\"]\)")
_UNIT66_SHIFT_TEN_RE = re.compile(r"\([^)]+-1\)\*10")
# Bare menu-title i18n namespaces (``MAINMENU_*``, ``MENUSERWIS_*``, ``MENU_*``, …).
# Require the known prefixes so abbreviations like ``DHW`` do not trigger asset fetches.
_MENU_TITLE_TOKEN_RE = re.compile(r"^(?:MAINMENU|MENUSERWIS|MENUPALNIKA|MENU)_[A-Z0-9_]+$")
# ParamStore flat keys referenced by SPA ``displayDropdown`` (e.g. ``P6.v219``).
_ROUTE_DROPDOWN_VALUE_KEY_RE = re.compile(r"^P\d+\.[a-z]\d+$", re.IGNORECASE)

# Installer / service module-item route *suffixes* (after optional ``companies.``).
# Compared case-insensitively. Everyday panels may still use ``MENUSERWIS_*`` titles.
_WEB_UI_EXCLUDED_MODULE_MENU_ROUTES: frozenset[str] = frozenset(
    {
        "modules.menu.dev",
        "modules.menu.producer",
        "modules.menu.configuration",
        "modules.menu.schema",
        "modules.menu.tests_output_input",
        "modules.menu.testsoutputinput",
        "modules.menu.calibration",
        "modules.menu.lock_board",
        "modules.menu.lockboard",
    }
)


def _normalize_module_menu_route_name(name: str) -> str:
    """Normalize a module-menu route name for installer denylist matching."""
    name_cf = name.strip().casefold()
    if name_cf.startswith("companies."):
        name_cf = name_cf[len("companies.") :]
    # Live menus use camelCase (``testsOutputInput``); denylist is snake_case.
    return name_cf.replace("_", "")


# Precomputed once — ``_route_name_is_excluded_installer_menu`` runs per route/ancestor.
_WEB_UI_EXCLUDED_MODULE_MENU_ROUTES_NORMALIZED: frozenset[str] = frozenset(
    _normalize_module_menu_route_name(item) for item in _WEB_UI_EXCLUDED_MODULE_MENU_ROUTES
)

# Known SPA view components that may host parameters outside the menu token list.
_PANEL_SHELL_COMPONENT_MARKERS: frozenset[str] = frozenset(
    {
        "ScheduleView",
        "TimeZonesView",
        "SchedulesView",
        "TariffsView",
    }
)


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

    async def discover_static_route_tokens(self, route_path: str) -> set[str]:
        """Return tokens from a static deviceMenu route chunk when supported."""
        raise NotImplementedError

    async def list_symbols_for_permissions(self, device_menu: int, permissions: Iterable[str]) -> set[str]:
        """Return tokens visible for the provided permission set."""
        raise NotImplementedError

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        """Return translations for a given language and namespace."""
        raise NotImplementedError

    async def get_unit_descriptor(self, unit_code: Any) -> Mapping[str, Any] | None:
        """Return index-defined unit descriptor metadata for a raw unit code."""
        raise NotImplementedError

    async def list_language_config(self) -> Any:
        """Return upstream translation configuration (or None)."""
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


@dataclass(frozen=True)
class _NumericTransform:
    """Normalized numeric transform extracted from unit descriptor."""

    shift: float
    factor: float
    precision: int | None


class ComputedValueEvaluator:
    """Evaluate rule-based computed mappings (primarily STATUS assets)."""

    def __init__(self, store: ParamStore) -> None:
        """Create an evaluator bound to a ParamStore instance."""
        self._store = store
        self._context: dict[str, Any] = {}

    def set_context(self, context: Mapping[str, Any] | None) -> None:
        """Set optional runtime context used by storeGetter-based conditions."""
        self._context = dict(context) if isinstance(context, Mapping) else {}

    @staticmethod
    def _coerce_expected(expected: Any) -> Any:
        if isinstance(expected, str) and expected.strip() == "void 0":
            return None
        return expected

    @staticmethod
    def _regex_from_literal(value: Any) -> re.Pattern[str] | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        if len(text) < 2 or not text.startswith("/"):
            return None
        last = text.rfind("/")
        if last <= 0:
            return None
        pattern = text[1:last]
        flags_raw = text[last + 1 :]
        flags = 0
        if "i" in flags_raw:
            flags |= re.IGNORECASE
        try:
            return re.compile(pattern, flags)
        except re.error:
            return None

    @staticmethod
    def _render_store_getter(template: str, context: Mapping[str, Any]) -> str:
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            value = context.get(key)
            return "" if value is None else str(value)

        return re.sub(r"\{([^}]+)\}", repl, template)

    def _read_store_getter(self, getter: str) -> Any:
        resolved = self._render_store_getter(getter, self._context)
        parts = [part for part in resolved.split(".") if part]
        if not parts:
            return None

        current: Any = self._context
        for part in parts:
            if isinstance(current, Mapping):
                if part in current:
                    current = current[part]
                    continue
                try:
                    int_key = int(part)
                except ValueError:
                    int_key = None
                if int_key is not None and int_key in current:
                    current = current[int_key]
                    continue
                return None

            if isinstance(current, list):
                try:
                    idx = int(part)
                except ValueError:
                    return None
                if 0 <= idx < len(current):
                    current = current[idx]
                    continue
                return None

            return None

        return current

    @classmethod
    def _compare_condition(cls, *, op: str | None, actual: Any, expected: Any) -> bool:
        if op is None:
            return False

        expected_norm = cls._coerce_expected(expected)

        if op == "equalTo":
            return bool(actual == expected_norm)
        if op == "notEqualTo":
            return bool(actual != expected_norm)
        if op == "greaterThan":
            return actual is not None and expected_norm is not None and actual > expected_norm
        if op == "greaterThanOrEqualTo":
            return actual is not None and expected_norm is not None and actual >= expected_norm
        if op == "lessThan":
            return actual is not None and expected_norm is not None and actual < expected_norm
        if op == "lessThanOrEqualTo":
            return actual is not None and expected_norm is not None and actual <= expected_norm

        if op in {"matches", "notMatches"}:
            pattern = cls._regex_from_literal(expected_norm)
            if pattern is None or actual is None:
                return False
            matched = bool(pattern.search(str(actual)))
            return matched if op == "matches" else not matched

        return False

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
            # Index-inline factories leave TypeScript enum leftovers such as
            # ``DiodeState['ON']`` / ``ThreeWayValveState['DISABLED']``.
            bracket = _JS_BRACKET_MEMBER_RE.search(v)
            if bracket is not None:
                return bracket.group(1)
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
        # Index-inline STATUS maps emit ``ClauseOperation['equalTo']`` instead of
        # the cleaned asset form ``equalTo`` / ``t.equalTo``.
        bracket = _JS_BRACKET_MEMBER_RE.search(s)
        if bracket is not None:
            return bracket.group(1)
        if "." in s:
            s = s.split(".")[-1]
        return s

    def _eval_condition_any(self, cond: dict[str, Any]) -> bool:
        expected = cond.get("expected")
        op = self._operation_name(cond.get("operation"))
        values = cond.get("value")
        if op is None:
            return False

        if isinstance(values, Mapping):
            getter = values.get("storeGetter")
            if isinstance(getter, str) and getter.strip():
                actual = self._read_store_getter(getter)
                return self._compare_condition(op=op, actual=actual, expected=expected)
            return False

        if not isinstance(values, list) or not values:
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

            if self._compare_condition(op=op, actual=actual, expected=expected):
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

    def set_runtime_context(self, context: Mapping[str, Any] | None) -> None:
        """Provide optional runtime context for computed symbol evaluation."""
        self._evaluator.set_context(context)

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

    async def prefetch_param_mappings(self, symbols: Iterable[str]) -> None:
        """Bulk-fetch and cache mappings for unresolved symbols.

        Args:
            symbols: Symbol names to prefetch.
        """
        uniq_symbols = list(dict.fromkeys(str(sym) for sym in symbols if sym))
        missing = [sym for sym in uniq_symbols if sym not in self._cache_mapping]
        if not missing:
            return

        result = await self._assets.get_param_mapping(missing)
        for sym in missing:
            self._cache_mapping[sym] = result.get(sym)

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

    @staticmethod
    def _normalize_text(value: str) -> str:
        return "".join(ch for ch in value.casefold() if ch.isalnum() or ch.isspace()).strip()

    @staticmethod
    def _lookup_dotted_path(data: Mapping[str, Any], path: str) -> str | None:
        if not path:
            return None
        cur: Any = data
        parts = [part for part in path.split(".") if part]
        if not parts:
            return None
        for part in parts:
            if not isinstance(cur, Mapping):
                return None
            cur = cur.get(part)
        return cur if isinstance(cur, str) and cur.strip() else None

    @staticmethod
    def _lookup_dotted_path_raw(data: Mapping[str, Any], path: str) -> str | None:
        if not path:
            return None
        cur: Any = data
        parts = [part for part in path.split(".") if part]
        if not parts:
            return None
        for part in parts:
            if not isinstance(cur, Mapping):
                return None
            cur = cur.get(part)
        return cur if isinstance(cur, str) else None

    @classmethod
    def _route_title(cls, route: Any, *, routes_i18n: Mapping[str, Any] | None = None) -> str:
        meta = getattr(route, "meta", None)
        dn = getattr(meta, "display_name", None) if meta is not None else None

        if isinstance(dn, str) and dn.strip() and isinstance(routes_i18n, Mapping):
            dn_norm = dn.strip()
            if dn_norm.startswith("routes."):
                translation_path = dn_norm[7:]
                translated = cls._lookup_dotted_path(routes_i18n, translation_path)
                if translated is not None:
                    return translated
            else:
                # Bare tokens such as ``MAINMENU_MENU_TERMOSTATU`` resolve via the
                # flat overlay built by :meth:`_panel_title_i18n` (string-default
                # namespaces and the ``menu`` pack), not via ``routes.*`` paths.
                translated = cls._lookup_dotted_path(routes_i18n, dn_norm)
                if translated is not None:
                    return translated

        if isinstance(routes_i18n, Mapping):
            route_name = getattr(route, "name", None)
            if isinstance(route_name, str) and route_name.strip():
                translated = cls._lookup_dotted_path(routes_i18n, route_name.strip())
                if translated is not None:
                    return translated

        if isinstance(dn, str) and dn.strip():
            return dn.strip()
        route_name = getattr(route, "name", None)
        if isinstance(route_name, str) and route_name.strip():
            return route_name.strip()
        route_path = getattr(route, "path", None)
        return str(route_path or "-")

    @classmethod
    def _collect_menu_title_tokens(cls, menu: MenuResult) -> set[str]:
        """Collect bare ``MAINMENU_*``-style tokens from route names and display names."""
        tokens: set[str] = set()
        for route, _ancestors in cls._iter_routes_with_ancestors(menu.routes):
            meta = getattr(route, "meta", None)
            candidates = (
                getattr(route, "name", None),
                getattr(meta, "display_name", None) if meta is not None else None,
            )
            for raw in candidates:
                if not isinstance(raw, str):
                    continue
                token = raw.strip()
                if _MENU_TITLE_TOKEN_RE.fullmatch(token):
                    tokens.add(token)
        return tokens

    @staticmethod
    def _string_namespace_title(namespace: str, table: Mapping[str, Any]) -> str | None:
        """Extract the title string from a string-default or self-keyed i18n namespace."""
        direct = table.get(namespace)
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        default = table.get("__default__")
        if isinstance(default, str) and default.strip():
            return default.strip()
        if len(table) == 1:
            only = next(iter(table.values()))
            if isinstance(only, str) and only.strip():
                return only.strip()
        return None

    async def _panel_title_i18n(self, menu: MenuResult) -> dict[str, Any]:
        """Build the i18n map used for panel path titles.

        Starts from the ``routes`` namespace (nested ``modules.menu.*`` keys) and
        overlays flat title strings for bare menu tokens. Those titles live in:

        - the ``menu`` namespace (a few ``MAINMENU_*`` / ``MENUSERWIS_*`` keys), and
        - dedicated string-default namespaces named like the token itself
          (``MAINMENU_MENU_TERMOSTATU`` → ``"Menu termostatów"``).
        """
        routes_i18n = dict(await self._i18n.get_namespace("routes"))
        menu_i18n = await self._i18n.get_namespace("menu")
        for key, value in menu_i18n.items():
            if not (isinstance(key, str) and isinstance(value, str) and value.strip()):
                continue
            existing = routes_i18n.get(key)
            # Prefer a real menu title over a blank/whitespace routes placeholder.
            if not (isinstance(existing, str) and existing.strip()):
                routes_i18n[key] = value.strip()

        for token in self._collect_menu_title_tokens(menu):
            existing = routes_i18n.get(token)
            if isinstance(existing, str) and existing.strip():
                continue
            table = await self._i18n.get_namespace(token)
            title = self._string_namespace_title(token, table)
            if title is not None:
                routes_i18n[token] = title
        return routes_i18n

    @classmethod
    def _route_allowed_in_module_item(cls, route: Any) -> bool:
        """Return whether a route may contribute symbols in all-panels mode.

        Frontend ``moduleItem`` panels use ``modules.menu.*`` /
        ``companies.modules.menu.*`` names. Live device menus also attach
        parameters directly to bare title tokens (``MAINMENU_*``,
        ``MENUSERWIS_*``, ``MENU_*``, …) — those must be included or HA bootstrap
        drops whole settings panels (boiler, ignition, valves, …).

        ``routes.*`` names are navigation chrome, not module-item panels.
        """
        raw_name = getattr(route, "name", None)
        if not isinstance(raw_name, str):
            return False

        name = raw_name.strip()
        if not name:
            return False
        if _MENU_TITLE_TOKEN_RE.fullmatch(name) is not None:
            return True

        name_cf = name.casefold()
        if ".menu." not in name_cf:
            return False
        if name_cf.startswith("routes."):
            return False
        return name_cf.startswith("modules.menu.") or name_cf.startswith("companies.modules.menu.")

    @classmethod
    def _route_name_is_excluded_installer_menu(cls, name: str) -> bool:
        """Return whether *name* matches a known installer-only module-menu route."""
        return _normalize_module_menu_route_name(name) in _WEB_UI_EXCLUDED_MODULE_MENU_ROUTES_NORMALIZED

    @classmethod
    def _route_is_end_user_web_ui(
        cls,
        route: Any,
        *,
        ancestors: tuple[Any, ...] = (),
    ) -> bool:
        """Return whether a module-item route belongs on the everyday web UI.

        Mirrors SPA side-menu gating in ``index-*.js`` (``isRouteVisible`` + the
        side-menu computed filter):

        - ``meta.isVisibleOnSideMenu`` is not ``False`` on the route or any ancestor.
        - Path has no ``:param`` segments (side menu only lists concrete paths).
        - Route name is not a known installer-only ``modules.menu.*`` /
          ``companies.modules.menu.*`` entry (denylist; case-insensitive).

        ``MENUSERWIS_*`` title tokens are **not** excluded: everyday UI panels such
        as buffer settings use that prefix (``MENUSERWIS_USTAWIENIA_BUFORU``).

        Account permissions are applied by the menu fetch (``permissions=…``), not
        here — callers must not retry with ``permissions=None`` for UI mode.
        """
        raw_name = getattr(route, "name", None)
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        if name and cls._route_name_is_excluded_installer_menu(name):
            return False

        path = getattr(route, "path", None)
        if isinstance(path, str) and ":" in path:
            return False

        meta = getattr(route, "meta", None)
        side = getattr(meta, "is_visible_on_side_menu", None) if meta is not None else None
        if side is False:
            return False

        for ancestor in ancestors:
            ancestor_name = getattr(ancestor, "name", None)
            if (
                isinstance(ancestor_name, str)
                and ancestor_name.strip()
                and cls._route_name_is_excluded_installer_menu(ancestor_name)
            ):
                return False
            ancestor_meta = getattr(ancestor, "meta", None)
            ancestor_side = getattr(ancestor_meta, "is_visible_on_side_menu", None) if ancestor_meta is not None else None
            if ancestor_side is False:
                return False
        return True

    @staticmethod
    def _iter_routes(routes: Iterable[Any]) -> Iterable[Any]:
        stack = list(routes)[::-1]
        while stack:
            cur = stack.pop()
            yield cur
            children = getattr(cur, "children", None)
            if isinstance(children, list):
                for child in reversed(children):
                    stack.append(child)

    @staticmethod
    def _iter_routes_with_ancestors(routes: Iterable[Any]) -> Iterable[tuple[Any, tuple[Any, ...]]]:
        stack: list[tuple[Any, tuple[Any, ...]]] = [(route, ()) for route in list(routes)[::-1]]
        while stack:
            cur, ancestors = stack.pop()
            yield cur, ancestors
            children = getattr(cur, "children", None)
            if isinstance(children, list):
                next_ancestors = (*ancestors, cur)
                for child in reversed(children):
                    stack.append((child, next_ancestors))

    @classmethod
    def _panel_title_hierarchical(
        cls,
        *,
        route: Any,
        ancestors: tuple[Any, ...],
        routes_i18n: Mapping[str, Any] | None,
    ) -> str:
        base = cls._route_title(route, routes_i18n=routes_i18n)
        if not ancestors:
            return base

        prefix_parts: list[str] = []
        for parent in ancestors:
            parent_title = cls._route_title(parent, routes_i18n=routes_i18n).strip()
            if not parent_title or parent_title == "-":
                continue
            prefix_parts.append(parent_title)

        if not prefix_parts:
            return base
        return "/".join([*prefix_parts, base])

    @staticmethod
    def _collect_route_symbols(route: Any) -> set[str]:
        symbols: set[str] = set()

        def add_from_container(container: Any) -> None:
            if container is None:
                return
            for kind in ("read", "write", "status", "special"):
                items = getattr(container, kind, None)
                if not isinstance(items, list):
                    continue
                for item in items:
                    tok = getattr(item, "token", None)
                    if isinstance(tok, str) and tok:
                        symbols.add(tok)

        meta = getattr(route, "meta", None)
        if meta is not None:
            add_from_container(getattr(meta, "parameters", None))
        add_from_container(getattr(route, "parameters", None))
        return symbols

    @classmethod
    def _normalize_route_path_key(cls, path: Any) -> str:
        """Normalize a menu route path into a static-route lookup key."""
        if not isinstance(path, str):
            return ""
        token = path.strip().strip("/")
        if not token or token in {".", ".."}:
            return ""
        return token

    @classmethod
    def _route_has_child_routes(cls, route: Any) -> bool:
        """Return whether *route* has non-empty ``children``."""
        children = getattr(route, "children", None)
        return isinstance(children, list) and len(children) > 0

    @classmethod
    def _route_component_is_panel_shell(cls, route: Any) -> bool:
        """Return whether the route ``component`` names a known SPA shell view."""
        component = getattr(route, "component", None)
        if not isinstance(component, str) or not component.strip():
            return False
        comp = component.strip()
        if comp in _PANEL_SHELL_COMPONENT_MARKERS:
            return True
        return any(marker.casefold() in comp.casefold() for marker in _PANEL_SHELL_COMPONENT_MARKERS)

    @classmethod
    def _route_is_panel_shell(
        cls,
        route: Any,
        *,
        static_route_symbols: Mapping[str, set[str]] | None = None,
    ) -> bool:
        """Return whether *route* is a navigation shell without inline menu parameters.

        Shell routes still appear in the SPA side menu (e.g. ``MAINMENU_STREFY_CZASOWE``)
        but declare parameters in a separate static ``deviceMenu/static/<path>.ts`` chunk.
        """
        if not cls._route_allowed_in_module_item(route):
            return False
        if cls._collect_route_symbols(route):
            return False
        if cls._route_has_child_routes(route):
            return False

        path_key = cls._normalize_route_path_key(getattr(route, "path", None))
        if static_route_symbols is not None and path_key and path_key in static_route_symbols:
            return True
        if cls._route_component_is_panel_shell(route):
            return True

        raw_name = getattr(route, "name", None)
        return isinstance(raw_name, str) and _MENU_TITLE_TOKEN_RE.fullmatch(raw_name.strip()) is not None

    @classmethod
    def _dropdown_param_truthy(cls, raw: Any) -> bool:
        """Return whether a ParamStore value should keep a dropdown-gated route visible."""
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, int | float) and not isinstance(raw, bool):
            return raw != 0
        if isinstance(raw, str):
            stripped = raw.strip()
            return bool(stripped) and stripped.casefold() not in {"0", "false"}
        # JS treats empty arrays/objects as truthy; ``bool([])`` / ``bool({})`` do not.
        if isinstance(raw, list | dict):
            return True
        return bool(raw)

    @classmethod
    def _route_display_dropdown_visibility(
        cls,
        route: Any,
        flat_values: Mapping[str, Any] | None,
    ) -> tuple[bool, str]:
        """Evaluate SPA ``displayDropdown`` leftovers for route side-menu visibility.

        When ``flat_values`` is ``None``, ParamStore-key dropdowns are treated as
        visible (``visible:dropdown-unprimed``) so callers without a primed store
        do not lose gated panels. An empty mapping still means primed-but-missing.
        """
        meta = getattr(route, "meta", None)
        dropdown = getattr(meta, "display_dropdown", None) if meta is not None else None
        if dropdown is None:
            return True, "visible:no-dropdown"
        if isinstance(dropdown, bool):
            return (bool(dropdown), "visible:dropdown-true" if dropdown else "hidden:dropdown-false")
        if not isinstance(dropdown, str):
            return True, "visible:dropdown-unknown"
        token = dropdown.strip()
        if not token:
            return True, "visible:no-dropdown"
        if _ROUTE_DROPDOWN_VALUE_KEY_RE.fullmatch(token):
            if flat_values is None:
                return True, "visible:dropdown-unprimed"
            raw = flat_values.get(token)
            if raw is None:
                return False, "hidden:dropdown-missing-value"
            visible = cls._dropdown_param_truthy(raw)
            return visible, "visible:dropdown-value" if visible else "hidden:dropdown-value"
        lowered = token.casefold()
        if lowered in {"!![]", "true", "1"}:
            return True, "visible:dropdown-always"
        if lowered in {"![]", "false", "0"}:
            return False, "hidden:dropdown-false"
        return True, "visible:dropdown-unknown"

    @classmethod
    def route_visibility_dependency_keys(
        cls,
        route: Any,
        *,
        ancestors: tuple[Any, ...] = (),
    ) -> set[str]:
        """Return ParamStore keys that may affect route side-menu visibility."""
        keys: set[str] = set()
        meta = getattr(route, "meta", None)
        if meta is not None:
            params = getattr(meta, "parameters", None)
            if params is not None:
                status_items = getattr(params, "status", None)
                if isinstance(status_items, list):
                    for item in status_items:
                        group = getattr(item, "group", None) if not isinstance(item, dict) else item.get("group")
                        use = getattr(item, "use", None) if not isinstance(item, dict) else item.get("use")
                        number = getattr(item, "number", None) if not isinstance(item, dict) else item.get("number")
                        if isinstance(group, str) and isinstance(use, str) and isinstance(number, int):
                            keys.add(f"{group}.{use}{number}")
            dropdown = getattr(meta, "display_dropdown", None)
            if isinstance(dropdown, str):
                token = dropdown.strip()
                if _ROUTE_DROPDOWN_VALUE_KEY_RE.fullmatch(token):
                    keys.add(token)
        for ancestor in ancestors:
            ancestor_meta = getattr(ancestor, "meta", None)
            if ancestor_meta is None:
                continue
            dropdown = getattr(ancestor_meta, "display_dropdown", None)
            if not isinstance(dropdown, str):
                continue
            token = dropdown.strip()
            if _ROUTE_DROPDOWN_VALUE_KEY_RE.fullmatch(token):
                keys.add(token)
            elif token.isdigit():
                # Dropdown selection routes often key off a parent write parameter — callers
                # also track symbol-level deps; keep digit-only ancestor dropdown as a soft hint.
                keys.add(f"route_dropdown:{token}")
        return keys

    @classmethod
    def route_visibility_diagnostics(
        cls,
        route: Any,
        *,
        ancestors: tuple[Any, ...] = (),
        flat_values: Mapping[str, Any] | None = None,
        all_panels: bool = False,
        web_ui_only: bool = False,
    ) -> tuple[bool, str]:
        """Return whether a menu route should be treated as visible in the web UI.

        Mirrors static SPA ``isRouteVisible`` gates (module-item classification,
        installer/side-menu filters, ``displayDropdown`` leftovers). Dynamic status
        rules on individual parameters are handled separately via
        :meth:`parameter_visibility_diagnostics`.
        """
        if all_panels and not cls._route_allowed_in_module_item(route):
            return False, "hidden:not-module-item"
        if web_ui_only and not cls._route_is_end_user_web_ui(route, ancestors=ancestors):
            return False, "hidden:not-web-ui"
        # SPA hides a leaf when any ancestor ``displayDropdown`` gate is false.
        # Ancestor ``visible:*`` reasons (including ParamStore-true) do not short-circuit;
        # only a hidden ancestor rejects. Leaf keeps the early-return for non-default
        # visible dropdown reasons. ``flat_values is None`` keeps ParamStore gates
        # visible (unprimed); ``{}`` still means missing-key → hidden.
        for ancestor in ancestors:
            ancestor_visible, ancestor_reason = cls._route_display_dropdown_visibility(ancestor, flat_values)
            if not ancestor_visible:
                return False, ancestor_reason
        dropdown_visible, dropdown_reason = cls._route_display_dropdown_visibility(route, flat_values)
        if not dropdown_visible:
            return False, dropdown_reason
        if dropdown_reason not in {"visible:no-dropdown", "visible:default"}:
            return True, dropdown_reason
        return True, "visible:default"

    @classmethod
    def _resolve_route_symbols(
        cls,
        route: Any,
        *,
        static_route_symbols: Mapping[str, set[str]] | None = None,
    ) -> set[str]:
        """Collect route symbols including optional static-route token overlays."""
        symbols = cls._collect_route_symbols(route)
        if symbols:
            return symbols
        path_key = cls._normalize_route_path_key(getattr(route, "path", None))
        if static_route_symbols is not None and path_key:
            overlay = static_route_symbols.get(path_key)
            if overlay:
                return set(overlay)
        return symbols

    @classmethod
    def build_panel_groups_from_menu(
        cls,
        menu: MenuResult,
        *,
        all_panels: bool = False,
        web_ui_only: bool = False,
        routes_i18n: Mapping[str, Any] | None = None,
        flat_values: Mapping[str, Any] | None = None,
        static_route_symbols: Mapping[str, set[str]] | None = None,
    ) -> dict[str, list[str]]:
        """Build route-driven panel groups from a menu tree.

        When ``all_panels`` is enabled, every non-empty module-item route becomes a
        panel. Otherwise, only the canonical Boiler/DHW/Valve1 groups are returned.

        When ``web_ui_only`` is enabled, installer routes and side-menu-hidden
        routes are dropped (:meth:`_route_is_end_user_web_ui`) so the panel set
        matches everyday web-UI navigation. Per-parameter SPA visibility
        (``isParameterVisible`` / status bits) is applied by callers such as HA
        bootstrap UI filter mode.
        """
        routes_meta: list[tuple[str, str, str, set[str], tuple[Any, ...], Any]] = []
        for route, ancestors in cls._iter_routes_with_ancestors(menu.routes):
            if all_panels and not cls._route_allowed_in_module_item(route):
                continue
            if web_ui_only:
                route_visible, _ = cls.route_visibility_diagnostics(
                    route,
                    ancestors=ancestors,
                    flat_values=flat_values,
                    all_panels=all_panels,
                    web_ui_only=web_ui_only,
                )
                if not route_visible:
                    continue
            symbols = cls._resolve_route_symbols(route, static_route_symbols=static_route_symbols)
            if symbols:
                title = cls._route_title(route, routes_i18n=routes_i18n)
                name = str(getattr(route, "name", "") or "")
                path = str(getattr(route, "path", "") or "")
                routes_meta.append((title, name, path, symbols, ancestors, route))

        if all_panels:
            groups: dict[str, set[str]] = {}
            for _title, _name, _path, symbols, ancestors, route in routes_meta:
                panel_name = cls._panel_title_hierarchical(route=route, ancestors=ancestors, routes_i18n=routes_i18n)
                groups.setdefault(panel_name, set()).update(symbols)
            return {panel: sorted(symbols) for panel, symbols in groups.items()}

        def pick_by_route(
            route_markers: list[str],
            *,
            fallback_title_keywords: list[str],
            default_title: str,
        ) -> tuple[str, set[str]]:
            markers = {cls._normalize_text(m) for m in route_markers if m}
            out: set[str] = set()
            matched_title: str | None = None
            for title, name, path, symbols, _ancestors, _route in routes_meta:
                name_norm = cls._normalize_text(name)
                path_norm = cls._normalize_text(path)
                if any(marker and marker in (name_norm, path_norm) for marker in markers):
                    if matched_title is None:
                        matched_title = title
                    out |= symbols

            if out:
                return (matched_title or default_title), out

            want = [cls._normalize_text(k) for k in fallback_title_keywords]
            for title, _name, _path, symbols, _ancestors, _route in routes_meta:
                t = cls._normalize_text(title)
                if any(w and w in t for w in want):
                    if matched_title is None:
                        matched_title = title
                    out |= symbols
            return (matched_title or default_title), out

        boiler_title, boiler = pick_by_route(
            ["modules.menu.boiler", "boiler"],
            fallback_title_keywords=["boiler"],
            default_title="Boiler",
        )
        dhw_title, dhw = pick_by_route(
            ["modules.menu.dhw", "dhw"],
            fallback_title_keywords=["dhw"],
            default_title="DHW",
        )
        valve_title, valve = pick_by_route(
            ["modules.menu.valve1", "valve/1", "valve1"],
            fallback_title_keywords=["valve_1", "valve1"],
            default_title="Valve 1",
        )
        return {
            boiler_title: sorted(boiler),
            dhw_title: sorted(dhw),
            valve_title: sorted(valve),
        }

    @classmethod
    def panel_route_diagnostics_from_menu(
        cls,
        menu: MenuResult,
        *,
        all_panels: bool = False,
        web_ui_only: bool = False,
        routes_i18n: Mapping[str, Any] | None = None,
        flat_values: Mapping[str, Any] | None = None,
        static_route_symbols: Mapping[str, set[str]] | None = None,
    ) -> list[dict[str, Any]]:
        """Return per-route panel inclusion diagnostics.

        This helper is intended for CLI debugging to explain why specific
        routes are included/excluded from panel rendering.
        """
        diagnostics: list[dict[str, Any]] = []
        for route, ancestors in cls._iter_routes_with_ancestors(menu.routes):
            title = cls._route_title(route, routes_i18n=routes_i18n)
            panel_title = cls._panel_title_hierarchical(route=route, ancestors=ancestors, routes_i18n=routes_i18n)
            name = str(getattr(route, "name", "") or "")
            path = str(getattr(route, "path", "") or "")
            symbols = cls._resolve_route_symbols(route, static_route_symbols=static_route_symbols)
            is_shell = cls._route_is_panel_shell(route, static_route_symbols=static_route_symbols)
            route_visible, route_vis_reason = cls.route_visibility_diagnostics(
                route,
                ancestors=ancestors,
                flat_values=flat_values,
                all_panels=all_panels,
                web_ui_only=web_ui_only,
            )
            web_visible, web_vis_reason = cls.route_visibility_diagnostics(
                route,
                ancestors=ancestors,
                flat_values=flat_values,
                all_panels=all_panels,
                web_ui_only=True,
            )
            component = getattr(route, "component", None)
            meta = getattr(route, "meta", None)
            side = getattr(meta, "is_visible_on_side_menu", None) if meta is not None else None
            dropdown = getattr(meta, "display_dropdown", None) if meta is not None else None

            accepted = True
            reason = "accepted"

            if all_panels:
                if not cls._route_allowed_in_module_item(route):
                    accepted = False
                    reason = "rejected:not-module-item"
                elif web_ui_only and not cls._route_is_end_user_web_ui(route, ancestors=ancestors):
                    accepted = False
                    reason = "rejected:not-web-ui"
                elif web_ui_only and not route_visible:
                    accepted = False
                    reason = f"rejected:route-hidden:{route_vis_reason}"
                elif not symbols:
                    accepted = False
                    reason = "rejected:no-symbols"
            else:
                if web_ui_only and not cls._route_is_end_user_web_ui(route, ancestors=ancestors):
                    accepted = False
                    reason = "rejected:not-web-ui"
                elif web_ui_only and not route_visible:
                    accepted = False
                    reason = f"rejected:route-hidden:{route_vis_reason}"
                elif not symbols:
                    accepted = False
                    reason = "rejected:no-symbols"

            diagnostics.append(
                {
                    "title": title,
                    "panel_title": panel_title,
                    "name": name,
                    "path": path,
                    "component": str(component) if component is not None else None,
                    "is_visible_on_side_menu": side,
                    "display_dropdown": dropdown,
                    "symbol_count": len(symbols),
                    "panel_shell": is_shell,
                    "route_visible": route_visible,
                    "route_visibility_reason": route_vis_reason,
                    "web_ui_visible": web_visible,
                    "web_ui_visibility_reason": web_vis_reason,
                    "accepted": accepted,
                    "reason": reason,
                }
            )
        return diagnostics

    async def _static_route_symbols_for_menu(self, menu: MenuResult) -> dict[str, set[str]]:
        """Discover static-route token overlays for shell routes in *menu*."""
        assets = self._assets
        if not hasattr(assets, "discover_static_route_tokens"):
            return {}
        out: dict[str, set[str]] = {}
        for route, _ancestors in self._iter_routes_with_ancestors(menu.routes):
            path_key = self._normalize_route_path_key(getattr(route, "path", None))
            if not path_key or path_key in out:
                continue
            if not self._route_is_panel_shell(route):
                continue
            try:
                tokens = await assets.discover_static_route_tokens(path_key)
            except Exception:
                LOG.exception("Static route token discovery failed for %s", path_key)
                tokens = set()
            if tokens:
                out[path_key] = set(tokens)
        return out

    async def build_panel_groups(
        self,
        *,
        device_menu: int,
        permissions: Iterable[str] | None = None,
        all_panels: bool = False,
        web_ui_only: bool = False,
        flat_values: Mapping[str, Any] | None = None,
        use_store_flat_values: bool = True,
    ) -> dict[str, list[str]]:
        """Build panel groups from module menu for selected permissions."""
        menu = await self.get_module_menu(device_menu=device_menu, permissions=permissions)
        routes_i18n = await self._panel_title_i18n(menu)
        static_route_symbols = await self._static_route_symbols_for_menu(menu)
        if flat_values is not None:
            values: Mapping[str, Any] | None = flat_values
        elif not use_store_flat_values:
            values = None
        else:
            # Empty implicit store ≡ unprimed (``None``), so displayDropdown stays
            # ``visible:dropdown-unprimed``. Callers pass ``{}`` explicitly for missing-key hide.
            flattened = self._store.flatten()
            values = flattened if flattened else None
        return self.build_panel_groups_from_menu(
            menu,
            all_panels=all_panels,
            web_ui_only=web_ui_only,
            routes_i18n=routes_i18n,
            flat_values=values,
            static_route_symbols=static_route_symbols,
        )

    async def panel_route_diagnostics(
        self,
        *,
        device_menu: int,
        permissions: Iterable[str] | None = None,
        all_panels: bool = False,
        web_ui_only: bool = False,
        flat_values: Mapping[str, Any] | None = None,
        use_store_flat_values: bool = True,
    ) -> list[dict[str, Any]]:
        """Return route diagnostics for panel inclusion filtering."""
        menu = await self.get_module_menu(device_menu=device_menu, permissions=permissions)
        routes_i18n = await self._panel_title_i18n(menu)
        static_route_symbols = await self._static_route_symbols_for_menu(menu)
        if flat_values is not None:
            values: Mapping[str, Any] | None = flat_values
        elif not use_store_flat_values:
            values = None
        else:
            flattened = self._store.flatten()
            values = flattened if flattened else None
        return self.panel_route_diagnostics_from_menu(
            menu,
            all_panels=all_panels,
            web_ui_only=web_ui_only,
            routes_i18n=routes_i18n,
            flat_values=values,
            static_route_symbols=static_route_symbols,
        )

    async def resolve_label(self, symbol: str) -> str | None:
        """Resolve label strictly from mapping `name` token."""
        mapping = await self.get_param_mapping(symbol)
        if mapping is not None and isinstance(mapping.raw, Mapping):
            raw_name = mapping.raw.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                resolved_from_name = await self._resolve_i18n_token(raw_name.strip())
                if isinstance(resolved_from_name, str) and resolved_from_name.strip():
                    return resolved_from_name
                return None
        return None

    async def resolve_unit(self, unit_code: Any) -> str | dict[str, str] | None:
        """Resolve unit metadata to a human-readable label or enumeration mapping."""
        return await self._i18n.resolve_unit(unit_code)

    async def resolve_raw_display_value(self, raw: Any, *, unit_code: Any) -> Any:
        """Return a display-ready scalar for activity/alarm feeds (enum, i18n, transforms).

        Applies the same unit-descriptor numeric transforms as :meth:`resolve_value`
        while preserving enum label lookup against the raw upstream scalar.
        """
        if unit_code is None or raw is None:
            return raw

        unit_meta = await self._resolve_unit_meta(raw_unit_code=unit_code)
        unit_options = self._unit_options_map(unit_meta)
        if unit_options is None:
            unit = await self.resolve_unit(unit_code)
            unit_options = self._unit_options_map(unit)

        label = self._unit_mapping_value_label(unit_options, raw)
        if label is not None:
            resolved = await self._resolve_units_value_token(label)
            return resolved if resolved is not None else label

        transform_expr = unit_meta.get("value") if isinstance(unit_meta, Mapping) else None
        display_val = self._apply_numeric_transform(raw, transform_expr)
        if isinstance(display_val, str):
            resolved_display = await self._resolve_units_value_token(display_val)
            if isinstance(resolved_display, str):
                return resolved_display
        return display_val

    async def resolve_module_connection_labels(self, *, lang: str | None = None) -> dict[str, str]:
        """Return SPA module connection-panel labels from the ``module`` i18n namespace."""
        return await self._i18n.resolve_module_connection_labels(lang=lang)

    @staticmethod
    def _to_float_literal(raw: str) -> float | None:
        text = raw.strip()
        if not text:
            return None
        if text.startswith("."):
            text = f"0{text}"
        if text.startswith("-."):
            text = text.replace("-.", "-0.", 1)
        try:
            return float(text)
        except ValueError:
            return None

    @classmethod
    def _normalize_js_expression(cls, text: str) -> str:
        """Rewrite obfuscated JS syntax into the plain forms the transform patterns expect.

        Upstream ships the web app obfuscated, which turns ``x.toFixed(1)`` into
        ``x['toFixed'](0x1)``. Normalizing bracket member access and radix literals lets one
        set of patterns match both the readable and the obfuscated build.

        Args:
            text: Raw expression source.

        Returns:
            The expression with bracket member access and radix literals in plain form.
        """
        normalized = _JS_BRACKET_MEMBER_RE.sub(r".\1", text)
        return _JS_RADIX_LITERAL_RE.sub(lambda m: str(int(m.group(0), 0)), normalized)

    @classmethod
    def _parse_numeric_transform(cls, raw_expr: Any) -> _NumericTransform | None:
        if not isinstance(raw_expr, str):
            return None

        text = cls._normalize_js_expression(raw_expr.strip())
        if not text:
            return None

        arrow_match = re.search(r"=>\s*(.+)$", text)
        if arrow_match is None:
            return None

        body = arrow_match.group(1).strip().rstrip(";")
        if body.startswith("{"):
            return None

        body_norm = re.sub(r"\s+", "", body)

        precision: int | None = None
        # Readable builds wrap the operand in parentheses; obfuscated ones do not.
        rounded_match = re.match(r"^Number\(\((.+)\)\.toFixed\((\d+)\)\)$", body_norm) or re.match(
            r"^Number\((.+)\)\.toFixed\((\d+)\)$", body_norm
        )
        if rounded_match is not None:
            body_norm = rounded_match.group(1).strip()
            precision = int(rounded_match.group(2))

        var_name = r"[A-Za-z_$][\w$]*"

        mul_match = re.match(rf"^({var_name})\*([+-]?(?:\d+\.\d+|\d+|\.\d+))$", body_norm)
        if mul_match is not None:
            factor = cls._to_float_literal(mul_match.group(2))
            if factor is None:
                return None
            return _NumericTransform(shift=0.0, factor=factor, precision=precision)

        div_match = re.match(rf"^({var_name})/([+-]?(?:\d+\.\d+|\d+|\.\d+))$", body_norm)
        if div_match is not None:
            divisor = cls._to_float_literal(div_match.group(2))
            if divisor is None or divisor == 0.0:
                return None
            return _NumericTransform(shift=0.0, factor=1.0 / divisor, precision=precision)

        affine_match = re.match(
            rf"^\(({var_name})([+-])([+-]?(?:\d+\.\d+|\d+|\.\d+))\)\*([+-]?(?:\d+\.\d+|\d+|\.\d+))$",
            body_norm,
        )
        if affine_match is not None:
            offset = cls._to_float_literal(affine_match.group(3))
            factor = cls._to_float_literal(affine_match.group(4))
            if offset is None or factor is None:
                return None
            shift = -offset if affine_match.group(2) == "-" else offset
            return _NumericTransform(shift=shift, factor=factor, precision=precision)

        # Shift-only, e.g. unit 47 ``x => x - 127`` / ``_0xac50fa=>_0xac50fa-0x7f``.
        shift_only = re.match(rf"^({var_name})([+-])([+-]?(?:\d+\.\d+|\d+|\.\d+))$", body_norm)
        if shift_only is not None:
            offset = cls._to_float_literal(shift_only.group(3))
            if offset is None:
                return None
            shift = -offset if shift_only.group(2) == "-" else offset
            return _NumericTransform(shift=shift, factor=1.0, precision=precision)

        return None

    @classmethod
    def _is_unit66_time_expr(cls, raw_expr: str) -> bool:
        """Return True if *raw_expr* is the unit-66 HH:MM formatter.

        The readable spelling hard-codes ``e`` and double quotes; the obfuscated
        bundle mangles the identifier, hex-encodes the literals, and uses
        ``Math['floor']`` / ``['padStart']``. After ``_normalize_js_expression``
        both collapse to: a ``units.202.0`` zero-token, ``(x-1)*10``, and
        ``padStart(2, ...)``.
        """
        collapsed = re.sub(r"\s+", "", cls._normalize_js_expression(raw_expr))
        if "units.202.0" not in collapsed:
            return False
        if _UNIT66_PADSTART_RE.search(collapsed) is None:
            return False
        return _UNIT66_SHIFT_TEN_RE.search(collapsed) is not None

    @classmethod
    def _format_unit66_time(cls, raw_value: Any) -> Any:
        """Format a unit-66 raw value as ``units.202.0`` or ``HH:MM``."""
        if isinstance(raw_value, bool):
            return raw_value
        try:
            numeric = int(float(raw_value))
        except (TypeError, ValueError):
            return raw_value
        if numeric == 0:
            return "units.202.0"
        total_minutes = (numeric - 1) * 10
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"

    @classmethod
    def _apply_numeric_transform(cls, raw_value: Any, raw_expr: Any) -> Any:
        if isinstance(raw_expr, str) and cls._is_unit66_time_expr(raw_expr):
            return cls._format_unit66_time(raw_value)

        if isinstance(raw_value, bool):
            return raw_value

        numeric_value: float
        if isinstance(raw_value, (int, float)):
            numeric_value = float(raw_value)
        elif isinstance(raw_value, str):
            text = raw_value.strip()
            if not text:
                return raw_value
            try:
                numeric_value = float(text)
            except ValueError:
                return raw_value
        else:
            return raw_value

        transform = cls._parse_numeric_transform(raw_expr)
        if transform is None:
            return raw_value

        transformed = (numeric_value + transform.shift) * transform.factor
        if transform.precision is not None:
            return round(transformed, transform.precision)
        if float(transformed).is_integer():
            return int(transformed)
        return transformed

    @staticmethod
    def _unit_options_map(unit: Any) -> dict[str, str] | None:
        if not isinstance(unit, Mapping):
            return None

        options_any = unit.get("options")
        if isinstance(options_any, Mapping):
            return {str(key).strip(): str(val).strip() for key, val in options_any.items()}

        special = {"text", "value", "valuePrepare", "colors"}
        if any(key in unit for key in special):
            return None

        return {str(key).strip(): str(val).strip() for key, val in unit.items()}

    async def _unit_display_value(self, unit: Any) -> str | dict[str, str] | None:
        if not isinstance(unit, Mapping):
            return unit if isinstance(unit, str) else None

        text_raw = unit.get("text")
        if not isinstance(text_raw, str) or not text_raw.strip():
            options = self._unit_options_map(unit)
            if options is not None:
                return options
            return {str(key).strip(): str(val).strip() for key, val in unit.items()}

        text_token = text_raw.strip()
        resolved_token = await self._resolve_i18n_token(text_token)
        if resolved_token is not None:
            return resolved_token

        return text_token

    @staticmethod
    def _normalize_unit_code(raw_unit_code: Any) -> str | None:
        if isinstance(raw_unit_code, int):
            return str(raw_unit_code)
        if isinstance(raw_unit_code, float):
            return str(int(raw_unit_code)) if raw_unit_code.is_integer() else None
        if isinstance(raw_unit_code, str):
            text = raw_unit_code.strip()
            if not text:
                return None
            if text.isdigit():
                return text
            try:
                as_float = float(text)
            except ValueError:
                return None
            return str(int(as_float)) if as_float.is_integer() else None
        return None

    async def _resolve_unit_meta(self, *, raw_unit_code: Any) -> Any:
        """Resolve canonical unit metadata for a raw unit code.

        Source of truth is the index-defined units descriptor table.
        """
        try:
            descriptor = await self._assets.get_unit_descriptor(raw_unit_code)
        except Exception:
            descriptor = None
        if isinstance(descriptor, Mapping) and descriptor:
            return dict(descriptor)

        normalized_code = self._normalize_unit_code(raw_unit_code)
        if normalized_code is not None:
            return {"text": f"units.{normalized_code}"}
        return None

    async def _resolve_units_value_token(self, label: str | None) -> str | None:
        if not isinstance(label, str):
            return None

        current = label.strip()
        if not current:
            return None

        resolved = await self._resolve_i18n_token(current)
        return resolved if resolved is not None else current

    async def _resolve_i18n_token(self, token: str | None) -> str | None:
        if not isinstance(token, str):
            return None

        current = token.strip()
        if not current:
            return None

        first_dot = current.find(".")
        if first_dot <= 0:
            return None
        namespace = current[:first_dot]
        path = current[first_dot + 1 :]

        if not namespace or not path:
            return None

        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", namespace):
            return None

        table = await self._i18n.get_namespace(namespace)

        resolved = self._lookup_dotted_path_raw(table, path)
        depth = 0
        while isinstance(resolved, str) and depth < 4:
            next_dot = resolved.find(".")
            if next_dot <= 0:
                break

            next_namespace = resolved[:next_dot]
            next_path = resolved[next_dot + 1 :]
            if not next_namespace or not next_path:
                break
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", next_namespace):
                break

            next_table = await self._i18n.get_namespace(next_namespace)
            next_value = self._lookup_dotted_path_raw(next_table, next_path)
            if not isinstance(next_value, str):
                break
            resolved = next_value
            depth += 1

        if isinstance(resolved, str):
            return resolved
        return None

    @staticmethod
    def _addr_key(pool: str, chan: str, idx: int) -> str:
        return f"{pool}.{chan}{idx}"

    @staticmethod
    def _is_status_rule_entry(entry: Any) -> bool:
        """Return whether *entry* looks like a STATUS ``if``/``elseif``/``then``/``else`` rule."""
        return isinstance(entry, Mapping) and any(key in entry for key in ("if", "elseif", "then", "else"))

    @classmethod
    def _is_status_rule_list(cls, entries: Any) -> bool:
        """Return whether *entries* is a non-empty list containing STATUS rule dicts."""
        return isinstance(entries, list) and bool(entries) and any(cls._is_status_rule_entry(entry) for entry in entries)

    @staticmethod
    def _is_address_selector_entry(entry: Any) -> bool:
        """Return whether *entry* is a ``{group, number, use[, convert, times]}`` register selector."""
        if not isinstance(entry, Mapping):
            return False
        group = entry.get("group")
        number = entry.get("number")
        use = entry.get("use")
        return isinstance(group, str) and bool(group) and isinstance(number, int) and isinstance(use, str) and bool(use)

    @classmethod
    def _is_address_selector_list(cls, entries: Any) -> bool:
        """Return whether *entries* is a non-empty list of register address selectors.

        Distinguishes multi-register address lists (#327) — e.g. ``[{"group": "P4",
        "number": 59, "use": "v", "convert": "..."}, {..., "times": 65536}]`` — from
        STATUS-style ``if``/``elseif``/``then``/``else`` rule lists, which happen to
        share the same ``raw["value"]`` / ``paths["value"]`` slot.
        """
        if not isinstance(entries, list) or not entries:
            return False
        if cls._is_status_rule_list(entries):
            return False
        return any(cls._is_address_selector_entry(entry) for entry in entries)

    @classmethod
    def _address_selectors_need_compose(cls, entries: list[Any]) -> bool:
        """Return whether address selectors require multi-register composition.

        Ordinary SPA parameters use a *single* ``{group, number, use}`` selector with
        no ``convert`` / non-default ``times``. Those must not go through
        :meth:`compose_mapping_register_value`: composition is only for multi-word /
        converted / scaled selector lists. Plain single-selector mappings return
        ``None`` so callers fall back to a direct store read (preserving the live
        value type, including half-degree floats such as ``40.5``).
        """
        selectors = [entry for entry in entries if cls._is_address_selector_entry(entry)]
        if len(selectors) >= 2:
            return True
        if len(selectors) != 1:
            return False
        entry = selectors[0]
        if entry.get("convert"):
            return True
        times = entry.get("times")
        return isinstance(times, (int, float)) and not isinstance(times, bool) and float(times) != 1.0

    @classmethod
    def _mapping_has_computed_rules(cls, mapping: ParamMap | None) -> bool:
        """Return whether *mapping* carries STATUS-style rule-based computed values.

        Only ``if``/``elseif``/``then``/``else`` rule lists count as computed.
        Address-selector lists describing multi-register values (``group``/``number``/
        ``use`` [+ ``convert``/``times``]) are excluded — those are composed via
        :meth:`compose_mapping_register_value` instead (#327).
        """
        if mapping is None:
            return False
        raw = mapping.raw
        if isinstance(raw, Mapping):
            any_rules = raw.get("any")
            if isinstance(any_rules, list) and any_rules:
                return True
            if cls._is_status_rule_list(raw.get("value")):
                return True
        paths = mapping.paths
        return isinstance(paths, Mapping) and cls._is_status_rule_list(paths.get("value"))

    @classmethod
    def compose_mapping_register_value(cls, store: ParamStore, mapping: Any) -> int | float | None:
        """Compose a multi-register (multi-word) parameter value from live register words.

        Some SPA parameters address more than one register as *address selectors*
        rather than a single value channel — e.g. ``PARAM_P4_59`` ("Czas pracy
        podajnika", #327)::

            [
                {"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"},
                {"group": "P4", "number": 60, "use": "v", "convert": "_0x35dce1", "times": 65536},
            ]

        Each selector reads ``{group}.{use[0]}{number}`` from *store*
        (``group`` already includes the ``P`` prefix, e.g. ``P4.v59``). Minified
        SPA bundles emit a different ``convert`` helper identifier per build, so
        this only checks *presence* of a truthy ``convert`` value rather than
        matching a specific name: presence means the register word must be
        coerced with ``int(raw) & 0xFFFF`` (unsigned 16-bit) before multiplying by
        ``times`` (default ``1``) and summing across selectors. Words without a
        ``convert`` entry keep their raw (possibly signed) value.

        Args:
            store: Live parameter store to read register words from.
            mapping: A :class:`ParamMap`, or a plain dict with ``paths``/``raw``
                (and, optionally, ``channels``) keys — the shape of the cached
                entity descriptors Home Assistant persists in ``entry.data``.

        Returns:
            The composed value as ``int`` when the sum is a whole number,
            otherwise ``float``. Returns ``None`` when *mapping* does not carry
            a multi-register / ``convert`` / non-default-``times`` selector list
            (plain single ``{group, number, use}`` paths fall through to a direct
            store read), or when none of the selectors have a live value in *store*.
        """
        raw: Any
        paths: Any
        if isinstance(mapping, ParamMap):
            raw = mapping.raw
            paths = mapping.paths
        elif isinstance(mapping, Mapping):
            raw = mapping.get("raw")
            paths = mapping.get("paths")
        else:
            return None

        entries: list[Any] | None = None
        if isinstance(paths, Mapping):
            candidate = paths.get("value")
            if cls._is_address_selector_list(candidate):
                entries = candidate
        if entries is None and isinstance(raw, Mapping):
            candidate = raw.get("value")
            if cls._is_address_selector_list(candidate):
                entries = candidate
        if entries is None or not cls._address_selectors_need_compose(entries):
            return None

        total = 0.0
        found_any = False
        for selector in entries:
            if not isinstance(selector, Mapping):
                continue
            group = selector.get("group")
            number = selector.get("number")
            use = selector.get("use")
            if not isinstance(group, str) or not isinstance(number, int) or not isinstance(use, str) or not use:
                continue
            fam = store.get_family(group, number)
            if fam is None:
                continue
            raw_word = fam.get(use[0])
            if raw_word is None:
                continue
            try:
                word_float = float(raw_word)
            except (TypeError, ValueError):
                continue

            found_any = True
            if selector.get("convert"):
                word_value: int | float = int(word_float) & 0xFFFF
            elif word_float.is_integer():
                word_value = int(word_float)
            else:
                word_value = word_float

            times_raw = selector.get("times")
            multiplier: int | float = times_raw if isinstance(times_raw, (int, float)) and not isinstance(times_raw, bool) else 1
            total += word_value * multiplier

        if not found_any:
            return None
        return int(total) if float(total).is_integer() else total

    @staticmethod
    def _mapping_has_simple_direct_value_path(mapping: ParamMap | None) -> bool:
        if mapping is None or not isinstance(mapping.paths, Mapping):
            return False
        values = mapping.paths.get("value")
        if not isinstance(values, list) or not values:
            return False

        for entry in values:
            try:
                group = entry.get("group")
                number = entry.get("number")
                use = entry.get("use")
            except AttributeError:
                continue
            if isinstance(group, str) and isinstance(number, int) and isinstance(use, str):
                return True
        return False

    @staticmethod
    def _mapping_primary_address(mapping: Any, *, symbol: str | None = None) -> tuple[str, str, int] | None:
        """Best-effort extraction of (pool, chan, idx) from a mapping object."""

        def _normalize_pool(pool: str | int) -> str | None:
            if isinstance(pool, int):
                return f"P{pool}"
            if isinstance(pool, str) and pool.strip():
                return pool.strip()
            return None

        def _normalize_idx(idx: int | str) -> int | None:
            if isinstance(idx, int):
                return idx
            try:
                return int(idx)
            except (TypeError, ValueError):
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

        def _collect(node: Any, acc: list[tuple[str, str | None, int]]) -> None:
            if isinstance(node, dict):
                pool_raw = node.get("group") if "group" in node else node.get("pool")
                num_raw = node.get("number") if "number" in node else node.get("index")
                if num_raw is None:
                    num_raw = node.get("idx")
                use = node.get("use") or node.get("path") or node.get("pathType")
                if use is None:
                    use = node.get("chan")

                pool = _normalize_pool(pool_raw) if isinstance(pool_raw, (str, int)) else None
                idx = _normalize_idx(num_raw) if isinstance(num_raw, (int, str)) else None
                if pool is not None and idx is not None:
                    acc.append((pool, str(use) if isinstance(use, str) else None, idx))
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
        bracket = _JS_BRACKET_MEMBER_RE.search(cleaned)
        if bracket is not None:
            return bracket.group(1)
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
            if use_raw is None:
                use_raw = entry.get("chan")
            number_raw = entry.get("number")
            if number_raw is None:
                number_raw = entry.get("index")
            if number_raw is None:
                number_raw = entry.get("idx")
            if not isinstance(group, str) or not isinstance(use_raw, str) or number_raw is None:
                continue
            try:
                number = int(number_raw)
            except (TypeError, ValueError):
                continue
            addr = cls._mapping_primary_address({"group": group, "number": number, "use": use_raw})
            if addr is None:
                continue
            chan = addr[1]
            address = f"{group}.{chan}{number}"
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

    @staticmethod
    def _unit_mapping_value_label(unit: str | dict[str, str] | None, value: Any) -> str | None:
        if not isinstance(unit, Mapping) or value is None:
            return None

        candidates: list[str] = []

        def _add_candidate(candidate: Any) -> None:
            if candidate is None:
                return
            text = str(candidate).strip()
            if text and text not in candidates:
                candidates.append(text)

        if isinstance(value, str):
            stripped = value.strip()
            _add_candidate(stripped)
            try:
                as_int = int(stripped)
            except (TypeError, ValueError):
                as_int = None
            if as_int is not None:
                _add_candidate(as_int)
            else:
                try:
                    as_float = float(stripped)
                except (TypeError, ValueError):
                    as_float = None
                if as_float is not None and as_float.is_integer():
                    _add_candidate(int(as_float))
        elif isinstance(value, bool):
            _add_candidate(int(value))
        elif isinstance(value, int):
            _add_candidate(value)
        elif isinstance(value, float):
            _add_candidate(value)
            if value.is_integer():
                _add_candidate(int(value))
        else:
            _add_candidate(value)

        for key in candidates:
            mapped = unit.get(key)
            if isinstance(mapped, str) and mapped.strip():
                return mapped.strip()

        def _normalize_symbolic(text: str) -> str:
            normalized = text.strip()
            if normalized.startswith("[") and normalized.endswith("]") and len(normalized) > 2:
                normalized = normalized[1:-1].strip()
            # Unit option tables keep enums as ``BoilerState['STOP']`` while computed
            # STATUS rules emit the cleaned tag ``STOP``.
            bracket = _JS_BRACKET_MEMBER_RE.search(normalized)
            if bracket is not None:
                return bracket.group(1)
            if "." in normalized:
                normalized = normalized.split(".", 1)[1].strip()
            return normalized

        normalized_candidates = {
            _normalize_symbolic(str(candidate))
            for candidate in candidates
            if isinstance(candidate, str) and _normalize_symbolic(str(candidate))
        }
        if normalized_candidates:
            for raw_key, mapped in unit.items():
                if not isinstance(mapped, str) or not mapped.strip():
                    continue
                key_norm = _normalize_symbolic(str(raw_key))
                if key_norm and key_norm in normalized_candidates:
                    return mapped.strip()
        return None

    @staticmethod
    def _to_bool_value(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(int(value))
        if isinstance(value, str):
            norm = value.strip().casefold()
            if norm in {"!0", "true", "1"}:
                return True
            if norm in {"!1", "false", "0"}:
                return False
        return None

    @staticmethod
    def _eval_status_rule(rule: dict[str, Any], flat_values: Mapping[str, Any]) -> bool:
        expected = rule.get("expected")
        operation = str(rule.get("operation") or "")
        refs = rule.get("value")
        if not isinstance(refs, list) or not refs:
            return False

        ref = refs[0]
        if not isinstance(ref, dict):
            return False

        group = ref.get("group")
        use = ref.get("use")
        number = ref.get("number")
        if not isinstance(group, str) or not isinstance(use, str) or not isinstance(number, int):
            return False

        key = f"{group}.{use}{number}"
        current = flat_values.get(key)
        expected_norm = None if isinstance(expected, str) and expected.strip() == "void 0" else expected

        if operation == "e.equalTo":
            return bool(current == expected_norm)
        if operation == "e.notEqualTo":
            return bool(current != expected_norm)

        if current is None:
            return False

        if operation in {"e.matches", "e.notMatches"} and isinstance(expected_norm, str):
            pattern = ComputedValueEvaluator._regex_from_literal(expected_norm)
            if pattern is None:
                return False
            matched = bool(pattern.search(str(current)))
            return matched if operation == "e.matches" else not matched

        return False

    @staticmethod
    def _status_paths_from_raw_status(raw_status: Any) -> list[dict[str, Any]]:
        status_paths: list[dict[str, Any]] = []
        if not isinstance(raw_status, Mapping):
            return status_paths

        for condition, entries in raw_status.items():
            if not isinstance(entries, list):
                continue
            # Normalize ``ParameterStatus['INVISIBLE']`` / ``[t.INVISIBLE]`` to ``INVISIBLE``
            # so visibility matches the SPA ``status.invisible`` flag name.
            condition_name = ParamResolver._clean_symbolic_tag(condition) or str(condition)
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                row = dict(entry)
                row["condition"] = condition_name
                status_paths.append(row)
        return status_paths

    @classmethod
    def _select_raw_any_branch(cls, any_rules: Any, flat_values: Mapping[str, Any]) -> Mapping[str, Any] | None:
        if not isinstance(any_rules, list):
            return None

        explicit_else: Mapping[str, Any] | None = None
        for rule in any_rules:
            if not isinstance(rule, Mapping):
                continue

            conds = rule.get("if")
            if conds is None:
                conds = rule.get("elseif")

            if isinstance(conds, list) and conds:
                ok = all(isinstance(c, dict) and cls._eval_status_rule(c, flat_values) for c in conds)
                if ok:
                    then_val = rule.get("then")
                    return then_val if isinstance(then_val, Mapping) else None

            if explicit_else is None:
                else_val = rule.get("else")
                if isinstance(else_val, Mapping):
                    explicit_else = else_val

        return explicit_else

    @classmethod
    def _status_paths_for_visibility(cls, mapping: Mapping[str, Any], flat_values: Mapping[str, Any]) -> list[dict[str, Any]]:
        paths = mapping.get("paths")
        if isinstance(paths, Mapping):
            status_paths_any = paths.get("status")
            if isinstance(status_paths_any, list):
                status_paths = [entry for entry in status_paths_any if isinstance(entry, dict)]
                if status_paths:
                    return status_paths

        raw = mapping.get("raw")
        if not isinstance(raw, Mapping):
            return []

        root_status = cls._status_paths_from_raw_status(raw.get("status"))
        if root_status:
            return root_status

        active = cls._select_raw_any_branch(raw.get("any"), flat_values)
        if isinstance(active, Mapping):
            branch_status = cls._status_paths_from_raw_status(active.get("status"))
            if branch_status:
                return branch_status

        return []

    @classmethod
    def _status_condition_name(cls, condition: Any) -> str:
        """Return the public status flag name for a path/raw condition token."""
        if not isinstance(condition, str):
            return ""
        return (cls._clean_symbolic_tag(condition) or condition).strip()

    @classmethod
    def _status_flag_value(
        cls,
        *,
        status_paths: list[dict[str, Any]],
        flag_condition: str,
        flat_values: Mapping[str, Any],
    ) -> bool | None:
        explicit_else: bool | None = None
        wanted = cls._status_condition_name(flag_condition).casefold()
        if not wanted:
            return None

        for status in status_paths:
            condition = cls._status_condition_name(status.get("condition")).casefold()
            if condition != wanted:
                continue

            group = status.get("group")
            use = status.get("use")
            number = status.get("number")
            bit = status.get("bit")
            if isinstance(group, str) and isinstance(use, str) and isinstance(number, int) and isinstance(bit, int):
                key = f"{group}.{use}{number}"
                raw = flat_values.get(key)
                if isinstance(raw, int):
                    return bool((raw >> bit) & 1)
                return None

            ifs = status.get("if")
            then_val = cls._to_bool_value(status.get("then"))
            if (
                isinstance(ifs, list)
                and then_val is not None
                and all(isinstance(rule, dict) and cls._eval_status_rule(rule, flat_values) for rule in ifs)
            ):
                return then_val

            if "else" in status:
                explicit_else = cls._to_bool_value(status.get("else"))

        return explicit_else

    def is_parameter_visible_like_app(
        self,
        *,
        desc: Mapping[str, Any],
        resolved: Any,
        flat_values: Mapping[str, Any] | None = None,
    ) -> bool:
        """Return bool visibility based on app-like status semantics."""
        visible, _ = self.parameter_visibility_diagnostics(desc=desc, resolved=resolved, flat_values=flat_values)
        return visible

    def parameter_visibility_diagnostics(
        self,
        *,
        desc: Mapping[str, Any],
        resolved: Any,
        flat_values: Mapping[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Return visibility using the same status semantics as the official app.

        Mirrors SPA ``isParameterVisible`` status checks in ``index-*.js``:

        - when the ``INVISIBLE`` flag resolves truthy, the parameter is hidden;
        - when the ``DEVICE_AVAILABLE`` flag resolves falsey, the parameter is hidden;
        - when a flag path is present but its backing value is missing, the flag
          is treated as unknown and does not hide the parameter.

        Condition tokens are normalized (``ParameterStatus['INVISIBLE']``,
        ``[t.INVISIBLE]``, ``INVISIBLE``) before comparison.

        Notes:
        - This helper does not enforce the SPA ``parameter.value !== undefined``
          gate. Callers (HA bootstrap) drop ``no_display_value`` separately.
        """
        values = flat_values if flat_values is not None else self._store.flatten()

        mapping = desc.get("mapping")
        if not isinstance(mapping, Mapping):
            return True, "visible:no-mapping"

        raw_mapping = mapping.get("raw")
        if isinstance(raw_mapping, Mapping) and any(key in raw_mapping for key in ("value2", "value3", "value4")):
            return False, "hidden:composite-component"

        status_paths = self._status_paths_for_visibility(mapping, values)
        if not status_paths:
            return True, "visible:no-paths"

        # SPA stores ParameterStatus.INVISIBLE as ``'invisible'``; catalog/paths keep
        # the public member ``INVISIBLE``. Match either spelling after cleanup.
        invisible = self._status_flag_value(status_paths=status_paths, flag_condition="INVISIBLE", flat_values=values)
        if invisible is True:
            return False, "hidden:invisible"

        device_available = self._status_flag_value(
            status_paths=status_paths,
            flag_condition="DEVICE_AVAILABLE",
            flat_values=values,
        )
        if device_available is False:
            return False, "hidden:device-unavailable"

        return True, "visible:default"

    async def resolve_value(self, symbol: str) -> ResolvedValue:
        """Resolve a symbol to a unified display value (direct or computed)."""
        mapping = await self.get_param_mapping(symbol)
        addr_tuple = self._mapping_canonical_address(symbol, mapping)

        address_key: str | None = None
        unit: str | dict[str, str] | None = None
        unit_meta: str | dict[str, str] | None = None
        raw_unit_code: Any = None
        mapping_unit_meta: Any = None
        if addr_tuple is not None:
            address_key = self._addr_key(addr_tuple[0], addr_tuple[1], addr_tuple[2])
            fam = self._store.get_family(addr_tuple[0], addr_tuple[2])
            if fam is not None:
                raw_unit_code = fam.unit_code
            if mapping is not None and mapping.units is not None:
                if raw_unit_code is None and isinstance(mapping.units, (str, int, float)):
                    raw_unit_code = mapping.units
                if isinstance(mapping.units, Mapping):
                    mapping_unit_meta = dict(mapping.units)

        unit_meta = await self._resolve_unit_meta(raw_unit_code=raw_unit_code)
        if unit_meta is None and isinstance(mapping_unit_meta, Mapping):
            unit_meta = dict(mapping_unit_meta)

        unit = await self._unit_display_value(unit_meta)
        unit_value_labels = self._unit_options_map(unit_meta)

        if mapping is not None and self._mapping_has_computed_rules(mapping):
            computed_value = self._evaluator.evaluate(mapping.raw)
            if computed_value is None and isinstance(mapping.paths, Mapping) and mapping.paths:
                computed_value = self._evaluator.evaluate({"paths": mapping.paths})

            if computed_value is None and addr_tuple is not None and self._mapping_has_simple_direct_value_path(mapping):
                raw_val = None
                fam = self._store.get_family(addr_tuple[0], addr_tuple[2])
                if fam is not None:
                    raw_val = fam.get(addr_tuple[1])
                display_val = self._apply_numeric_transform(
                    raw_val, unit_meta.get("value") if isinstance(unit_meta, Mapping) else None
                )
                if isinstance(display_val, str):
                    resolved_display = await self._resolve_units_value_token(display_val)
                    if isinstance(resolved_display, str):
                        display_val = resolved_display
                return ResolvedValue(
                    symbol=symbol,
                    kind="direct",
                    address=address_key,
                    value=display_val,
                    value_label=await self._resolve_units_value_token(
                        self._unit_mapping_value_label(unit_value_labels, display_val)
                    ),
                    unit=unit,
                )

            computed_value_label = await self._resolve_units_value_token(
                self._unit_mapping_value_label(unit_value_labels, computed_value)
            )

            computed_address = address_key if self._mapping_has_simple_direct_value_path(mapping) else None

            return ResolvedValue(
                symbol=symbol,
                kind="computed",
                address=computed_address,
                value=computed_value,
                value_label=computed_value_label,
                unit=unit,
            )

        if mapping is not None:
            composed = self.compose_mapping_register_value(self._store, mapping)
            if composed is not None:
                display_val = self._apply_numeric_transform(
                    composed, unit_meta.get("value") if isinstance(unit_meta, Mapping) else None
                )
                if isinstance(display_val, str):
                    resolved_display = await self._resolve_units_value_token(display_val)
                    if isinstance(resolved_display, str):
                        display_val = resolved_display
                return ResolvedValue(
                    symbol=symbol,
                    kind="direct",
                    address=address_key,
                    value=display_val,
                    value_label=await self._resolve_units_value_token(
                        self._unit_mapping_value_label(unit_value_labels, display_val)
                    ),
                    unit=unit,
                )

        val = None
        if addr_tuple is not None:
            fam = self._store.get_family(addr_tuple[0], addr_tuple[2])
            if fam is not None:
                val = fam.get(addr_tuple[1])

        display_val = self._apply_numeric_transform(val, unit_meta.get("value") if isinstance(unit_meta, Mapping) else None)
        if isinstance(display_val, str):
            resolved_display = await self._resolve_units_value_token(display_val)
            if isinstance(resolved_display, str):
                display_val = resolved_display

        return ResolvedValue(
            symbol=symbol,
            kind="direct",
            address=address_key,
            value=display_val,
            value_label=await self._resolve_units_value_token(self._unit_mapping_value_label(unit_value_labels, display_val)),
            unit=unit,
        )

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
            label = await self._resolve_i18n_token(mapping_name_key)

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
                raw_unit_code_for_labels: Any = unit_code
                if raw_unit_code_for_labels is None and isinstance(mapping.units, (str, int, float)):
                    raw_unit_code_for_labels = mapping.units

                unit_meta_for_labels = await self._resolve_unit_meta(raw_unit_code=raw_unit_code_for_labels)
                unit_value_labels = self._unit_options_map(unit_meta_for_labels)
                computed_value_label = await self._resolve_units_value_token(
                    self._unit_mapping_value_label(unit_value_labels, computed_value)
                )

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

    async def describe_symbols(self, symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Describe multiple symbols with shared bulk-prefetched mapping cache.

        Args:
            symbols: Iterable of symbolic names.

        Returns:
            Mapping from symbol to the same payload returned by :meth:`describe_symbol`.
        """
        uniq_symbols = list(dict.fromkeys(str(sym) for sym in symbols if sym))
        await self.prefetch_param_mappings(uniq_symbols)

        out: dict[str, dict[str, Any]] = {}
        for sym in uniq_symbols:
            out[sym] = await self.describe_symbol(sym)
        return out

    async def merge_assets_with_permissions(self, permissions: list[str], device_menu: int = 0) -> dict[str, dict[str, Any]]:
        """Merge menu-visible symbols with mappings and live values for a permission set."""
        symbols = await self._assets.list_symbols_for_permissions(device_menu, permissions)
        return await self.describe_symbols(sorted(symbols))
