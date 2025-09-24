from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, Optional
from aiohttp import ClientSession

@dataclass(slots=True)
class IndexMap:
    i18n: Dict[str, str]
    parameters: Dict[str, str]
    module_menu: Optional[str] = None

class IndexResolver:
    """Resolve asset URLs by scanning index*.js for dynamic import maps."""
    def __init__(self, base_url: str, session: ClientSession) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session
        self._cached: Optional[IndexMap] = None

    async def _fetch_index_text(self) -> str:
        # Try a few common entry points
        for path in ("/assets/index.js", "/assets/index.mjs", "/"):
            async with self.session.get(f"{self.base_url}{path}") as r:
                if r.status == 200:
                    return await r.text()
        raise RuntimeError("Could not fetch index to resolve assets.")

    @staticmethod
    def _parse_index(text: str) -> IndexMap:
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
        if self._cached is None:
            self._cached = self._parse_index(await self._fetch_index_text())
        return self._cached

    async def url_for_i18n(self, lang: str, namespace: str) -> str:
        m = await self.ensure_map()
        key = f"resources/languages/{lang}/{namespace}.json"
        asset = m.i18n.get(key)
        if not asset:
            raise KeyError(f"No i18n asset for {key}")
        return f"{self.base_url}{asset}"

    async def url_for_param(self, symbol_or_filename: str) -> str:
        m = await self.ensure_map()
        asset = m.parameters.get(symbol_or_filename)
        return f"{self.base_url}{asset}" if asset else f"{self.base_url}/assets/{symbol_or_filename}.js"

    async def url_for_module_menu(self) -> str:
        m = await self.ensure_map()
        if not m.module_menu:
            raise KeyError("No module.menu asset found in index.")
        return f"{self.base_url}{m.module_menu}"
