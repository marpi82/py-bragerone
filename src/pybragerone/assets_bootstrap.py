from __future__ import annotations

import re
from typing import Any

from .assets_client import AssetClient
from .jsparse import parse_param_module, parse_parameter_labels, parse_units_js
from .param_catalog import ParamCatalog

PARAM_NAME_RE = re.compile(r"/assets/(?:no-lang/)?(PARAM_[A-Za-z0-9_]+)-[^/]*\.js$")
UNITS_RE = re.compile(r"/assets/.*/units-[A-Za-z0-9]+\.js$")
PARAMETERS_RE = re.compile(r"/assets/.*/parameters-[A-Za-z0-9]+\.js$")


async def build_catalog_from_frontend(base_url: str, lang: str = "pl") -> ParamCatalog:
    """
    Fetch minimal set of assets directly from the running frontend:
      - index-*.js (discover all chunks)
      - find one language pair: parameters-*.js + units-*.js for selected lang
      - collect all PARAM_*.js
    Parse and assemble into a ParamCatalog.
    """
    client = AssetClient(base_url)
    index_urls = await client.fetch_index_assets()
    if not index_urls:
        # If detection fails, try the canonical SPA path:
        index_urls = [f"{base_url.rstrip('/')}/assets/index.html"]
    # Fetch the HTML/JS shells and extract asset paths (loose heuristic: scan for "/assets/*.js")
    texts = await client.fetch_many(index_urls)
    js_paths: list[str] = []
    for _, txt in texts.items():
        js_paths.extend(re.findall(r'["\\\'](/assets/[^"\\\']+?\.js)["\\\']', txt))
    js_paths = sorted(set(js_paths))

    # Separate candidates
    lang_candidates = [p for p in js_paths if (lang + "/") in p]
    no_lang_candidates = [
        p for p in js_paths if "/no-lang/" in p or ("/assets/" in p and "/lang/" not in p)
    ]

    # Pick language files
    units_paths = [p for p in lang_candidates if UNITS_RE.search(p)]
    params_paths = [p for p in lang_candidates if PARAMETERS_RE.search(p)]
    if not units_paths or not params_paths:
        # As a fallback, keep scanning any referenced chunks we can reach (best-effort)
        pass

    # Also include all PARAM_*.js (usually in /assets/no-lang/ or just /assets/)
    param_paths = [p for p in no_lang_candidates if PARAM_NAME_RE.search(p)]

    # Fetch all
    fetch_all = sorted(set(units_paths + params_paths + param_paths))
    blobs = await client.fetch_many(fetch_all)

    # Parse
    # 1) units: first found
    units: dict[str, Any] = {}
    for p, txt in blobs.items():
        if UNITS_RE.search(p):
            try:
                units = parse_units_js(txt)
                break
            except Exception:
                continue

    # 2) labels: merge (some builds split them, we just use the first good hit)
    labels: dict[str, str] = {}
    alias_count_total = 0
    had_default_any = False
    for p, txt in blobs.items():
        if PARAMETERS_RE.search(p):
            m, alias_count, had_def = parse_parameter_labels(txt)
            labels.update(m)
            alias_count_total += alias_count
            had_default_any = had_default_any or had_def

    # 3) PARAM_* meta
    param_modules: list[tuple[str, dict[str, Any]]] = []
    for p, txt in blobs.items():
        m = PARAM_NAME_RE.search(p)
        if not m:
            continue
        logical = m.group(1)  # e.g. "PARAM_6" or "PARAM_P4_61" - we normalize later
        try:
            obj = parse_param_module(txt)
            param_modules.append((logical, obj))
        except Exception:
            # Some chunks may not match the default-object pattern; skip silently
            continue

    catalog = ParamCatalog.from_parts(units, labels, param_modules)
    return catalog
