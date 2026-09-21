#!/usr/bin/env python3
"""Classify panel tokens that lack ParamMap (live diagnostic for mapped regression)."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from pybragerone import BragerOneApiClient
from pybragerone.api.server import server_for
from pybragerone.models.catalog import _HELPER_TOKEN_RE, LiveAssetsCatalog
from pybragerone.models.param import ParamStore
from pybragerone.models.param_resolver import ParamResolver

_PUBLIC = re.compile(r"^(?:PARAM|STATUS)_[A-Z0-9_]+$")
_LEFTOVER_HINT = re.compile(r"\(|\[|\]|\)")


def _classify(token: str, *, has_asset: bool) -> str:
    if _PUBLIC.fullmatch(token):
        return "public_with_asset" if has_asset else "public_no_asset"
    if _LEFTOVER_HINT.search(token) or "map" in token.casefold():
        return "leftover_call"
    if token.startswith(("P0_", "P1_", "P2_", "P3_", "P4_", "P5_", "P6_", "P7_", "P8_", "P9_")):
        return "overlay_p_prefix"
    if _HELPER_TOKEN_RE.search(token):
        return "embedded_public_token"
    return "other"


async def main() -> int:
    """Classify live panel tokens that lack ParamMap and write a JSON report."""
    email = os.environ["PYBO_EMAIL"].strip()
    password = os.environ["PYBO_PASSWORD"].strip()
    object_id = int(os.environ["PYBO_OBJECT_ID"])
    modules = [m.strip() for m in os.environ.get("PYBO_MODULES", "").split(",") if m.strip()]
    lang = os.environ.get("PYBO_LANG", "en").strip() or "en"
    platform = os.environ.get("PYBO_PLATFORM", "bragerone").strip() or "bragerone"

    client = BragerOneApiClient(server=server_for(platform), creds_provider=lambda: (email, password), validate_on_start=False)
    report: dict[str, object] = {}
    try:
        await client.ensure_auth(email, password)
        catalog = LiveAssetsCatalog(client)
        mods = await client.get_modules(object_id)
        if modules:
            wanted = set(modules)
            mods = [m for m in mods if str(m.devid) in wanted]
        if not mods:
            raise SystemExit("no modules")

        await catalog._ensure_index_loaded()
        basenames = set(catalog._idx.assets_by_basename.keys())

        all_unmapped: list[dict[str, object]] = []
        counts = Counter()
        for mod in mods:
            devid = str(mod.devid)
            store = ParamStore()
            status, data = await client.modules_parameters_prime([devid], return_data=True)  # type: ignore[misc]
            if status not in (200, 204) or not isinstance(data, dict):
                raise RuntimeError(f"prime failed for {devid}: {status}")
            store.ingest_prime_payload(data)
            flat = store.flatten_for_devid(devid)
            resolver = ParamResolver(store=store, assets=catalog, lang=lang)
            perms = [str(p) for p in (getattr(mod, "permissions", None) or [])]
            groups = await resolver.build_panel_groups(
                device_menu=int(mod.deviceMenu),
                permissions=perms,
                all_panels=True,
                web_ui_only=False,
                flat_values=flat,
            )
            symbols = sorted({sym for group in groups.values() for sym in group})
            descriptions = await resolver.describe_symbols(symbols)
            unmapped = [
                s for s in symbols if not isinstance(descriptions.get(s), Mapping) or descriptions[s].get("mapping") is None
            ]
            for token in unmapped:
                has_asset = token in basenames
                kind = _classify(token, has_asset=has_asset)
                counts[kind] += 1
                all_unmapped.append({"devid": devid, "token": token, "kind": kind, "has_asset": has_asset})

            report[devid] = {
                "device_menu": int(mod.deviceMenu),
                "symbols": len(symbols),
                "mapped": len(symbols) - len(unmapped),
                "unmapped": len(unmapped),
                "panel_groups": len(groups),
            }

        samples: dict[str, list[str]] = {}
        for row in all_unmapped:
            kind = str(row["kind"])
            samples.setdefault(kind, [])
            if len(samples[kind]) < 25:
                samples[kind].append(str(row["token"]))

        out = {
            "modules": report,
            "unmapped_counts_by_kind": dict(counts),
            "unmapped_total": len(all_unmapped),
            "samples_by_kind": samples,
            "basename_count": len(basenames),
        }
        out_path = Path("reports/live/unmapped_panel_tokens.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"wrote {out_path}", file=sys.stderr)
    finally:
        await client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
