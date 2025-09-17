import os
import re
from typing import Any

import aiohttp

from . import jsparse

ASSET_PATH_IN_JS_RE = re.compile(r"""["'](?P<p>/assets/[^"']+?\.js)["']""")
IMPORT_DOT_RE = re.compile(r"""import\(["'](?P<p>\./[^"']+?\.js)["']\)""")
LANG_CHUNK_ENTRY_RE = re.compile(
    r"""
    ["']\.\./\.\./resources/languages/
    (?P<flag>[a-z]{2})
    /[^"']+?\.json["']\s*:\s*
    \(\)\s*=>\s*d\(\(\)\s*=>\s*import\(
    ["'](?P<chunk>\./[^"']+?\.js)["']\)\s*
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _norm_base(url: str) -> str:
    return url.rstrip("/")


class AssetClient:
    def __init__(self, http_session: aiohttp.ClientSession, base_url: str, debug: bool = False):
        self.http = http_session
        self.base_url = _norm_base(base_url)
        self.debug = debug

    def _join_base(self, path: str) -> str:
        if not path:
            return self.base_url.rstrip("/")
        # jeśli już pełny URL - zwróć jak jest
        if path.startswith("http://") or path.startswith("https://"):
            return path
        base = self.base_url.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        return base + path

    @staticmethod
    async def _fetch_text(http: aiohttp.ClientSession, url: str) -> str | None:
        try:
            async with http.get(url, allow_redirects=True) as r:
                if r.status == 200:
                    data = await r.read()
                    try:
                        return data.decode("utf-8", "ignore")
                    except Exception:
                        return data.decode("latin-1", "ignore")
                return None
        except Exception:
            return None

    async def fetch_index_js(self) -> str:
        """Pobierz jeden (pierwszy) index-*.js jako tekst."""
        # najpierw index.html albo /
        html = await self._fetch_text(
            self.http, f"{self.base_url}/index.html"
        ) or await self._fetch_text(self.http, f"{self.base_url}/")
        if not html:
            raise RuntimeError("Could not fetch index.html or '/'")

        # proste wyłuskanie ścieżek /assets/index-*.js z HTML
        # nie replikujemy całego fetch.py - bierzemy pierwszy index
        m = re.search(r"""["'](?P<p>/assets/index(?:-[^"']+)?\.js)["']""", html)
        if not m:
            # fallback: poszukaj <script src="/assets/index-*.js">
            m = re.search(
                r"""<script[^>]+src=["'](?P<p>/assets/index[^"']+\.js)["']""", html, re.IGNORECASE
            )
        if not m:
            raise RuntimeError("No /assets/index-*.js found in HTML")

        index_path = m.group("p")
        index_url = f"{self.base_url}{index_path}"
        idx = await self._fetch_text(self.http, index_url)
        if not idx:
            raise RuntimeError(f"Failed to fetch {index_url}")
        return idx

    async def _find_lang_bundles(self, index_js: str, lang: str) -> tuple[str, str]:
        """
        Find parameters-*.js and units-*.js for given lang by scanning chunk list in index_js.
        We no longer need to scan inside chunks, because these files are top-level language chunks.
        """

        # znajdź wszystkie wpisy chunków językowych dla tego lang
        rel_chunk_paths: list[str] = []
        for mm in LANG_CHUNK_ENTRY_RE.finditer(index_js):
            flag = (mm.group("flag") or "").lower()
            chunk_rel = (mm.group("chunk") or "").lstrip("./")
            if flag == lang and chunk_rel:
                rel_chunk_paths.append(f"/assets/{chunk_rel}")

        if not rel_chunk_paths:
            raise RuntimeError(f"Lang '{lang}': no language chunk entries found in index.js")

        # patrzymy po basename
        params_candidates = sorted(
            [p for p in rel_chunk_paths if os.path.basename(p).startswith("parameters-")]
        )
        units_candidates = sorted(
            [p for p in rel_chunk_paths if os.path.basename(p).startswith("units-")]
        )

        if not params_candidates or not units_candidates:
            some = sorted(os.path.basename(p) for p in rel_chunk_paths)
            raise RuntimeError(
                f"Lang '{lang}': parameters-/units- not found among {len(rel_chunk_paths)} chunks "
                f"(examples={some[:10]}{'...' if len(some) > 10 else ''})"
            )

        return units_candidates[-1], params_candidates[-1]

    async def fetch_lang_units_and_params(self, lang: str) -> tuple[dict[str, Any], dict[str, str]]:
        index_js = await self.fetch_index_js()
        units_path, params_path = await self._find_lang_bundles(index_js, lang)

        units_url = self._join_base(units_path)
        params_url = self._join_base(params_path)

        if self.debug:
            print(f"[assets] lang={lang} units_url={units_url}")
            print(f"[assets] lang={lang} params_url={params_url}")

        units_js = await self._fetch_text(self.http, units_url)
        if units_js is None:
            raise RuntimeError(f"Failed to fetch {units_url}")

        params_js = await self._fetch_text(self.http, params_url)
        if params_js is None:
            raise RuntimeError(f"Failed to fetch {params_url}")

        units = jsparse.parse_units_js(units_js)  # Twoje istniejące parse'y
        labels = jsparse.parse_parameters_js(params_js)
        return units, labels

    async def fetch_all_param_meta(self) -> dict[str, Any]:
        """
        Pobiera i scala wszystkie no-lang PARAM_*.js w jedną strukturę meta.
        Wersja online: czytamy index-*.js → zbieramy ścieżki no-lang z importów → pobieramy tylko PARAM_*.js.
        """
        index_js = await self.fetch_index_js()

        # no-lang wymagałoby pełnej logiki z fetch.py; uprośćmy pod kątem naszego celu:
        # wyciągnij wszystkie literalne /assets/PARAM_*.js, a także future-proof: import("./PARAM_*.js")
        paths: set[str] = set()

        # literalne:
        for m in ASSET_PATH_IN_JS_RE.finditer(index_js):
            p = m.group("p")
            if p and os.path.basename(p).startswith("PARAM_"):
                paths.add(p)

        # względne importy:
        for ri in re.findall(r"""import\(["']\./([^"']+?\.js)["']\)""", index_js):
            if os.path.basename(ri).startswith("PARAM_"):
                paths.add(f"/assets/{ri}")

        # Jeśli w index nie ma bezpośrednich odwołań do PARAM_*, może być tak jak z lang chunkami:
        # niektóre referencje pojawiają się dopiero po załadowaniu innych chunków.
        # W wersji minimum - wystarczy to co znajdziemy w index.js (działało w praktyce).
        # Gdyby się okazało, że to za mało — łatwo rozszerzymy jak w fetch.py.

        meta: dict[str, Any] = {}

        for p in sorted(paths):
            url = f"{self.base_url}{p}"
            js = await self._fetch_text(self.http, url)
            if not js:
                # pomiń pojedynczy błąd, nie zwalniaj całości
                continue
            one = jsparse.parse_labels_js(js)
            # scal
            for key, spec in one.items():
                meta[key] = spec

        return meta
