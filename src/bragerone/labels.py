from __future__ import annotations
import logging
from typing import Callable, Dict, Optional

from .const import ONE_BASE

HttpGet = Callable[[str], "str | bytes"]

# NOTE: simple safe fallback resolver; parser WIP
POOL_NAMES_PL = {
    "P4":  "Sensors",
    "P5":  "Statuses",
    "P6":  "Boiler settings",
    "P7":  "P7",
    "P8":  "Login/Passwords",
    "P10": "Burner settings",
    "P11": "Hardware/Software",
    "P12": "Thermostats",
    "P17": "P17",
}

class LabelFetcher:
    def __init__(self, base_url: str = ONE_BASE, http_get: Optional[HttpGet] = None, logger: Optional[logging.Logger] = None):
        self.base_url = base_url.rstrip("/")
        self.http_get = http_get
        self.log = logger or logging.getLogger("bragerone.labels")

        # alias maps: "parameters.PARAM_7" -> {"pl":"Temperatura załączenia pomp", ...}
        self._alias_lang_map: Dict[str, Dict[str, str]] = {}
        # reverse map: ("P6", 7) -> "parameters.PARAM_7"
        self._param_alias: Dict[tuple[str, int], str] = {}

    # --- public API ---
    async def bootstrap(self, lang: str = "en"):
        """
        In the future: fetch index bundle(s), parse `parameters-*.js` assets, etc.
        For now: keep it no-op but safe, so logging works and nothing crashes.
        """
        # No-op parser (WIP). Keep your earlier dumps for the next step.
        return

    def count_vars(self) -> int:
        return len(self._param_alias)

    def count_langs(self) -> int:
        # count unique languages across all aliases
        langs = set()
        for d in self._alias_lang_map.values():
            langs.update(d.keys())
        return len(langs)

    def param_label(self, pool: str, num: int, lang: str = "en") -> Optional[str]:
        """
        Return human-readable label for (pool, num); if not known, fall back to None.
        """
        alias = self._param_alias.get((pool, num))
        if alias:
            tr = self._alias_lang_map.get(alias, {})
            # try requested lang
            if lang in tr and tr[lang]:
                return tr[lang]
            # try English
            if "en" in tr and tr["en"]:
                return tr["en"]
            # try Polish
            if "pl" in tr and tr["pl"]:
                return tr["pl"]
        return None

    def pool_human(self, pool: str, lang: str = "en") -> str:
        # simple fallback pool names
        return POOL_NAMES_PL.get(pool, pool)

    # --- helpers for Gateway ---
    def pretty(self, pool: str, var: str, lang: str = "en") -> str:
        num = None
        if var and var[:1] in ("v", "u", "s", "n", "x"):
            try:
                num = int(var[1:])
            except Exception:
                pass
        if num is not None:
            label = self.param_label(pool, num, lang)
            if label:
                return f"[{self.pool_human(pool, lang)}] {pool}.{var} – {label}"
            return f"[{self.pool_human(pool, lang)}] {pool}.{var}"
        return f"{pool}.{var}"

