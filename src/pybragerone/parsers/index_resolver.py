"""Resolve asset URLs by parsing index*.js for dynamic import maps."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..api import BragerOneApiClient
from ..consts import ONE_BASE


@dataclass(slots=True)
class IndexMap:
    """Mapping of asset names to URLs extracted from index*.js."""

    i18n: dict[str, str]
    parameters: dict[str, str]
    module_menu: str | None = None


class IndexResolver:
    """Resolve asset URLs by scanning index*.js for dynamic import maps."""

    def __init__(self, api: BragerOneApiClient) -> None:
        """Initialize with a BragerOneApiClient instance."""
        self._api = api
        self._cached: IndexMap | None = None

    async def _fetch_index_text(self) -> str:
        """Fetch index*.js text from the server."""
        # Try a few common entry points
        session = await self._api._ensure_session()
        for path in ("/assets/index.js", "/assets/index.mjs", "/"):
            async with session.request("GET", f"{ONE_BASE}{path}") as r:
                if r.status == 200:
                    return await r.text()
        raise RuntimeError("Could not fetch index to resolve assets.")

    @staticmethod
    def _parse_index(text: str) -> IndexMap:
        """Parse index*.js text to extract dynamic import maps."""
        # dynamic import map for i18n
        i18n_pat = re.compile(
            r"\.{2}/\.{2}/resources/languages/(?P<lang>[a-z]{2})/(?P<ns>[a-zA-Z0-9_\-]+)\.json.*?import\(\"\./(?P<asset>[a-zA-Z0-9_.\-]+)\"\)",
            re.DOTALL,
        )
        i18n = {
            f"resources/languages/{m.group('lang')}/{m.group('ns')}.json": f"/assets/{m.group('asset')}"
            for m in i18n_pat.finditer(text)
        }
        # mapping assets: allow PARAM_* and other ALLCAPS_WITH_UNDERSCORES names
        param_pat = re.compile(r"(?P<name>[A-Z0-9_]+)\s*[:=].*?import\(\"\./(?P<asset>[A-Za-z0-9_\-\.]+)\"\)")
        parameters = {m.group("name"): f"/assets/{m.group('asset')}" for m in param_pat.finditer(text)}
        # module.menu
        menu = None
        m = re.search(r"import\(\"\./(module\.menu-[a-zA-Z0-9_.\-]+)\"\)", text)
        if m:
            menu = f"/assets/{m.group(1)}"
        return IndexMap(i18n=i18n, parameters=parameters, module_menu=menu)

    async def ensure_map(self) -> IndexMap:
        """Ensure the index map is loaded and return it."""
        if self._cached is None:
            self._cached = self._parse_index(await self._fetch_index_text())
        return self._cached

    async def url_for_i18n(self, lang: str, namespace: str) -> str:
        """Get URL for an i18n asset by language code and namespace."""
        m = await self.ensure_map()
        key = f"resources/languages/{lang}/{namespace}.json"
        asset = m.i18n.get(key)
        if not asset:
            raise KeyError(f"No i18n asset for {key}")
        return f"{ONE_BASE}{asset}"

    async def url_for_param(self, symbol_or_filename: str) -> str:
        """Get URL for a parameter asset by symbol (e.g. PARAM_X) or filename (e.g. param-x.js)."""
        m = await self.ensure_map()
        asset = m.parameters.get(symbol_or_filename)
        return f"{ONE_BASE}{asset}" if asset else f"{ONE_BASE}/assets/{symbol_or_filename}.js"

    async def url_for_module_menu(self) -> str:
        """Get URL for module.menu asset."""
        m = await self.ensure_map()
        if not m.module_menu:
            raise KeyError("No module.menu asset found in index.")
        return f"{ONE_BASE}{m.module_menu}"
