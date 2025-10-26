"""Implementation of live asset catalog parsing from BragerOne web app.

This module provides classes and utilities for parsing and managing live assets
from the BragerOne web application, including:

- LiveAssetsCatalog: Main entry point for fetching and parsing assets
- AssetRef, AssetIndex: Data structures for tracking asset references
- ParamMap: Data structures for menu routes and parameter mappings
- TranslationConfig: Configuration for available translations
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import tree_sitter_javascript
from tree_sitter import Language, Node, Parser, Tree

from .menu import MenuResult
from .menu_manager import MenuManager, RawMenuData

if TYPE_CHECKING:
    from ..api import BragerOneApiClient

JS_LANGUAGE = Language(tree_sitter_javascript.language())
LOG = logging.getLogger(__name__)


# ----------------------------- Data types -----------------------------


@dataclass(slots=True)
class AssetRef:
    """Reference to a versioned asset from the BragerOne catalog.

    Attributes:
        url: The full URL to the asset file.
        base: The base name without hash (e.g., 'module.menu' from 'module.menu-BNvCCsxi').
        hash: The hash identifier for this version (e.g., 'BNvCCsxi').
        etag: Optional ETag from HTTP headers for cache validation.
        last_modified: Optional last modified timestamp from HTTP headers.
    """

    url: str
    base: str  # BASENAME (np. 'module.menu-BNvCCsxi' → base='module.menu')
    hash: str  # 'BNvCCsxi'
    etag: str | None = None
    last_modified: str | None = None


@dataclass(slots=True)
class AssetIndex:
    """Index of assets parsed from ``index-*.js`` file.

    Attributes:
        assets_by_basename: Full list of assets declared in ``index-*.js`` (exact basenames, no normalization).
            Maps basename strings to lists of AssetRef objects.
        menu_map: Mapping from deviceMenu integers to BASENAME strings (e.g., ``module.menu-<hash>.js``).
        inline_param_candidates: List of (start_byte, end_byte) tuples indicating potential
            inline parameter maps detected within ``index-*.js``.
        index_bytes: Raw bytes of the index file for potential inline parsing.
    """

    # full list of assets declared in index-*.js (exact basenames, no normalization)
    assets_by_basename: dict[str, list[AssetRef]] = field(default_factory=dict)
    # mapping from deviceMenu:int -> BASENAME('module.menu-<hash>.js')
    menu_map: dict[int, str] = field(default_factory=dict)
    # inline parameter maps detected within index-*.js
    inline_param_candidates: list[tuple[int, int]] = field(default_factory=list)  # (start_byte, end_byte)
    # raw index for potential inline parsing
    index_bytes: bytes = b""

    def find_asset_for_basename(self, basename: str) -> AssetRef | None:
        """Find an asset reference by its basename.

        Args:
            basename: The basename of the asset to search for.

        Returns:
            The last asset reference found for the given basename, or None if no
            asset is found. When multiple assets share the same basename, returns
            the last one (typically the newest hash).

        Note:
            Uses an alpha heuristic that assumes the last asset in the list is
            the most recent version when multiple assets share the same basename.
        """
        lst = self.assets_by_basename.get(basename)
        if not lst:
            return None
        # Alpha heuristic: take the last found (usually the newest hash)
        return lst[-1]

    def find_asset_for_full_name(self, full_name: str) -> AssetRef | None:
        """Find an asset reference by its full name with hash (e.g., 'module.menu-Dbo_n32n').

        Args:
            full_name: The full name of the asset with hash to search for.

        Returns:
            The asset reference if found, or None if not found.
        """
        # Search through all assets by basename to find the one with matching full name
        for basename_assets in self.assets_by_basename.values():
            for asset in basename_assets:
                if f"{asset.base}-{asset.hash}" == full_name:
                    return asset
        return None


@dataclass(slots=True)
class ParamMap:
    """Represents a parameter mapping in the BragerOne system.

    This class encapsulates the mapping between parameter identifiers and their
    metadata, including paths, units, limits, and status flags. It serves as a
    structured representation of parameter configurations retrieved from the router.

    Attributes:
        key: The unique parameter identifier token from the router.
            Examples: "URUCHOMIENIE_KOTLA", "PARAM_66".
        group: Optional parameter group identifier. Example: "P6".
        paths: Dictionary mapping path types to their respective path lists.
            Entries are normalized lists of dictionaries describing pool/index/use
            metadata for value/unit/status/command/min/max channels.
        component_type: Optional type of the UI component associated with this parameter.
        units: Optional measurement unit identifier. May be a localized string, numeric
            code, or mapping used for enumerations; resolution happens via the units
            i18n catalog where possible.
        limits: Optional dictionary containing parameter limit definitions and constraints.
        status_flags: List of dictionaries defining various status flags and their meanings.
        origin: Source of the parameter map definition.
            Format: "asset:<url>" for external sources or "inline:index" for inline definitions.
        raw: The raw, unprocessed parameter map dictionary. Preserved for future use
            in internationalization (i18n) and logging purposes.

    Example:
        >>> param_map = ParamMap()
        >>> param_map.key = "PARAM_66"
        >>> param_map.group = "P6"
        >>> param_map.paths = {"v": ["status", "value"], "u": ["status", "unit"]}
    """

    key: str  # token from router: np. "URUCHOMIENIE_KOTLA" lub "PARAM_66"
    group: str | None  # np. "P6"
    paths: dict[str, list[dict[str, Any]]]  # value/unit/status/command/min/max channel descriptors
    component_type: str | None
    units: str | int | float | dict[str, Any] | list[Any] | None
    limits: dict[str, Any] | None
    status_flags: list[dict[str, Any]]
    status_conditions: dict[str, list[dict[str, Any]]] | None
    command_rules: list[dict[str, Any]]
    origin: str  # "asset:<url>" or "inline:index"
    raw: dict[str, Any]  # raw map (will be useful later for i18n/logging)


# ----------------------------- Parser helpers -----------------------------


class _TS:
    """Lightweight wrapper around tree-sitter Parser for JavaScript/TypeScript.

    This class provides a simplified interface to the tree-sitter parser
    specifically configured for JavaScript language parsing.

    Attributes:
        parser: The underlying tree-sitter Parser instance.
    """

    __slots__ = ("parser",)

    def __init__(self) -> None:
        """Initialize the parser with JavaScript language support.

        Sets up a tree-sitter Parser instance configured to parse JavaScript
        and TypeScript code using the tree-sitter-javascript grammar.
        """
        self.parser = Parser()
        self.parser.language = JS_LANGUAGE

    def parse(self, code: bytes) -> Tree:
        """Parse JavaScript code into an Abstract Syntax Tree (AST).

        Args:
            code: The JavaScript source code as bytes to parse.

        Returns:
            A tree-sitter Tree object representing the parsed AST.

        Example:
            >>> parser = _TS()
            >>> tree = parser.parse(b'const x = 42;')
            >>> print(tree.root_node.type)
            program
        """
        return self.parser.parse(code)


def _node_text(code: bytes, n: Node) -> str:
    """Extract text content from a tree-sitter Node.

    Args:
        code: The source code bytes the node comes from.
        n: The tree-sitter Node to extract text from.

    Returns:
        The decoded text content of the node.
    """
    return code[n.start_byte : n.end_byte].decode("utf-8", errors="replace")


def _is_string(n: Node) -> bool:
    """Check if a Node represents a string literal.

    Args:
        n: The tree-sitter Node to check.

    Returns:
        True if the node is a string or template_string type.
    """
    return n.type in {"string", "template_string"}


def _string_value(text: str) -> str:
    """Extract the value from a string literal, removing quotes.

    Args:
        text: The raw string text including quotes.

    Returns:
        The string value with surrounding quotes removed.
    """
    if len(text) >= 2 and text[0] in "\"'`" and text[-1] == text[0]:
        return text[1:-1]
    return text


def _walk(node: Node) -> Iterable[Node]:
    """Depth-first traversal of tree-sitter Node tree.

    Args:
        node: The root node to start traversal from.

    Yields:
        Each node in the tree in depth-first order.
    """
    stack = [node]
    while stack:
        cur = stack.pop()
        yield cur
        for i in range(cur.child_count - 1, -1, -1):
            child = cur.child(i)
            if child is not None:
                stack.append(child)


def _find_export_root(code: bytes, root: Node) -> Node | None:
    """Find the root export object or array in a JavaScript AST.

    This function implements a two-step strategy:
    1. Look for explicit export statements containing object/array literals
    2. Fall back to finding the largest object/array in the tree

    Args:
        code: The source code bytes (currently unused but kept for consistency).
        root: The root node of the AST to search.

    Returns:
        The Node representing the main export object/array, or None if not found.
    """
    # 1) export default <expr>
    for n in _walk(root):
        if n.type == "export_statement":
            # looking for object/array literal in export
            for ch in n.named_children:
                if ch.type in {"object", "array"}:
                    return ch
    # 2) fallback: largest object/array
    best = None
    best_sz = -1
    for n in _walk(root):
        if n.type in {"object", "array"}:
            sz = n.end_byte - n.start_byte
            if sz > best_sz:
                best, best_sz = n, sz
    return best


def _node_to_python(code: bytes, node: Node, bindings: dict[str, Any] | None = None) -> Any:
    """Convert an arbitrary AST node to a Python object.

    When *bindings* is provided, identifier nodes are resolved using the
    already-converted values stored in the mapping. This allows handling of the
    common pattern where large dictionaries reuse previously declared constants
    (e.g. i18n bundles exporting `const foo = "label"; const map = {key: foo};`).
    """
    t = node.type

    if t == "object":
        obj: dict[str, Any] = {}
        for prop in node.named_children:
            if prop.type != "pair":
                continue
            key_node = prop.child_by_field_name("key")
            value_node = prop.child_by_field_name("value")
            if key_node is None or value_node is None:
                continue

            key = _string_value(_node_text(code, key_node)) if _is_string(key_node) else _node_text(code, key_node)
            obj[key] = _node_to_python(code, value_node, bindings)
        return obj

    if t == "array":
        return [_node_to_python(code, child, bindings) for child in node.named_children]

    if _is_string(node):
        return _string_value(_node_text(code, node))

    if t == "number":
        text = _node_text(code, node)
        try:
            return float(text) if any(c in text for c in ".eE") else int(text)
        except Exception:
            return text

    if t in {"true", "false"}:
        return t == "true"

    if t == "null":
        return None

    if t in {"identifier", "property_identifier"}:
        name = _node_text(code, node)
        if bindings and name in bindings:
            return bindings[name]
        return name

    return _node_text(code, node)


def _object_to_python(code: bytes, node: Node, *, bindings: dict[str, Any] | None = None) -> Any:
    """Backward-compatible wrapper around :func:`_node_to_python` for objects."""
    result = _node_to_python(code, node, bindings)
    return result if isinstance(result, dict) else {}


def _collect_bindings(code: bytes, root: Node) -> dict[str, Any]:
    """Collect simple top-level bindings to resolve identifiers during conversion."""
    bindings: dict[str, Any] = {}

    for statement in root.named_children:
        if statement.type not in {"lexical_declaration", "variable_declaration"}:
            continue

        for declarator in statement.named_children:
            if declarator.type != "variable_declarator":
                continue

            name_node = declarator.child_by_field_name("name")
            value_node = declarator.child_by_field_name("value")

            if name_node is None or value_node is None:
                continue

            if name_node.type not in {"identifier", "property_identifier"}:
                continue

            name = _node_text(code, name_node)
            if not name:
                continue

            try:
                value = _node_to_python(code, value_node, bindings)
            except Exception as exc:  # pragma: no cover - defensive parsing fallback
                LOG.debug("Failed to resolve binding '%s': %s", name, exc)
            else:
                bindings[name] = value

    return bindings


# ----------------------------- TranslationConfig -----------------------------


@dataclass
class TranslationConfig:
    """Configuration of available translations."""

    translations: list[dict[str, Any]]
    default_translation: str


# ----------------------------- LiveAssetsCatalog -----------------------------


class LiveAssetsCatalog:
    """Main entry point: fetches index-<hash>.js, parses router (module.menu-<hash>.js).

    Only loads necessary parameter map files (based on router tokens).
    """

    def __init__(
        self,
        api: BragerOneApiClient,
        logger: logging.Logger | None = None,
        visibility_strategy: str = "independent",  # "independent" | "parent_gates_children" (for future use)
        schemas_enabled: bool = False,  # hook (OFF)
        request_timeout: float = 8.0,
        concurrency: int = 8,
    ) -> None:
        """Initialize the LiveAssetsCatalog.

        Args:
            api: BragerOneApiClient used to fetch assets and index files.
            logger: Optional logger to use for informational and debug output.
            visibility_strategy: Strategy for gating menu visibility (default 'independent').
            schemas_enabled: Whether schema validation is enabled (currently unused).
            request_timeout: Timeout for network requests in seconds.
            concurrency: Maximum concurrent network operations (reserved for future use).
        """
        self._api = api
        self._timeout = request_timeout
        self._ts = _TS()
        self._idx = AssetIndex()
        self._log = logger or logging.getLogger(__name__)
        self._last_index_url: str | None = None

        # New menu management system
        self._menu_manager = MenuManager(self._log)

        # Track auto-discovery attempts to help guard repeated network fetches
        self._index_autoload_attempts = 0

    def _smart_urljoin(self, base_url: str, relative_url: str) -> str:
        """Smart urljoin that handles assets prefix correctly to avoid double /assets/ paths.

        Args:
            base_url: Base URL (usually an index file like /assets/index-hash.js)
            relative_url: Relative URL, may start with assets/

        Returns:
            Properly joined URL without duplicate /assets/ segments
        """
        from urllib.parse import urljoin

        # If relative_url starts with assets/ and base_url contains /assets/,
        # remove the assets/ prefix from relative_url to avoid duplication
        if relative_url.startswith("assets/") and "/assets/" in base_url:
            # Remove assets/ prefix
            relative_url = relative_url[7:]  # len('assets/') = 7

        return urljoin(base_url, relative_url)

    # ---------- lifecycle ----------

    async def __aenter__(self) -> LiveAssetsCatalog:
        """Enter the async context manager and return self."""
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Exit the async context manager."""
        pass

    # ---------- INDEX ----------

    async def refresh_index(self, index_url: str) -> None:
        """Fetches index-<hash>.js and builds full asset index.

        - assets_by_basename (exact BASENAME → [AssetRef])
        - menu_map: int -> BASENAME(module.menu-<hash>.js), if present in index
        - inline_param_candidates: list of (start,end) large objects in index that look like param-maps
        """
        code = await self._api.get_bytes(index_url)
        self._last_index_url = index_url  # Store for i18n URL construction
        self._idx = self._build_asset_index_from_index_js(index_url, code)
        self._log.info(
            "INDEX: assets=%d basenames=%d menus=%d inline_param_candidates=%d",
            sum(len(v) for v in self._idx.assets_by_basename.values()),
            len(self._idx.assets_by_basename),
            len(self._idx.menu_map),
            len(self._idx.inline_param_candidates),
        )

    async def _auto_discover_and_load_index(self) -> None:
        """Auto-discover and load the index file."""
        import re

        import httpx

        self._log.info("Auto-discovering index file...")

        try:
            # Try to discover index URL from assets page
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://one.brager.pl/assets/")
                resp.raise_for_status()
                assets_html = resp.text

            # Look for patterns like /assets/index-XXXXXXXX.js
            m = re.search(r"/assets/(index-[A-Za-z0-9_-]+\.js)", assets_html)

            if m:
                index_filename = m.group(1)
                discovered_url = f"https://one.brager.pl/assets/{index_filename}"
                self._log.info("Discovered index: %s", discovered_url)
                await self.refresh_index(discovered_url)
                return

            # Try alternative URLs if discovery failed
            alt_urls = ["https://one.brager.pl/assets/index-main.js", "https://one.brager.pl/assets/index.js"]

            for alt_url in alt_urls:
                try:
                    self._log.debug("Trying alternative: %s", alt_url)
                    await self.refresh_index(alt_url)
                    self._log.info("Success with alternative: %s", alt_url)
                    return
                except Exception as e:
                    self._log.debug("Alternative failed: %s - %s", alt_url, e)

            # If all fails, log warning
            self._log.warning("Failed to auto-discover index file")

        except Exception as e:
            self._log.warning("Error auto-discovering index: %s", e)

    async def _ensure_index_loaded(self) -> None:
        """Best-effort ensure that the asset index is available."""
        if self._idx.index_bytes or self._idx.assets_by_basename:
            return

        attempt = self._index_autoload_attempts + 1
        self._index_autoload_attempts = attempt
        self._log.debug("Index not loaded yet. Auto-discovery attempt %d", attempt)

        try:
            await self._auto_discover_and_load_index()
        except Exception as e:  # pragma: no cover - should not happen but guard just in case
            self._log.warning("Auto-discovery attempt %d failed: %s", attempt, e)

    def _build_asset_index_from_index_js(self, index_url: str, code: bytes) -> AssetIndex:
        text = code.decode("utf-8", errors="replace")

        # Performance optimization: limit regex search to first part of file for most assets
        # Most index files have assets declared early, but we keep a fallback for full file
        search_text = text[:50000] if len(text) > 50000 else text

        # 1) Collect all '*-<hash>.js' paths from literals - SIMPLIFIED FOR PERFORMANCE
        # Much simpler regex that should be faster
        assets_by_basename: dict[str, list[AssetRef]] = {}

        # Parameters and i18n assets frequently live deeper in the bundle, so we scan both the
        # leading slice and the remaining part. We also normalise basenames to strip path prefixes.
        simple_pattern = re.compile(r"([A-Za-z0-9._/-]+?)-([A-Za-z0-9_-]+)\.js")

        def _register(matches: Iterable[re.Match[str]]) -> None:
            for m in matches:
                raw_base = m.group(1)
                h = m.group(2)
                # Normalise '../parameters/write/FOO' → 'FOO'
                norm_base = raw_base.rsplit("/", 1)[-1]
                full_url = self._smart_urljoin(index_url, f"{raw_base}-{h}.js")
                bucket = assets_by_basename.setdefault(norm_base, [])
                if all(existing.hash != h or existing.url != full_url for existing in bucket):
                    bucket.append(AssetRef(url=full_url, base=norm_base, hash=h))

        _register(simple_pattern.finditer(search_text))

        if len(text) > len(search_text):
            self._log.debug("Scanning remaining index fragment for additional assets...")
            _register(simple_pattern.finditer(text[len(search_text) :]))

        # 2) Try to find mapping from deviceMenu:int -> 'module.menu-<hash>.js' in index (Regex fallback)
        # Use regex pattern matching since AST parsing fails on complex minified code in Object.assign
        menu_map: dict[int, str] = {}

        try:
            # Look for deviceMenu patterns in Object.assign calls
            # Pattern: "../../config/router/deviceMenu/N/module.menu.ts":()=>d(()=>import("./module.menu-HASH.js")
            device_menu_pattern = (
                r'"\.\.\/\.\.\/config\/router\/deviceMenu\/(\d+)\/module\.menu\.ts":\(\)\=\>d'
                r'\(\(\)\=\>import\("\./(module\.menu-[A-Za-z0-9_]+)\.js"\)'
            )

            # Ensure code is a string for regex
            if isinstance(code, bytes):
                code_str = code.decode("utf-8")
            elif isinstance(code, (bytearray, memoryview)):
                code_str = bytes(code).decode("utf-8")
            else:
                code_str = str(code)

            for match in re.finditer(device_menu_pattern, code_str):
                device_menu_num = int(match.group(1))
                menu_file_name = match.group(2)
                menu_map[device_menu_num] = menu_file_name
                self._log.debug("Found deviceMenu mapping: %d -> %s", device_menu_num, menu_file_name)

        except Exception as regex_e:
            self._log.debug("Regex deviceMenu parsing failed: %s", regex_e)

        # Prepare limited code for AST parsing (needed for inline param candidates)
        ast_limit = min(1000000, len(code))
        limited_code = code[:ast_limit]

        # 3) Inline param-map candidates (AST on limited data)
        inline_candidates: list[tuple[int, int]] = []

        if len(limited_code) > 0:
            try:
                # Reuse tree if available, or parse again for param candidates
                if "tree" not in locals():
                    tree = self._ts.parse(limited_code)

                objects_checked = 0
                max_param_objects = 10  # More objects for param search

                for n in _walk(tree.root_node):
                    if n.type == "object" and objects_checked < max_param_objects:
                        objects_checked += 1

                        approx_len = n.end_byte - n.start_byte
                        if approx_len > 200:  # heuristic: larger objects are more likely to be maps
                            # quick "shape" of param-map: look for keywords inside
                            obj_start = n.start_byte
                            obj_end = min(n.end_byte, len(limited_code))
                            snippet = limited_code[obj_start:obj_end]
                            if any(
                                key in snippet
                                for key in (b"group", b"pool", b"use", b"value", b"unit", b"status", b"componentType")
                            ):
                                inline_candidates.append((obj_start, obj_end))

            except Exception as param_e:
                self._log.debug("Param candidates AST parsing failed: %s", param_e)

        return AssetIndex(
            assets_by_basename=assets_by_basename,
            menu_map=menu_map,
            inline_param_candidates=inline_candidates,
            index_bytes=code,
        )

    # ---------- MENU ----------

    async def get_module_menu(
        self,
        device_menu: int,
        permissions: Iterable[str] | None = None,
        *,
        debug_mode: bool = False,
    ) -> MenuResult:
        """Get processed menu using the unified MenuManager pipeline."""
        if device_menu not in self._menu_manager.list_cached_menus():
            await self._load_and_cache_menu(device_menu)

        perm_set = None if permissions is None else set(permissions)
        return self._menu_manager.get_menu(device_menu=device_menu, permissions=perm_set, debug_mode=debug_mode)

    async def _load_and_cache_menu(self, device_menu: int) -> None:
        """Load raw menu data and cache it in MenuManager."""
        # Auto-load index if not loaded yet
        if not self._idx.menu_map and not self._idx.assets_by_basename:
            await self._auto_discover_and_load_index()

        # Find asset for device_menu
        menu_name = self._idx.menu_map.get(device_menu)
        if not menu_name:
            self._log.warning("No menu mapping found for device_menu=%d", device_menu)
            # Cache empty menu
            self._menu_manager.store_raw_menu(device_menu, [], None)
            return

        # Get asset reference
        asset = self._idx.find_asset_for_full_name(menu_name)
        if not asset:
            asset = self._idx.find_asset_for_basename("module.menu")

        if not asset:
            self._log.warning("No menu asset found for device_menu=%d", device_menu)
            self._menu_manager.store_raw_menu(device_menu, [], None)
            return

        # Fetch and parse menu
        self._log.info("Loading menu asset: %s", asset.url)
        code = await self._api.get_bytes(asset.url)

        # Parse raw routes (no filtering, no processing)
        raw_routes = self._parse_menu_routes(code)

        # Store in cache
        self._menu_manager.store_raw_menu(device_menu=device_menu, routes=raw_routes, asset_url=asset.url)

        self._log.info("Cached raw menu for device_menu=%d: %d routes", device_menu, len(raw_routes))

    def get_raw_menu(self, device_menu: int) -> RawMenuData:
        """Get raw unprocessed menu data for debugging."""
        return self._menu_manager.get_raw_menu(device_menu)

    def get_menu_debug_info(self, device_menu: int) -> dict[str, Any]:
        """Get debug information about cached menu."""
        return self._menu_manager.get_debug_info(device_menu)

    def _parse_menu_routes(self, code: bytes) -> list[dict[str, Any]]:
        """Returning list of root-routes (1:1 with export in module.menu-*.js)."""
        tree = self._ts.parse(code)
        bindings = _collect_bindings(code, tree.root_node)
        root = _find_export_root(code, tree.root_node)
        if root is None:
            return []
        export_obj = _node_to_python(code, root, bindings)

        def extract_routes(value: Any, depth: int = 0) -> list[dict[str, Any]]:
            if depth > 5:
                return []

            if isinstance(value, list):
                candidates = [item for item in value if isinstance(item, dict)]
                meaningful = [item for item in candidates if any(key in item for key in ("path", "name", "children", "meta"))]
                return meaningful or []

            if isinstance(value, dict):
                for key in ("routes", "deviceMenu", "menu", "items"):
                    if key in value:
                        extracted = extract_routes(value[key], depth + 1)
                        if extracted:
                            return extracted
                for nested in value.values():
                    extracted = extract_routes(nested, depth + 1)
                    if extracted:
                        return extracted
            return []

        raw_routes = extract_routes(export_obj)
        return [self._attach_parameters_tokens(route) for route in raw_routes]

    PARAM_CALL_RE = re.compile(r"""[A-Za-z]\([^,]*?,\s*(['"])(?P<tok>[^'"]+)\1\)""")

    def _attach_parameters_tokens(self, node: dict[str, Any]) -> dict[str, Any]:
        """Attach parameter tokens to a node by processing its parameters section.

        After AST to dict conversion, items in parameters.* sections can be:
        - Literal strings (already valid tokens)
        - Call expressions as raw strings, e.g., "E(A.WRITE,'URUCHOMIENIE_KOTLA')"
            from which we extract the token using regex

        This method processes all parameter sections (read, write, status, special),
        extracts tokens from various formats, and normalizes them into a consistent
        dict structure with a "token" key. It recursively processes child nodes.

        Args:
                node: A dictionary representing a catalog node that may contain a
                        "parameters" section with read/write/status/special subsections,
                        and optionally a "children" list.

        Returns:
                A new dictionary with the same structure as the input node, but with
                parameters normalized to dicts containing "token" keys, and children
                recursively processed.
        """
        out = dict(node)
        params = out.get("parameters")
        if isinstance(params, dict):
            newp: dict[str, list[dict[str, Any]]] = {}
            for sec in ("read", "write", "status", "special"):
                items = params.get(sec, []) or []
                norm: list[dict[str, Any]] = []
                for it in items:
                    if isinstance(it, str):
                        original = it.strip()
                        m = self.PARAM_CALL_RE.search(original)
                        if m:
                            tok = m.group("tok")
                            norm.append({"token": tok, "parameter": original})
                        else:
                            norm.append({"token": original, "parameter": original})
                    elif isinstance(it, dict):
                        entry = dict(it)
                        param_value = entry.get("parameter")
                        if isinstance(param_value, str):
                            match = self.PARAM_CALL_RE.search(param_value)
                            if match and "token" not in entry:
                                entry["token"] = match.group("tok")
                        elif "token" in entry:
                            token_val = str(entry["token"])
                            entry.setdefault("parameter", token_val)
                        else:
                            fallback_text = str(it)
                            match = self.PARAM_CALL_RE.search(fallback_text)
                            if match:
                                entry["token"] = match.group("tok")
                                entry.setdefault("parameter", fallback_text)
                        if "parameter" not in entry and "token" in entry:
                            entry["parameter"] = str(entry["token"]) or ""
                        norm.append(entry)
                    else:
                        s = str(it)
                        m = self.PARAM_CALL_RE.search(s)
                        if m:
                            tok = m.group("tok")
                            norm.append({"token": tok, "parameter": s})
                        elif s:
                            norm.append({"token": s, "parameter": s})
                newp[sec] = norm
            out["parameters"] = newp
        # recursion for children
        ch = out.get("children")
        if isinstance(ch, list):
            out["children"] = [self._attach_parameters_tokens(c) if isinstance(c, dict) else c for c in ch]
        elif ch is not None:
            # Fix: If children exists but is not a list (e.g., string reference like 'wA'),
            # convert to empty list to prevent MenuManager errors
            self._log.debug(f"Converting non-list children to empty list: {type(ch)} {ch}")
            out["children"] = []
        return out

    # ---------- PARAM MAPS ----------

    async def get_param_mapping(self, tokens: Iterable[str]) -> dict[str, ParamMap]:
        """Retrieve parameter mappings for the given tokens.

        This method attempts to resolve parameter mappings for each provided token through
        a two-stage resolution process:

        1. First, it searches for a dedicated asset file named ``BASENAME-<hash>.js`` where
           BASENAME exactly matches the token.
        2. If no asset is found, and there is exactly one unresolved token with exactly
           one inline parameter candidate in the index, it attempts to use the inline
           parameter map from the ``index-*.js`` file as a fallback.
        3. Any tokens that cannot be resolved through either method are omitted from
           the results.

        Args:
             tokens: An iterable of token strings to resolve into parameter mappings.

        Returns:
             A dictionary mapping successfully resolved token strings to their
             corresponding ParamMap objects. Only tokens that were successfully
             resolved are included in the returned dictionary.

        Note:
             The method performs asset fetching concurrently using asyncio.gather for
             improved performance. Failed fetches are logged but do not raise exceptions.
        """
        uniq_tokens = list(dict.fromkeys(str(t) for t in tokens if t))

        if not self._idx.assets_by_basename:
            await self._ensure_index_loaded()

        # 1) file assets
        file_jobs: list[tuple[str, AssetRef]] = []
        unresolved: list[str] = []
        for tok in uniq_tokens:
            a = self._idx.find_asset_for_basename(tok)
            if a:
                file_jobs.append((tok, a))
            else:
                unresolved.append(tok)

        results: dict[str, ParamMap] = {}

        async def fetch_and_parse(tok: str, a: AssetRef) -> None:
            try:
                code = await self._api.get_bytes(a.url)
                pm = self._parse_param_map_from_js(code, tok, origin=f"asset:{a.url}")
                if pm:
                    results[tok] = pm
                else:
                    self._log.debug("PARAM MAP not found in asset (export not object?): %s", a.url)
            except Exception as e:
                self._log.warning("Param asset fetch failed %s: %s", a.url, e)

        await asyncio.gather(*(fetch_and_parse(tok, a) for tok, a in file_jobs), return_exceptions=False)

        # 2) inline fallback — only if index has exactly 1 candidate and 1 unresolved token
        if unresolved and len(unresolved) == 1 and len(self._idx.inline_param_candidates) == 1:
            tok = unresolved[0]
            start, end = self._idx.inline_param_candidates[0]
            chunk = self._idx.index_bytes[start:end]
            pm = self._parse_param_map_from_js(chunk, tok, origin="inline:index")
            if pm:
                results[tok] = pm
            else:
                self._log.debug("Inline param candidate didn't parse as expected for %s", tok)

        self._log.info(
            "PARAM MAPS: tokens=%d resolved=%d unresolved=%d", len(uniq_tokens), len(results), len(uniq_tokens) - len(results)
        )
        return results

    def _parse_param_map_from_js(self, code: bytes, key: str, origin: str) -> ParamMap | None:
        """Parse a JavaScript file (or index fragment) and extract a parameter map object.

        This method analyzes JavaScript code to find and parse an exported object that
        appears to be a parameter map. It extracts various fields like group, paths,
        component type, units, limits, and status flags, performing minimal normalization
        on the data structure.

        Args:
            code: The JavaScript source code as bytes to parse.
            key: A string identifier for this parameter map.
            origin: A string indicating the source/origin of this parameter map.

        Returns:
            A ParamMap object containing the parsed and normalized parameter data,
            or None if no valid parameter map could be extracted from the code.

        Note:
            The method performs minimal normalization by checking for alternative field
            names (e.g., 'group' or 'pool', 'use' fields or direct 'value'/'unit'/'status').
            The raw parsed object is preserved in the ParamMap's 'raw' attribute.
        """
        tree = self._ts.parse(code)
        root = _find_export_root(code, tree.root_node)
        node = root
        if node is None:
            return None
        obj = _object_to_python(code, node)
        if not isinstance(obj, dict):
            return None

        group = obj.get("group") or obj.get("pool")

        def _ensure_mapping_list(value: Any) -> list[dict[str, Any]]:
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, Mapping)]
            if isinstance(value, Mapping):
                return [dict(value)]
            return []

        def _normalize_status(value: Any) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
            conditions: dict[str, list[dict[str, Any]]] = {}
            flat: list[dict[str, Any]] = []
            if isinstance(value, Mapping):
                for raw_key, entries in value.items():
                    key_str = str(raw_key)
                    normalized_entries = _ensure_mapping_list(entries)
                    if not normalized_entries:
                        continue
                    conditions[key_str] = normalized_entries
                    for entry in normalized_entries:
                        enriched = dict(entry)
                        enriched.setdefault("condition", key_str)
                        flat.append(enriched)
            elif isinstance(value, list):
                normalized_entries = _ensure_mapping_list(value)
                if normalized_entries:
                    conditions["default"] = normalized_entries
                    flat.extend(normalized_entries)
            return conditions, flat

        def _normalize_literal(value: Any) -> Any:
            if isinstance(value, str):
                trimmed = value.strip()
                if trimmed == "void 0":
                    return None
                if trimmed == "undefined":
                    return None
                if trimmed == "!0":
                    return True
                if trimmed == "!1":
                    return False
            return value

        def _normalize_identifier(value: Any) -> str | None:
            if not isinstance(value, str):
                return None
            cleaned = value.strip()
            if not cleaned:
                return None
            if cleaned.startswith("[") and cleaned.endswith("]") and len(cleaned) > 2:
                cleaned = cleaned[1:-1]
            parts = cleaned.split(".", 1)
            if len(parts) == 2 and parts[0] in {"a", "e", "n", "o", "t"}:
                cleaned = parts[1]
            return cleaned

        def _normalize_condition_entries(entries: Any) -> list[dict[str, Any]]:
            conditions_list: list[dict[str, Any]] = []
            if not isinstance(entries, list):
                return conditions_list
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                condition = {
                    "operation": _normalize_identifier(entry.get("operation")),
                    "expected": _normalize_literal(entry.get("expected")),
                    "targets": _ensure_mapping_list(entry.get("value")),
                }
                conditions_list.append(condition)
            return conditions_list

        def _normalize_command_action(raw_action: Any) -> dict[str, Any] | None:
            if not isinstance(raw_action, Mapping):
                return None
            command = _normalize_identifier(raw_action.get("command"))
            value = _normalize_literal(raw_action.get("value"))
            action: dict[str, Any] = {}
            if command:
                action["command"] = command
            if value is not None:
                action["value"] = value
            return action if action else None

        def _normalize_command_branches(blocks: Any, logic_key: str) -> list[dict[str, Any]]:
            normalized: list[dict[str, Any]] = []
            if not isinstance(blocks, list):
                return normalized
            for entry in blocks:
                if not isinstance(entry, Mapping):
                    continue
                branch_key = None
                for candidate in ("if", "elseif", "else"):
                    if candidate in entry:
                        branch_key = candidate
                        break
                if branch_key is None:
                    branch_key = "if"
                conditions = _normalize_condition_entries(entry.get(branch_key)) if branch_key != "else" else []
                action_source = entry.get("then") if branch_key != "else" else entry.get("else")
                action = _normalize_command_action(action_source)
                if action is None:
                    continue
                normalized_entry: dict[str, Any] = {
                    "logic": logic_key,
                    "kind": branch_key,
                    "conditions": conditions,
                }
                normalized_entry.update(action)
                normalized.append(normalized_entry)
            return normalized

        value_paths = _ensure_mapping_list(obj.get("value"))
        unit_paths = _ensure_mapping_list(obj.get("unit"))
        command_paths = _ensure_mapping_list(obj.get("command"))
        min_paths = _ensure_mapping_list(obj.get("minValue") or obj.get("min"))
        max_paths = _ensure_mapping_list(obj.get("maxValue") or obj.get("max"))
        status_conditions, status_flat = _normalize_status(obj.get("status"))

        command_rules: list[dict[str, Any]] = []
        for logic_key in ("any", "all", "when"):
            command_rules.extend(_normalize_command_branches(obj.get(logic_key), logic_key))

        use = obj.get("use")
        if isinstance(use, Mapping):
            value_paths = value_paths or _ensure_mapping_list(use.get("v"))
            unit_paths = unit_paths or _ensure_mapping_list(use.get("u"))
            if not status_flat:
                _, status_flat = _normalize_status(use.get("s"))
            min_paths = min_paths or _ensure_mapping_list(use.get("n"))
            max_paths = max_paths or _ensure_mapping_list(use.get("x"))

        paths = {
            "value": value_paths,
            "unit": unit_paths,
            "status": status_flat,
            "command": command_paths,
            "min": min_paths,
            "max": max_paths,
        }
        component = obj.get("componentType")
        units_raw = obj.get("units") or obj.get("unit_name") or None
        limits = None
        for cand in ("limits", "range", "minmax"):
            if cand in obj and isinstance(obj[cand], dict):
                limits = obj[cand]
                break
        status_flags = obj.get("statusFlags") or obj.get("status_bits") or []

        return ParamMap(
            key=key,
            group=group if isinstance(group, str) else None,
            paths=paths,
            component_type=component if isinstance(component, str) else None,
            units=units_raw if isinstance(units_raw, (str, int, float)) else None,
            limits=limits,
            status_flags=status_flags if isinstance(status_flags, list) else [],
            status_conditions=status_conditions or None,
            command_rules=command_rules,
            origin=origin,
            raw=obj,
        )

    # ---------- Permissions helper ----------

    async def list_symbols_for_permissions(
        self,
        device_menu: int,
        permissions: Iterable[str],
    ) -> set[str]:
        """List symbols visible for given permissions.

        This is a convenient shortcut that fetches the menu for device_menu and returns
        tokens visible for the provided permissions. The schemas hook remains OFF.

        Args:
            device_menu: The device menu identifier.
            permissions: An iterable of permission strings to check visibility against.

        Returns:
            A set of token strings that are visible for the given permissions.
        """
        menu = await self.get_module_menu(device_menu=device_menu, permissions=permissions)
        return menu.all_tokens()

    # ---------- i18n support ----------

    async def list_language_config(self) -> TranslationConfig | None:
        """Get translation configuration from assets.

        Parses the ``index-*.js`` file to extract language configuration by structural patterns.
        The configuration object contains translations array and defaultTranslation field.
        """
        if not self._idx.index_bytes:
            await self._ensure_index_loaded()
        if not self._idx.index_bytes:
            self._log.warning("No index data available. Call refresh_index() or refresh_index_minimal() first.")
            return None

        try:
            return self._parse_language_config_from_js(self._idx.index_bytes)
        except Exception as e:
            self._log.warning("Failed to parse language config from index: %s", e)
            return None

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        """Get i18n mapping for a given language and namespace.

        Parses the index file for dynamic language imports in the format:
        "../../resources/languages/{lang}/{namespace}.json":()=>d(()=>import("./file-hash.js"),[]).then(e=>e.default)

        Then fetches and parses the corresponding asset file.

        Args:
            lang: Language code (e.g., 'en', 'pl').
            namespace: Namespace (e.g., 'parameters', 'units').

        Returns:
            Dictionary with translation mappings, or empty dict if not found.
        """
        if not self._idx.index_bytes:
            await self._ensure_index_loaded()
        if not self._idx.index_bytes:
            self._log.warning("No index data available for i18n lookup")
            return {}

        try:
            # Find the asset for this specific language/namespace combination
            asset_ref = self._find_i18n_asset(lang, namespace)
            if not asset_ref:
                self._log.debug("No i18n asset found for %s/%s", lang, namespace)
                return {}

            # Fetch and parse the i18n file
            code = await self._api.get_bytes(asset_ref.url)
            translations = self._parse_i18n_from_js(code)

            self._log.debug("Loaded i18n %s/%s: %d keys", lang, namespace, len(translations))
            return translations

        except Exception as e:
            self._log.warning("Failed to load i18n %s/%s: %s", lang, namespace, e)
            return {}

    def _find_i18n_asset(self, lang: str, namespace: str) -> AssetRef | None:
        """Find i18n asset for given language and namespace.

        Looks for patterns in index like:
        "../../resources/languages/{lang}/{namespace}.json":()=>d(()=>import("./file-hash.js"),[])

        Args:
            lang: Language code.
            namespace: Namespace (e.g., 'parameters', 'units').

        Returns:
            AssetRef for the i18n file or None if not found.
        """
        if not self._idx.index_bytes:
            return None

        index_text = self._idx.index_bytes.decode("utf-8", errors="replace")

        # Pattern to match: "../../resources/languages/{lang}/{namespace}.json":()=>d(()=>import("./filename-hash.js")
        # We need to extract the import file path and hash
        import_pattern = re.compile(
            rf'["\']\.\.\/\.\.\/resources\/languages\/{re.escape(lang)}\/{re.escape(namespace)}\.json["\']'
            r':\s*\(\)\s*=>\s*\w+\s*\(\s*\(\)\s*=>\s*import\s*\(\s*["\']\.\/([^"\']+)-([A-Za-z0-9_]+)\.js["\']'
        )

        match = import_pattern.search(index_text)
        if not match:
            self._log.debug("No i18n asset pattern match for %s/%s. Pattern: %s", lang, namespace, import_pattern.pattern)
            return None

        file_base = match.group(1)  # e.g., "parameters"
        file_hash = match.group(2)  # e.g., "BNvCCsxi"

        # Construct the full asset filename and URL
        asset_filename = f"{file_base}-{file_hash}.js"

        # Look up the asset in our index by basename
        # The basename should match the file_base (e.g., "parameters")
        asset_ref = self._idx.find_asset_for_basename(file_base)
        if asset_ref and asset_ref.hash == file_hash:
            return asset_ref

        # Fallback: construct URL based on index URL pattern
        # This assumes the i18n files are in the same directory as the index
        if hasattr(self, "_last_index_url") and self._last_index_url:
            asset_url = self._smart_urljoin(self._last_index_url, asset_filename)
            return AssetRef(url=asset_url, base=file_base, hash=file_hash)

        return None

    def _parse_i18n_from_js(self, code: bytes) -> dict[str, Any]:
        """Parse i18n translations from a JavaScript module.

        Expected format:
        export default { "key1": "value1", "key2": "value2", ... }

        Args:
            code: JavaScript source code bytes.

        Returns:
            Dictionary of translations.
        """
        try:
            tree = self._ts.parse(code)
            root = tree.root_node
            code_text = code.decode("utf-8", errors="replace")

            bindings: dict[str, Any] = {}

            # Collect constant bindings so we can resolve identifier references
            for child in root.named_children:
                if child.type != "lexical_declaration":
                    continue
                for declarator in child.named_children:
                    if declarator.type != "variable_declarator":
                        continue
                    name_node = declarator.child_by_field_name("name")
                    value_node = declarator.child_by_field_name("value")
                    if name_node is None or value_node is None:
                        continue
                    name = _node_text(code, name_node).strip()
                    if not name:
                        continue
                    bindings[name] = _node_to_python(code, value_node, bindings)

            translations: Any | None = None

            # Prefer explicit `export default <expr>` if present.
            for child in root.named_children:
                if child.type != "export_statement":
                    continue
                value_node = child.child_by_field_name("value")
                if value_node is not None:
                    translations = _node_to_python(code, value_node, bindings)
                    break

            if translations is None:
                match = re.search(
                    r"export\s*\{[^}]*?([A-Za-z0-9_$]+)\s+as\s+default",
                    code_text,
                )
                if match:
                    default_name = match.group(1)
                    candidate = bindings.get(default_name)
                    if candidate is not None:
                        translations = candidate

            if translations is None:
                export_root = _find_export_root(code, root)
                if export_root is not None:
                    translations = _node_to_python(code, export_root, bindings)

            if isinstance(translations, dict):
                return translations

            if translations is not None:
                self._log.warning("i18n export is not an object: %s", type(translations))
            return {}

        except Exception as e:
            self._log.warning("Failed to parse i18n JavaScript: %s", e)
            return {}

    def _parse_language_config_from_js(self, js_bytes: bytes) -> TranslationConfig | None:
        """Parse language configuration from JavaScript code using tree-sitter.

        Looks for language configuration objects with translations array and defaultTranslation.

        Args:
            js_bytes: Raw JavaScript code as bytes.

        Returns:
            TranslationConfig object or None if parsing fails.
        """
        try:
            tree = self._ts.parse(js_bytes)

            # Look for language configuration object by structure pattern
            lang_config_object = self._find_language_config_object_bytes(tree, js_bytes)
            if not lang_config_object:
                return None

            # Extract translations array and defaultTranslation
            translations = self._extract_translations_array_bytes(lang_config_object, js_bytes)
            default_translation = self._extract_default_translation_bytes(lang_config_object, js_bytes)

            if not translations or not default_translation:
                return None

            return TranslationConfig(translations=translations, default_translation=default_translation)

        except Exception as e:
            self._log.warning("Failed to parse JS language config: %s", e)
            return None

    def _find_language_config_object_bytes(self, tree: Tree, js_bytes: bytes) -> Node | None:
        """Find language configuration object by structure pattern (bytes version).

        Searches for objects containing:
        - 'translations' array with objects having 'id' and 'flag' properties
        - 'defaultTranslation' string property

        This method is resilient to variable name changes during minification and
        works with any variable assignment (var/const/let) or object property.
        """

        def get_node_text_local(node: Node) -> str:
            """Local helper to extract node text from bytes."""
            node_bytes = js_bytes[node.start_byte : node.end_byte]
            node_text = node_bytes.decode("utf-8", errors="replace")
            # Remove quotes from string literals
            if (
                node.type in ("string", "property_identifier")
                and len(node_text) >= 2
                and (
                    (node_text.startswith('"') and node_text.endswith('"'))
                    or (node_text.startswith("'") and node_text.endswith("'"))
                )
            ):
                return node_text[1:-1]
            return node_text

        def is_language_config_object(obj_node: Node) -> bool:
            """Check if this object looks like a language configuration."""
            if obj_node.type != "object":
                return False

            has_translations = False
            has_default_translation = False

            for pair in obj_node.children:
                if pair.type != "pair":
                    continue

                key_node = pair.child_by_field_name("key")
                value_node = pair.child_by_field_name("value")

                if not (key_node and value_node):
                    continue

                key_text = get_node_text_local(key_node)

                # Look for translations array
                if key_text == "translations" and value_node.type == "array":
                    # Check if array contains objects with language-like structure
                    if is_translations_array_local(value_node):
                        has_translations = True

                # Look for defaultTranslation string
                elif key_text == "defaultTranslation" and value_node.type == "string":
                    has_default_translation = True

            result = has_translations and has_default_translation
            return result

        def is_translations_array_local(array_node: Node) -> bool:
            """Local helper to check if array looks like translations array."""
            valid_entries = 0
            total_objects = 0

            for child in array_node.children:
                if child.type == "object":
                    total_objects += 1
                    has_id = False
                    has_flag = False

                    for pair in child.children:
                        if pair.type != "pair":
                            continue

                        key_node = pair.child_by_field_name("key")
                        if not key_node:
                            continue

                        key_text = get_node_text_local(key_node)
                        if key_text == "id":
                            has_id = True
                        elif key_text == "flag":
                            has_flag = True

                    if has_id and has_flag:
                        valid_entries += 1

            # Consider it a translations array if most objects have the expected structure
            threshold = total_objects * 0.7
            return total_objects > 0 and valid_entries >= threshold

        def visit_node(node: Node) -> Node | None:
            # Check all object literals for language config pattern
            if node.type == "object" and is_language_config_object(node):
                return node

            # Also check variable assignments and property values
            if node.type == "variable_declarator":
                value_node = node.child_by_field_name("value")
                if value_node and value_node.type == "object" and is_language_config_object(value_node):
                    return value_node

            elif node.type == "assignment_expression":
                right = node.child_by_field_name("right")
                if right and right.type == "object" and is_language_config_object(right):
                    return right

            # Recursively search children
            for child in node.children:
                result = visit_node(child)
                if result:
                    return result
            return None

        return visit_node(tree.root_node)

    def _find_language_config_object(self, tree: Tree, text: str) -> Node | None:
        """Find language configuration object by structure pattern (string version).

        Searches for objects containing:
        - 'translations' array with objects having 'id' and 'flag' properties
        - 'defaultTranslation' string property

        This method is resilient to variable name changes during minification and
        works with any variable assignment (var/const/let) or object property.

        Note: This is the legacy string-based version. Use _find_language_config_object_bytes
        for better Unicode support.
        """

        def get_node_text_local(node: Node) -> str:
            """Local helper to extract node text."""
            node_text = text[node.start_byte : node.end_byte]
            # Remove quotes from string literals
            if (
                node.type in ("string", "property_identifier")
                and len(node_text) >= 2
                and (
                    (node_text.startswith('"') and node_text.endswith('"'))
                    or (node_text.startswith("'") and node_text.endswith("'"))
                )
            ):
                return node_text[1:-1]
            return node_text

        def is_language_config_object(obj_node: Node) -> bool:
            """Check if this object looks like a language configuration."""
            if obj_node.type != "object":
                return False

            has_translations = False
            has_default_translation = False

            for pair in obj_node.children:
                if pair.type != "pair":
                    continue

                key_node = pair.child_by_field_name("key")
                value_node = pair.child_by_field_name("value")

                if not (key_node and value_node):
                    continue

                key_text = get_node_text_local(key_node)

                # Look for translations array
                if key_text == "translations" and value_node.type == "array":
                    # Check if array contains objects with language-like structure
                    if is_translations_array_local(value_node):
                        has_translations = True

                # Look for defaultTranslation string
                elif key_text == "defaultTranslation" and value_node.type == "string":
                    has_default_translation = True

            result = has_translations and has_default_translation
            return result

        def is_translations_array_local(array_node: Node) -> bool:
            """Local helper to check if array looks like translations array."""
            valid_entries = 0
            total_objects = 0

            for child in array_node.children:
                if child.type == "object":
                    total_objects += 1
                    has_id = False
                    has_flag = False

                    for pair in child.children:
                        if pair.type != "pair":
                            continue

                        key_node = pair.child_by_field_name("key")
                        if not key_node:
                            continue

                        key_text = get_node_text_local(key_node)
                        if key_text == "id":
                            has_id = True
                        elif key_text == "flag":
                            has_flag = True

                    if has_id and has_flag:
                        valid_entries += 1

            # Consider it a translations array if most objects have the expected structure
            threshold = total_objects * 0.7
            return total_objects > 0 and valid_entries >= threshold

        def visit_node(node: Node) -> Node | None:
            # Check all object literals for language config pattern
            if node.type == "object" and is_language_config_object(node):
                return node

            # Also check variable assignments and property values
            if node.type == "variable_declarator":
                value_node = node.child_by_field_name("value")
                if value_node and value_node.type == "object" and is_language_config_object(value_node):
                    return value_node

            elif node.type == "assignment_expression":
                right = node.child_by_field_name("right")
                if right and right.type == "object" and is_language_config_object(right):
                    return right

            # Recursively search children
            for child in node.children:
                result = visit_node(child)
                if result:
                    return result
            return None

        return visit_node(tree.root_node)

    def _is_translations_array(self, array_node: Node, text: str) -> bool:
        """Check if an array looks like a translations array.

        Looks for array elements that are objects with 'id' and 'flag' properties,
        which is the signature of language configuration entries.
        """
        valid_entries = 0
        total_objects = 0

        for child in array_node.children:
            if child.type == "object":
                total_objects += 1
                has_id = False
                has_flag = False

                for pair in child.children:
                    if pair.type != "pair":
                        continue

                    key_node = pair.child_by_field_name("key")
                    if not key_node:
                        continue

                    key_text = self._get_node_text(key_node, text)
                    if key_text == "id":
                        has_id = True
                    elif key_text == "flag":
                        has_flag = True

                if has_id and has_flag:
                    valid_entries += 1

        # Consider it a translations array if most objects have the expected structure
        threshold = total_objects * 0.7
        return total_objects > 0 and valid_entries >= threshold

    def _extract_translations_array_bytes(self, obj_node: Node, js_bytes: bytes) -> list[dict[str, Any]] | None:
        """Extract translations array from language configuration object (bytes version)."""
        for pair in obj_node.children:
            if pair.type == "pair":
                key_node = pair.child_by_field_name("key")
                if key_node:
                    key_bytes = js_bytes[key_node.start_byte : key_node.end_byte]
                    key_text = key_bytes.decode("utf-8", errors="replace")
                    if key_text == "translations":
                        value_node = pair.child_by_field_name("value")
                        if value_node and value_node.type == "array":
                            return self._parse_translations_array_bytes(value_node, js_bytes)
        return None

    def _extract_default_translation_bytes(self, obj_node: Node, js_bytes: bytes) -> str | None:
        """Extract defaultTranslation from language configuration object (bytes version)."""
        for pair in obj_node.children:
            if pair.type == "pair":
                key_node = pair.child_by_field_name("key")
                if key_node:
                    key_bytes = js_bytes[key_node.start_byte : key_node.end_byte]
                    key_text = key_bytes.decode("utf-8", errors="replace")
                    if key_text == "defaultTranslation":
                        value_node = pair.child_by_field_name("value")
                        if value_node and value_node.type == "string":
                            # Remove quotes from string literal
                            value_bytes = js_bytes[value_node.start_byte : value_node.end_byte]
                            value_text = value_bytes.decode("utf-8", errors="replace")
                            return value_text.strip("\"'")
        return None

    def _parse_translations_array_bytes(self, array_node: Node, js_bytes: bytes) -> list[dict[str, Any]]:
        """Parse the translations array into Python list of dicts (bytes version)."""
        translations = []
        for child in array_node.children:
            if child.type == "object":
                translation = self._parse_translation_object_bytes(child, js_bytes)
                if translation:
                    translations.append(translation)
        return translations

    def _parse_translation_object_bytes(self, obj_node: Node, js_bytes: bytes) -> dict[str, Any] | None:
        """Parse a single translation object (bytes version)."""
        translation = {}
        for pair in obj_node.children:
            if pair.type == "pair":
                key_node = pair.child_by_field_name("key")
                value_node = pair.child_by_field_name("value")
                if key_node and value_node:
                    key_bytes = js_bytes[key_node.start_byte : key_node.end_byte]
                    key = key_bytes.decode("utf-8", errors="replace")
                    value = self._parse_js_value_bytes(value_node, js_bytes)
                    translation[key] = value
        return translation if translation else None

    def _parse_js_value_bytes(self, node: Node, js_bytes: bytes) -> Any:
        """Parse a JavaScript value node into Python equivalent (bytes version)."""
        if node.type == "string":
            val_bytes = js_bytes[node.start_byte : node.end_byte]
            val_text = val_bytes.decode("utf-8", errors="replace")
            return val_text.strip("\"'")
        elif node.type == "number":
            val_bytes = js_bytes[node.start_byte : node.end_byte]
            val_text = val_bytes.decode("utf-8", errors="replace")
            return int(val_text) if "." not in val_text else float(val_text)
        elif node.type == "true":
            return True
        elif node.type == "false":
            return False
        elif node.type == "null":
            return None
        elif node.type == "object":
            obj = {}
            for pair in node.children:
                if pair.type == "pair":
                    key_node = pair.child_by_field_name("key")
                    value_node = pair.child_by_field_name("value")
                    if key_node and value_node:
                        key_bytes = js_bytes[key_node.start_byte : key_node.end_byte]
                        key = key_bytes.decode("utf-8", errors="replace")
                        value = self._parse_js_value_bytes(value_node, js_bytes)
                        obj[key] = value
            return obj
        elif node.type == "array":
            arr = []
            for child in node.children:
                if child.type not in (",", "[", "]"):
                    arr.append(self._parse_js_value_bytes(child, js_bytes))
            return arr
        else:
            # Fallback to raw text
            val_bytes = js_bytes[node.start_byte : node.end_byte]
            return val_bytes.decode("utf-8", errors="replace")

    def _extract_translations_array(self, obj_node: Node, text: str) -> list[dict[str, Any]] | None:
        """Extract translations array from language configuration object."""
        for pair in obj_node.children:
            if pair.type == "pair":
                key_node = pair.child_by_field_name("key")
                if key_node and self._get_node_text(key_node, text) == "translations":
                    value_node = pair.child_by_field_name("value")
                    if value_node and value_node.type == "array":
                        return self._parse_translations_array(value_node, text)
        return None

    def _extract_default_translation(self, obj_node: Node, text: str) -> str | None:
        """Extract defaultTranslation from language configuration object."""
        for pair in obj_node.children:
            if pair.type == "pair":
                key_node = pair.child_by_field_name("key")
                if key_node and self._get_node_text(key_node, text) == "defaultTranslation":
                    value_node = pair.child_by_field_name("value")
                    if value_node and value_node.type == "string":
                        # Remove quotes from string literal
                        return self._get_node_text(value_node, text).strip("\"'")
        return None

    def _parse_translations_array(self, array_node: Node, text: str) -> list[dict[str, Any]]:
        """Parse the translations array into Python list of dicts."""
        translations = []
        for child in array_node.children:
            if child.type == "object":
                translation = self._parse_translation_object(child, text)
                if translation:
                    translations.append(translation)
        return translations

    def _parse_translation_object(self, obj_node: Node, text: str) -> dict[str, Any] | None:
        """Parse a single translation object."""
        translation = {}
        for pair in obj_node.children:
            if pair.type == "pair":
                key_node = pair.child_by_field_name("key")
                value_node = pair.child_by_field_name("value")
                if key_node and value_node:
                    key = self._get_node_text(key_node, text)
                    value = self._parse_js_value(value_node, text)
                    translation[key] = value
        return translation if translation else None

    def _parse_js_value(self, node: Node, text: str) -> Any:
        """Parse a JavaScript value node into Python equivalent."""
        if node.type == "string":
            return self._get_node_text(node, text).strip("\"'")
        elif node.type == "number":
            val_text = self._get_node_text(node, text)
            return int(val_text) if "." not in val_text else float(val_text)
        elif node.type == "true":
            return True
        elif node.type == "false":
            return False
        elif node.type == "null":
            return None
        elif node.type == "object":
            obj = {}
            for pair in node.children:
                if pair.type == "pair":
                    key_node = pair.child_by_field_name("key")
                    value_node = pair.child_by_field_name("value")
                    if key_node and value_node:
                        key = self._get_node_text(key_node, text)
                        value = self._parse_js_value(value_node, text)
                        obj[key] = value
            return obj
        elif node.type == "array":
            arr = []
            for child in node.children:
                if child.type != "," and child.type != "[" and child.type != "]":
                    arr.append(self._parse_js_value(child, text))
            return arr
        else:
            # Fallback to raw text
            return self._get_node_text(node, text)

    def _get_node_text(self, node: Node, text: str) -> str:
        """Extract text content of a node, handling quoted strings."""
        node_text = text[node.start_byte : node.end_byte]
        # Remove quotes from string literals
        if (
            node.type == "string"
            and len(node_text) >= 2
            and (
                (node_text.startswith('"') and node_text.endswith('"')) or (node_text.startswith("'") and node_text.endswith("'"))
            )
        ):
            return node_text[1:-1]
        return node_text
