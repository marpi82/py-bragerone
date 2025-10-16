"""Implementation of live asset catalog parsing from BragerOne web app.

This module provides classes and utilities for parsing and managing live assets
from the BragerOne web application, including:
- LiveAssetsCatalog: Main entry point for fetching and parsing assets
- AssetRef, AssetIndex: Data structures for tracking asset references
- MenuResult, ParamMap: Data structures for menu routes and parameter mappings
- TranslationConfig: Configuration for available translations
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import urljoin

from tree_sitter import Node, Parser, Tree
from tree_sitter_javascript import language as TS_JS_LANGUAGE

from ..api import BragerOneApiClient

JS_LANGUAGE = TS_JS_LANGUAGE()


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
    """Index of assets parsed from index-*.js file.

    Attributes:
        assets_by_basename: Full list of assets declared in index-*.js (exact basenames, no normalization).
            Maps basename strings to lists of AssetRef objects.
        menu_map: Mapping from deviceMenu integers to BASENAME strings (e.g., 'module.menu-<hash>.js').
        inline_param_candidates: List of (start_byte, end_byte) tuples indicating potential
            inline parameter maps detected within index-*.js.
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


@dataclass(slots=True)
class ParamMap:
    """Represents a parameter mapping in the Brager One system.

    This class encapsulates the mapping between parameter identifiers and their
    metadata, including paths, units, limits, and status flags. It serves as a
    structured representation of parameter configurations retrieved from the router.

    Attributes:
        key: The unique parameter identifier token from the router.
            Examples: "URUCHOMIENIE_KOTLA", "PARAM_66".
        group: Optional parameter group identifier. Example: "P6".
        paths: Dictionary mapping path types to their respective path lists.
            Keys include "v" (value), "u" (unit), "s" (status), "x", and "n" (name).
        component_type: Optional type of the UI component associated with this parameter.
        units: Optional string representing the measurement units for this parameter.
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
    paths: dict[str, list[str]]  # {"v": [...], "u": [...], "s":[...], "x":[...], "n":[...]}
    component_type: str | None
    units: str | None
    limits: dict[str, Any] | None
    status_flags: list[dict[str, Any]]
    origin: str  # "asset:<url>" or "inline:index"
    raw: dict[str, Any]  # raw map (will be useful later for i18n/logging)


@dataclass(slots=True)
class MenuResult:
    """Result container for menu processing operations.

    This class encapsulates the results of menu processing, including the router
    tree structure, extracted tokens, and origin information.

    Attributes:
        routes: A list of dictionaries representing the router tree structure in a
            1:1 mapping. Each dictionary contains route configuration details.
        tokens: A set of unique token strings extracted from parameters after
            gating logic has been applied.
        origin_asset: Reference to the source asset from which the menu was derived,
            or None if no asset reference exists.
        origin_inline: Boolean flag indicating whether the menu was processed inline.
            This is typically False but kept for completeness.

    Example:
        >>> result = MenuResult(
        ...     routes=[{"path": "/home", "component": "Home"}],
        ...     tokens={"PARAM_1", "PARAM_2"},
        ...     origin_asset=AssetRef("http://example.com/menu.js", "menu", "abc123"),
        ...     origin_inline=False
        ... )
    """

    routes: list[dict[str, Any]]  # router tree 1:1
    tokens: set[str]  # all tokens from parameters.* (after gating)
    origin_asset: AssetRef | None
    origin_inline: bool  # True if menu was inline (unlikely, but kept)


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
        cast(Any, self.parser).set_language(JS_LANGUAGE)

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


def _object_to_python(code: bytes, node: Node) -> Any:
    """Minimal AST → Python converter.

    - object → dict (recursively)
    - array  → list (recursively)
    - string/template → str (with quotes stripped)
    - number/bool/null → primitives
    - rest (e.g. call_expression) → raw text (_node_text)
    """
    t = node.type
    if t == "object":
        out: dict[str, Any] = {}
        for prop in node.named_children:
            if prop.type != "pair":
                continue
            k = prop.child_by_field_name("key")
            v = prop.child_by_field_name("value")
            if not (k and v):
                continue
            key_txt = _node_text(code, k)
            key = _string_value(key_txt) if _is_string(k) else key_txt
            out[key] = _object_to_python(code, v)
        return out
    if t == "array":
        return [_object_to_python(code, ch) for ch in node.named_children]
    if _is_string(node):
        return _string_value(_node_text(code, node))
    if t == "number":
        s = _node_text(code, node)
        try:
            return float(s) if any(c in s for c in ".eE") else int(s)
        except Exception:
            return s
    if t in {"true", "false"}:
        return t == "true"
    if t == "null":
        return None
    return _node_text(code, node)


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

    # ---------- lifecycle ----------

    async def __aenter__(self) -> LiveAssetsCatalog:
        """Enter the async context manager and return self."""
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Exit the async context manager."""
        pass

    # ---------- INDEX ----------

    async def refresh_index(self, index_url: str) -> None:
        """Fetches index-<hash>.js and builds.

        - assets_by_basename (exact BASENAME → [AssetRef])
        - menu_map: int -> BASENAME(module.menu-<hash>.js), if present in index
        - inline_param_candidates: list of (start,end) large objects in index that look like param-maps
        """
        code = await self._api.get_bytes(index_url)
        self._idx = self._build_asset_index_from_index_js(index_url, code)
        self._log.info(
            "INDEX: assets=%d basenames=%d menus=%d inline_param_candidates=%d",
            sum(len(v) for v in self._idx.assets_by_basename.values()),
            len(self._idx.assets_by_basename),
            len(self._idx.menu_map),
            len(self._idx.inline_param_candidates),
        )

    def _build_asset_index_from_index_js(self, index_url: str, code: bytes) -> AssetIndex:
        text = code.decode("utf-8", errors="replace")

        # 1) Collect all '*-<hash>.js' paths from literals (zero assumptions about directory)
        #    BASENAME = everything up to the last '-' before .js extension
        path_re = re.compile(
            r'(?P<url>(?P<prefix>/[^"\'`\s]+/)?(?P<base>[^"\'`\s-]+(?:\.[^"\'`\s-]+)*)-(?P<hash>[A-Za-z0-9_]+)\.js)'
        )
        assets_by_basename: dict[str, list[AssetRef]] = {}
        for m in path_re.finditer(text):
            url_rel = m.group("url")
            base = m.group("base")
            h = m.group("hash")
            full_url = urljoin(index_url, url_rel)
            assets_by_basename.setdefault(base, []).append(AssetRef(url=full_url, base=base, hash=h))

        # 2) Try to find mapping from deviceMenu:int -> 'module.menu-<hash>.js' in index (AST)
        tree = self._ts.parse(code)
        menu_map: dict[int, str] = {}
        for n in _walk(tree.root_node):
            if n.type == "object":
                for pair in n.named_children:
                    if pair.type != "pair":
                        continue
                    k = pair.child_by_field_name("key")
                    v = pair.child_by_field_name("value")
                    if not (k and v):
                        continue
                    # numeric key?
                    key_txt = _node_text(code, k)
                    try:
                        key_int = int(_string_value(key_txt))
                    except Exception:
                        continue
                    # value: string containing 'module.menu-...js'
                    val_txt = _node_text(code, v)
                    if "module.menu-" in val_txt and ".js" in val_txt:
                        # try to extract BASENAME (without -hash.js)
                        mm = re.search(r"(module\.menu)-[A-Za-z0-9_]+\.js", val_txt)
                        if mm:
                            menu_map[key_int] = mm.group(1)  # 'module.menu'
        # 3) Inline param-map candidates (large object literals)
        inline_candidates: list[tuple[int, int]] = []
        for n in _walk(tree.root_node):
            if n.type == "object":
                approx_len = n.end_byte - n.start_byte
                if approx_len > 200:  # heuristic: larger objects are more likely to be maps
                    # quick "shape" of param-map: look for keywords inside
                    snippet = code[n.start_byte : n.end_byte]
                    if any(key in snippet for key in (b"group", b"pool", b"use", b"value", b"unit", b"status", b"componentType")):
                        inline_candidates.append((n.start_byte, n.end_byte))

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
    ) -> MenuResult:
        """Matches 'module.menu-<hash>.js' based on map from index-*.js and device_menu (REST).

        Parses menu to tree, does permissions-gating (strategy 'independent'),
        collects unique tokens from parameters.* and returns result.
        """
        # 1) find BASENAME for device_menu (if present in index), otherwise fallback to 'module.menu'
        basename = self._idx.menu_map.get(device_menu, "module.menu")
        asset = self._idx.find_asset_for_basename(basename)
        if not asset:
            # fallback: try anything starting with 'module.menu' (preserving "Alpha accuracy")
            asset = self._idx.find_asset_for_basename("module.menu")
        if not asset:
            raise RuntimeError(f"Brak assetu menu dla device_menu={device_menu}")

        code = await self._api.get_bytes(asset.url)
        routes = self._parse_menu_routes(code)
        # permissions gating (independent)
        perms = set(permissions or [])
        routes_gated = self._gate_routes_independent(routes, perms)
        tokens = self._collect_tokens_from_routes(routes_gated)

        self._log.info(
            "MENU: nodes=%d tokens=%d (device_menu=%s, asset=%s)",
            self._count_nodes(routes_gated),
            len(tokens),
            device_menu,
            asset.url,
        )

        return MenuResult(routes=routes_gated, tokens=tokens, origin_asset=asset, origin_inline=False)

    def _parse_menu_routes(self, code: bytes) -> list[dict[str, Any]]:
        """Returning list of root-routes (1:1 with export in module.menu-*.js)."""
        tree = self._ts.parse(code)
        root = _find_export_root(code, tree.root_node)
        if root is None:
            return []
        obj = _object_to_python(code, root)
        # menu can be an array or a dict with key 'routes'
        if isinstance(obj, list):
            return [self._attach_parameters_tokens(e) for e in obj if isinstance(e, dict)]
        if isinstance(obj, dict):
            if isinstance(obj.get("routes"), list):
                return [self._attach_parameters_tokens(e) for e in obj["routes"] if isinstance(e, dict)]
            return [self._attach_parameters_tokens(obj)]
        return []

    PARAM_CALL_RE = re.compile(r"""[A-Z]\([^,]*?,\s*(['"])(?P<tok>[^'"]+)\1\)""")

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
                        m = self.PARAM_CALL_RE.search(it)
                        if m:
                            tok = m.group("tok")
                            norm.append({"token": tok})
                        else:
                            # if it was already a literal, treat as token
                            norm.append({"token": it.strip()})
                    elif isinstance(it, dict) and "token" in it:
                        norm.append({"token": str(it["token"])})
                    else:
                        # fallback: try str(it)
                        s = str(it)
                        m = self.PARAM_CALL_RE.search(s)
                        if m:
                            norm.append({"token": m.group("tok")})
                newp[sec] = norm
            out["parameters"] = newp
        # recursion for children
        ch = out.get("children")
        if isinstance(ch, list):
            out["children"] = [self._attach_parameters_tokens(c) if isinstance(c, dict) else c for c in ch]
        return out

    def _gate_routes_independent(self, routes: list[dict[str, Any]], permissions: set[str]) -> list[dict[str, Any]]:
        def gate(node: dict[str, Any]) -> dict[str, Any]:
            meta = node.get("meta") or {}
            perm = meta.get("permissionModule")
            visible = (perm in permissions) if (permissions and perm) else True
            # filter elements parameters.* by their own perms (if we ever start extracting them),
            # in Alpha we keep tokens without perm-per-item
            params = node.get("parameters") or {}
            if isinstance(params, dict):
                for sec in ("read", "write", "status", "special"):
                    lst = params.get(sec) or []
                    # on Alpha: no per-item filtering (perm), only node-level
                    params[sec] = lst
                node["parameters"] = params
            node["_visible"] = bool(visible)
            # children: we don't inherit visibility (strategy 'independent')
            children = node.get("children") or []
            if isinstance(children, list):
                node["children"] = [gate(c) for c in children if isinstance(c, dict)]
            return node

        return [gate(r) for r in routes]

    def _collect_tokens_from_routes(self, routes: list[dict[str, Any]]) -> set[str]:
        out: set[str] = set()

        def walk(n: dict[str, Any]) -> None:
            params = n.get("parameters") or {}
            if isinstance(params, dict):
                for sec in ("read", "write", "status", "special"):
                    for el in params.get(sec, []) or []:
                        tok = el.get("token")
                        if tok:
                            out.add(str(tok))
            for c in n.get("children") or []:
                if isinstance(c, dict):
                    walk(c)

        for r in routes:
            walk(r)
        return out

    @staticmethod
    def _count_nodes(routes: list[dict[str, Any]]) -> int:
        cnt = 0

        def walk(n: dict[str, Any]) -> None:
            nonlocal cnt
            cnt += 1
            for c in n.get("children") or []:
                if isinstance(c, dict):
                    walk(c)

        for r in routes:
            walk(r)
        return cnt

    # ---------- PARAM MAPS ----------

    async def get_param_mapping(self, tokens: Iterable[str]) -> dict[str, ParamMap]:
        """Retrieve parameter mappings for the given tokens.

        This method attempts to resolve parameter mappings for each provided token through
        a two-stage resolution process:
        1. First, it searches for a dedicated asset file named 'BASENAME-<hash>.js' where
            BASENAME exactly matches the token.
        2. If no asset is found, and there is exactly one unresolved token with exactly
            one inline parameter candidate in the index, it attempts to use the inline
            parameter map from the index-*.js file as a fallback.
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

        # Minimal normalization: group/pool + use or value/unit/status/x/n
        group = obj.get("group") or obj.get("pool")
        use = obj.get("use") or {}
        paths = {
            "v": list(use.get("v") or obj.get("value") or []),
            "u": list(use.get("u") or obj.get("unit") or []),
            "s": list(use.get("s") or obj.get("status") or []),
            "x": list(use.get("x") or []),
            "n": list(use.get("n") or []),
        }
        component = obj.get("componentType")
        units = obj.get("units") or obj.get("unit_name") or None
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
            units=units if isinstance(units, str) else None,
            limits=limits,
            status_flags=status_flags if isinstance(status_flags, list) else [],
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
        m = await self.get_module_menu(device_menu=device_menu, permissions=permissions)
        return m.tokens
