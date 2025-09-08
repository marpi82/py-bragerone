# labels.py
from __future__ import annotations
import re
from typing import Callable, Dict, Optional, List
import html

ONE_BASE = "https://one.brager.pl"

class LabelFetcher:
    def __init__(self, base_url: str, http_get: Callable[[str], "awaitable[str]"]):
        self.base = base_url.rstrip("/")
        self._get = http_get
        # aliasy paramów:  ("P6",7) -> "PARAM_7" -> "Tc" (alias), trzymamy bezpośrednio num->alias
        self._param_alias: Dict[int, str] = {}
        # alias -> tekst (z różnych bundle)
        self._alias_lang_map: Dict[str, str] = {}
        # cache zawartości assetów:
        self._assets_index: List[str] = []

    async def bootstrap(self, lang: str = "pl"):
        # 1) pobierz index
        html_index = await self._get(f"{self.base}/")
        paths = re.findall(r'href="(/assets/[^"]+\.js)"', html_index)
        self._assets_index = list(dict.fromkeys(paths))  # dedupe

        # 2) wybierz kandydatów parameters*.js (preferencyjnie z sufiksem języka)
        params_candidates = self._filter_params_files(lang)
        if not params_candidates:
            # fallback: wszystkie parameters*.js
            params_candidates = [p for p in self._assets_index if "/assets/parameters" in p]

        # 3) przeparsuj aż uzyskamy mapy
        for p in params_candidates:
            try:
                js = await self._get(f"{self.base}{p}")
            except Exception:
                continue
            # wyciągnij PARAM_<n> -> alias
            self._merge_param_aliases(js)
            # wyciągnij alias -> string
            self._merge_alias_strings(js)

    def _filter_params_files(self, lang: str) -> List[str]:
        lang = (lang or "en").lower()
        # priorytet: …parameters-<coś>-<lang>.js  albo …parameters-<lang>*.js
        preferred = []
        generic = []
        for p in self._assets_index:
            if "/assets/parameters" not in p:
                continue
            if f"-{lang}." in p or f"_{lang}." in p:
                preferred.append(p)
            else:
                generic.append(p)
        return preferred + generic

    def _merge_param_aliases(self, js: str):
        # wzorzec:  PARAM_7: Tc   albo  "PARAM_7":Tc  (po minifikacji)
        for m in re.finditer(r'PARAM_(\d+)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)', js):
            num = int(m.group(1))
            alias = m.group(2)
            self._param_alias[num] = alias

    def _merge_alias_strings(self, js: str):
        # wzorzec:  Tc="Temperatura załączenia pomp" lub Tc='...'
        for m in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*("([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\')', js):
            alias = m.group(1)
            raw = m.group(2)
            text = self._unescape_js_string(raw)
            # pominij oczywiste nie-teksty (np. import aliasów)
            if 1 <= len(text) <= 200 and not text.startswith("./") and not text.endswith(".js"):
                self._alias_lang_map[alias] = text

    def _unescape_js_string(self, s: str) -> str:
        # s zawiera cudzysłowy, np.  "Ala ma \u0105"
        if s and s[0] in ('"', "'") and s[-1] == s[0]:
            s = s[1:-1]
        # \uXXXX
        def uni(m):
            try:
                return chr(int(m.group(1), 16))
            except Exception:
                return m.group(0)
        s = re.sub(r'\\u([0-9a-fA-F]{4})', uni, s)
        # sekwencje prostsze
        s = s.replace(r'\"', '"').replace(r"\'", "'").replace(r"\\", "\\").replace(r"\n", "\n").replace(r"\t", "\t")
        # HTML na wszelki wypadek
        s = html.unescape(s)
        return s

    def param_label(self, pool: str, number: int, lang: str = "pl") -> Optional[str]:
        """
        Zwraca przyjazną nazwę dla P?.v<number>, korzystając z:
         parameters.PARAM_<number> -> alias -> właściwy string.
        """
        # dziś ignorujemy pool w etykiecie (PARAM_<n> jest wspólny)
        alias = self._param_alias.get(number)
        if not alias:
            return None
        txt = self._alias_lang_map.get(alias)
        return txt
