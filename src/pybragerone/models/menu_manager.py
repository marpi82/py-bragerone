"""Refactored menu system with clear separation of concerns.

New design:
1. MenuParser - parses raw JS and stores raw menu data
2. MenuProcessor - applies filtering, validation, i18n etc.
3. ProcessedMenu - final clean result with all transformations applied
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .menu import MenuParameter, MenuResult


@dataclass
class RawMenuData:
    """Raw menu data parsed from JavaScript asset."""

    routes: list[dict[str, Any]] = field(default_factory=list)
    asset_url: str | None = None
    device_menu: int | None = None
    parsed_at: float = field(default_factory=lambda: __import__("time").time())

    def route_count(self) -> int:
        """Count total routes including nested."""

        def count_recursive(routes: list[dict[str, Any]]) -> int:
            count = len(routes)
            for route in routes:
                children = route.get("children", [])
                count += count_recursive(children)
            return count

        return count_recursive(self.routes)


class MenuProcessor:
    """Processes raw menu data with various filters and transformations."""

    def __init__(self, raw_menu: RawMenuData, logger: logging.Logger | None = None) -> None:
        """Initialise processor with raw menu data and optional logger."""
        self.raw_menu = raw_menu
        self.logger = logger or logging.getLogger(__name__)

    def get_clean_menu(
        self,
        *,
        filter_permissions: set[str] | None = None,
        include_invisible: bool = False,
        apply_i18n: bool = True,
        resolve_tokens: bool = True,
    ) -> MenuResult:
        """Get processed menu with specified transformations.

        Args:
            filter_permissions: Set of user permissions to filter by. If None, no filtering.
            include_invisible: If True, keeps routes that user can't access (for debug)
            apply_i18n: If True, applies internationalization transformations
            resolve_tokens: If True, resolves parameter tokens to clean format

        Returns:
            Processed MenuResult with clean Pydantic models
        """
        working_routes = self._deep_copy_routes(self.raw_menu.routes)

        # Step 1: Apply permission filtering if requested
        if filter_permissions is not None:
            working_routes = self._apply_permission_filter(working_routes, filter_permissions, include_invisible)

        # Step 2: Apply i18n transformations if requested
        if apply_i18n:
            working_routes = self._apply_i18n(working_routes)

        # Step 3: Resolve tokens if requested
        if resolve_tokens:
            working_routes = self._resolve_tokens(working_routes)

        # Step 4: Convert to clean Pydantic models with validation
        clean_menu = MenuResult.model_validate({"routes": working_routes, "asset_url": self.raw_menu.asset_url})

        self.logger.info(
            "Processed menu: %d routes, %d tokens, permissions_filtered=%s",
            clean_menu.route_count(),
            clean_menu.token_count(),
            filter_permissions is not None,
        )

        return clean_menu

    def get_debug_info(self) -> dict[str, Any]:
        """Get debug information about the menu."""
        return {
            "raw_routes_count": self.raw_menu.route_count(),
            "asset_url": self.raw_menu.asset_url,
            "device_menu": self.raw_menu.device_menu,
            "parsed_at": self.raw_menu.parsed_at,
            "sample_route": self.raw_menu.routes[0] if self.raw_menu.routes else None,
            "route_names": [route.get("name", "unnamed") for route in self.raw_menu.routes],
        }

    def _deep_copy_routes(self, routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Create deep copy of routes for safe processing."""
        import copy

        return copy.deepcopy(routes)

    def _apply_permission_filter(
        self,
        routes: list[dict[str, Any]],
        permissions: set[str],
        include_invisible: bool,
    ) -> list[dict[str, Any]]:
        """Filter routes respecting the provided permission set."""
        detected_prefixes = self._detect_permission_prefixes(routes)
        self.logger.debug("Detected permission prefixes: %s", detected_prefixes)

        def normalize_permission(raw: str | None) -> str:
            if not raw:
                return ""
            for prefix in detected_prefixes:
                if raw.startswith(prefix):
                    return raw[len(prefix) :]
            return raw

        def has_permission(required: str | None) -> bool:
            if not required:
                return True
            normalized = normalize_permission(required)
            return normalized in permissions

        def gate(node: dict[str, Any]) -> dict[str, Any]:
            meta = node.get("meta") or {}
            visible = has_permission(meta.get("permissionModule"))

            def filter_parameters(container: dict[str, Any]) -> None:
                for section in ("read", "write", "status", "special"):
                    original = container.get(section) or []
                    filtered: list[dict[str, Any] | str] = []
                    for item in original:
                        if isinstance(item, dict):
                            allowed = has_permission(item.get("permissionModule"))
                            if allowed or include_invisible:
                                filtered.append(dict(item))
                        else:
                            filtered.append(item)
                    container[section] = filtered

            params = node.get("parameters")
            if isinstance(params, dict):
                filter_parameters(params)
                node["parameters"] = params

            meta_params = meta.get("parameters")
            if isinstance(meta_params, dict):
                filter_parameters(meta_params)
                meta["parameters"] = meta_params
            node["meta"] = meta

            children = node.get("children") or []
            node["children"] = [gate(child) for child in children if isinstance(child, dict)]

            node["_visible"] = visible
            return node

        def strip_invisible(processed: list[dict[str, Any]]) -> list[dict[str, Any]]:
            result: list[dict[str, Any]] = []
            for route in processed:
                if not isinstance(route, dict):
                    continue
                if not include_invisible and not route.get("_visible", False):
                    continue
                clean = dict(route)
                clean.pop("_visible", None)
                if isinstance(clean.get("children"), list):
                    clean["children"] = strip_invisible(clean["children"])
                result.append(clean)
            return result

        gated = [gate(route) for route in routes if isinstance(route, dict)]
        return strip_invisible(gated)

    def _apply_i18n(self, routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Perform minimal i18n cleanup such as trimming display names."""

        def apply(node: dict[str, Any]) -> None:
            meta = node.get("meta")
            if isinstance(meta, dict) and isinstance(meta.get("displayName"), str):
                meta["displayName"] = meta["displayName"].strip()
            children = node.get("children")
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        apply(child)

        for route in routes:
            if isinstance(route, dict):
                apply(route)
        return routes

    def _resolve_tokens(self, routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize parameter entries to guarantee clean tokens before validation."""

        def normalize_list(items: list[Any]) -> list[Any]:
            normalized: list[Any] = []
            for item in items:
                if isinstance(item, dict):
                    try:
                        model = MenuParameter.model_validate(item)
                        normalized.append(model.model_dump(mode="json", by_alias=True))
                    except ValidationError:
                        normalized.append(dict(item))
                else:
                    normalized.append(item)
            return normalized

        def process(node: dict[str, Any]) -> dict[str, Any]:
            params = node.get("parameters")
            if isinstance(params, dict):
                for section in ("read", "write", "status", "special"):
                    params[section] = normalize_list(params.get(section, []) or [])
                node["parameters"] = params

            meta = node.get("meta")
            if isinstance(meta, dict):
                meta_params = meta.get("parameters")
                if isinstance(meta_params, dict):
                    for section in ("read", "write", "status", "special"):
                        meta_params[section] = normalize_list(meta_params.get(section, []) or [])
                    meta["parameters"] = meta_params
                node["meta"] = meta

            children = node.get("children")
            if isinstance(children, list):
                node["children"] = [process(child) for child in children if isinstance(child, dict)]
            return node

        return [process(route) for route in routes if isinstance(route, dict)]

    def _detect_permission_prefixes(self, routes: list[dict[str, Any]]) -> list[str]:
        """Auto-detect permission prefixes used in the menu."""
        prefixes = set()

        def scan_route(route: dict[str, Any]) -> None:
            meta = route.get("meta", {})

            # Check route permission
            perm = meta.get("permissionModule", "")
            if perm:
                for prefix in ["A.", "e.", "E."]:
                    if perm.startswith(prefix):
                        prefixes.add(prefix)
                        break

            # Check parameter permissions
            params = meta.get("parameters", {})
            for section in ("read", "write", "status", "special"):
                items = params.get(section, [])
                for item in items:
                    if isinstance(item, dict):
                        item_perm = item.get("permissionModule", "")
                        if item_perm:
                            for prefix in ["A.", "e.", "E."]:
                                if item_perm.startswith(prefix):
                                    prefixes.add(prefix)
                                    break

            # Scan children
            for child in route.get("children", []):
                scan_route(child)

        for route in routes:
            scan_route(route)

        # Return in consistent order
        return sorted(prefixes)


class MenuManager:
    """High-level menu management with caching and convenience methods."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Create a manager with optional externally provided logger."""
        self.logger = logger or logging.getLogger(__name__)
        self._raw_cache: dict[int, RawMenuData] = {}
        self._processor_cache: dict[int, MenuProcessor] = {}

    def store_raw_menu(self, device_menu: int, routes: list[dict[str, Any]], asset_url: str | None = None) -> None:
        """Store raw menu data for later processing."""
        raw_menu = RawMenuData(routes=routes, asset_url=asset_url, device_menu=device_menu)
        self._raw_cache[device_menu] = raw_menu

        # Create processor
        processor = MenuProcessor(raw_menu, self.logger)
        self._processor_cache[device_menu] = processor

        self.logger.info("Stored raw menu for device_menu=%d with %d routes", device_menu, raw_menu.route_count())

    def get_menu(self, device_menu: int, *, permissions: set[str] | None = None, debug_mode: bool = False) -> MenuResult:
        """Get processed menu for device_menu.

        Args:
            device_menu: Device menu ID
            permissions: User permissions for filtering (None = no filtering)
            debug_mode: If True, includes invisible routes for debugging

        Returns:
            Processed MenuResult
        """
        if device_menu not in self._processor_cache:
            raise ValueError(f"No menu data stored for device_menu={device_menu}")

        processor = self._processor_cache[device_menu]

        perm_set = permissions if permissions is None else set(permissions)

        return processor.get_clean_menu(
            filter_permissions=perm_set, include_invisible=debug_mode, apply_i18n=True, resolve_tokens=True
        )

    def get_raw_menu(self, device_menu: int) -> RawMenuData:
        """Get raw menu data for debugging."""
        if device_menu not in self._raw_cache:
            raise ValueError(f"No raw menu data for device_menu={device_menu}")

        return self._raw_cache[device_menu]

    def get_debug_info(self, device_menu: int) -> dict[str, Any]:
        """Get debug information for device_menu."""
        if device_menu not in self._processor_cache:
            raise ValueError(f"No menu data for device_menu={device_menu}")

        processor = self._processor_cache[device_menu]
        return processor.get_debug_info()

    def list_cached_menus(self) -> list[int]:
        """List all cached device_menu IDs."""
        return list(self._raw_cache.keys())

    def clear_cache(self) -> None:
        """Clear all cached menu data."""
        self._raw_cache.clear()
        self._processor_cache.clear()
        self.logger.info("Cleared menu cache")
