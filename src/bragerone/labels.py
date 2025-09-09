from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "bragerone")


@dataclass
class LabelStore:
    # alias → label for given language (e.g. "parameters.PARAM_7" → "Pump activation temperature")
    aliases: Dict[str, str] = field(default_factory=dict)
    # (pool:number) → alias  (e.g. "P6:7" → "parameters.PARAM_7")
    param_alias: Dict[str, str] = field(default_factory=dict)
    # (pool:number) → unit_id (optional, numeric or string id coming from 'u' field)
    param_unit_id: Dict[str, str] = field(default_factory=dict)
    # unit_id → unit label (e.g. "0" → "°C")
    unit_labels: Dict[str, str] = field(default_factory=dict)
    # unit_id → {value → label} for enums (e.g. "6" → {"11":"Return protection", ...})
    enums: Dict[str, Dict[str, str]] = field(default_factory=dict)


class LabelFetcher:
    """
    v1: lazy + cache only (no network fetch yet).
    You can enrich the cache via touch_* helpers (used by CLI/tools/tests).
    """

    def __init__(self) -> None:
        self._by_lang: Dict[str, LabelStore] = {}

    # ---------- public API ----------

    def bootstrap(self, lang: str) -> None:
        """Ensure cache presence for a language (lazy load)."""
        self.ensure(lang)

    def ensure(self, lang: str) -> None:
        if lang in self._by_lang:
            return
        self._by_lang[lang] = self._load_cache(lang)

    def count_vars(self) -> int:
        return sum(len(st.param_alias) for st in self._by_lang.values())

    def count_langs(self) -> int:
        return len(self._by_lang)

    # --- lookups ---

    def get_param_label(self, pool: str, number: int, lang: str) -> str:
        self.ensure(lang)
        key = f"{pool}:{number}"
        st = self._by_lang[lang]
        alias = st.param_alias.get(key)
        if not alias:
            return ""
        return st.aliases.get(alias, "")

    def get_param_unit_id(self, pool: str, number: int, lang: str) -> str:
        self.ensure(lang)
        key = f"{pool}:{number}"
        st = self._by_lang[lang]
        return st.param_unit_id.get(key, "")

    def get_unit_label(self, unit_id: str, lang: str) -> str:
        self.ensure(lang)
        st = self._by_lang[lang]
        return st.unit_labels.get(str(unit_id), "")

    def get_enum_label(self, unit_id: str, value: Any, lang: str) -> str:
        self.ensure(lang)
        st = self._by_lang[lang]
        enum_map = st.enums.get(str(unit_id)) or {}
        return enum_map.get(str(value), "")

    # --- enrichment helpers (used by tool/CLI/tests) ---

    def touch_param_alias(self, pool: str, number: int, alias: str, *, lang: str | None = None) -> None:
        for l in ([lang] if lang else (list(self._by_lang.keys()) or ["en"])):
            self.ensure(l)
            self._by_lang[l].param_alias[f"{pool}:{number}"] = alias
            self._save_cache(l)

    def touch_alias(self, alias: str, label: str, *, lang: str) -> None:
        self.ensure(lang)
        st = self._by_lang[lang]
        st.aliases[alias] = label
        self._save_cache(lang)

    def touch_param_unit(self, pool: str, number: int, unit_id: str | int, *, lang: str | None = None) -> None:
        uid = str(unit_id)
        for l in ([lang] if lang else (list(self._by_lang.keys()) or ["en"])):
            self.ensure(l)
            self._by_lang[l].param_unit_id[f"{pool}:{number}"] = uid
            self._save_cache(l)

    def touch_unit_label(self, unit_id: str | int, unit_label: str, *, lang: str) -> None:
        self.ensure(lang)
        self._by_lang[lang].unit_labels[str(unit_id)] = unit_label
        self._save_cache(lang)

    def touch_enum_map(self, unit_id: str | int, mapping: Dict[str, str] | Dict[int, str], *, lang: str) -> None:
        self.ensure(lang)
        # Normalize keys to strings
        norm = {str(k): v for k, v in dict(mapping).items()}
        self._by_lang[lang].enums[str(unit_id)] = norm
        self._save_cache(lang)

    # ---------- disk cache ----------

    def _cache_path(self, lang: str) -> str:
        os.makedirs(CACHE_DIR, exist_ok=True)
        return os.path.join(CACHE_DIR, f"labels-{lang}.json")

    def _load_cache(self, lang: str) -> LabelStore:
        p = self._cache_path(lang)
        if not os.path.exists(p):
            return LabelStore()
        try:
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)
            st = LabelStore()
            st.aliases = obj.get("aliases", {})
            st.param_alias = obj.get("param_alias", {})
            st.param_unit_id = obj.get("param_unit_id", {})
            st.unit_labels = obj.get("unit_labels", {})
            st.enums = obj.get("enums", {})
            return st
        except Exception:
            return LabelStore()

    def _save_cache(self, lang: str) -> None:
        p = self._cache_path(lang)
        st = self._by_lang.get(lang)
        if not st:
            return
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "aliases": st.aliases,
                        "param_alias": st.param_alias,
                        "param_unit_id": st.param_unit_id,
                        "unit_labels": st.unit_labels,
                        "enums": st.enums,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass


# ---------- value formatting helper (used by Gateway/CLI) ----------

def _parse_num_from_var(var: str) -> Optional[int]:
    if not var:
        return None
    if var[0] in ("v", "n", "x", "u", "s"):
        try:
            return int(var[1:])
        except Exception:
            return None
    return None


def format_value(pool: str, var: str, value: Any, lf: LabelFetcher, lang: str) -> str:
    """
    Pretty-print a value with either enum label (if unit_id has enum) or with unit suffix.
    Falls back to raw value if nothing is known.
    """
    num = _parse_num_from_var(var)
    if num is None:
        return f"{value}"

    unit_id = lf.get_param_unit_id(pool, num, lang)
    if unit_id:
        enum_label = lf.get_enum_label(unit_id, value, lang)
        if enum_label:
            return enum_label
        unit_label = lf.get_unit_label(unit_id, lang)
        if unit_label:
            return f"{value}{unit_label if unit_label.startswith(' ') else ' ' + unit_label}"

    return f"{value}"

