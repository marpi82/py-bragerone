#!/usr/bin/env python3
"""Refresh gitignored ``tests/assets`` dumps from the live BragerOne CDN (auth)."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from pybragerone import BragerOneApiClient
from pybragerone.api.server import server_for
from pybragerone.models.catalog import LiveAssetsCatalog

_ASSETS = Path(__file__).resolve().parents[1] / "tests" / "assets"
_INDEX_RE = re.compile(r"index-[A-Za-z0-9_-]+\.js")


async def main() -> int:
    """Download current index / param / menu JS dumps into ``tests/assets``."""
    email = os.environ["PYBO_EMAIL"].strip()
    password = os.environ["PYBO_PASSWORD"].strip()
    platform = os.environ.get("PYBO_PLATFORM", "bragerone").strip() or "bragerone"
    client = BragerOneApiClient(server=server_for(platform), creds_provider=lambda: (email, password), validate_on_start=False)
    try:
        await client.ensure_auth(email, password)
        catalog = LiveAssetsCatalog(client)
        await catalog._ensure_index_loaded()
        index_url = catalog._last_index_url or ""
        index_name = Path(index_url).name if index_url else "index-unknown.js"
        if not _INDEX_RE.fullmatch(index_name):
            raise SystemExit(f"unexpected index asset name: {index_name!r}")

        index_dir = _ASSETS / "index"
        params_dir = _ASSETS / "params"
        menus_dir = _ASSETS / "menus"
        for folder in (index_dir, params_dir, menus_dir):
            folder.mkdir(parents=True, exist_ok=True)

        # Clear previous dumps so captured tests exercise only the new fingerprint.
        for folder in (index_dir, params_dir, menus_dir):
            for old in folder.glob("*.js"):
                old.unlink()

        index_bytes = catalog._idx.index_bytes or b""
        (index_dir / index_name).write_bytes(index_bytes)
        print(f"wrote {index_dir / index_name} ({len(index_bytes)} bytes)")

        # Representative mapped params + STATUS samples (skip tokens without dedicated assets).
        wanted = ["PARAM_66", "STATUS_BAR_PUMP", "STATUS_P5_0", "STATUS_P5_22", "STATUS_P5_81"]
        for token in wanted:
            asset = catalog._idx.find_asset_for_basename(token)
            if asset is None:
                print(f"skip missing asset basename={token}")
                continue
            code = await client.get_bytes(asset.url)
            out = params_dir / f"{asset.base}-{asset.hash}.js"
            out.write_bytes(code)
            print(f"wrote {out.name} ({len(code)} bytes)")

        # Prefer the hashed menu id from menu_map (basename "0" can collide with other chunks).
        menu_id = catalog._idx.menu_map.get(0) or catalog._idx.menu_map.get("0")
        menu_asset = None
        if isinstance(menu_id, str) and menu_id:
            for refs in catalog._idx.assets_by_basename.values():
                for ref in refs:
                    if f"{ref.base}-{ref.hash}" == menu_id:
                        menu_asset = ref
                        break
                if menu_asset is not None:
                    break
        if menu_asset is None:
            menu_asset = catalog._idx.find_asset_for_basename("module.menu")
        if menu_asset is not None:
            code = await client.get_bytes(menu_asset.url)
            out = menus_dir / f"{menu_asset.base}-{menu_asset.hash}.js"
            out.write_bytes(code)
            print(f"wrote {out.name} ({len(code)} bytes)")
        else:
            print(f"skip menu asset (menu_id={menu_id!r})")

        print(f"fingerprint index={index_name}")
    finally:
        await client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
