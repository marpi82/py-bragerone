#!/usr/bin/env python3
"""Refresh gitignored ``tests/assets`` dumps from the live BragerOne CDN (auth)."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path

from pybragerone import BragerOneApiClient
from pybragerone.api.server import server_for
from pybragerone.models.catalog import LiveAssetsCatalog

_ASSETS = Path(__file__).resolve().parents[1] / "tests" / "assets"
_INDEX_RE = re.compile(r"index-[A-Za-z0-9_-]+\.js")
_CAPTURE_SUBDIRS = ("index", "params", "menus")


def _write_bytes(path: Path, payload: bytes) -> None:
    """Create parents and write *payload* to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _mkdtemp_on_assets() -> str:
    """Create a temp directory on the same filesystem as ``tests/assets``."""
    _ASSETS.mkdir(parents=True, exist_ok=True)
    return tempfile.mkdtemp(prefix="pybo-assets-", dir=str(_ASSETS))


def _rmtree(path: Path) -> None:
    """Recursively remove *path* if it exists."""
    if path.exists():
        shutil.rmtree(path)


def _promote_staged_captures(*, staged: Path) -> None:
    """Replace capture directories by renaming staged siblings into place.

    Staging lives under ``tests/assets`` so ``Path.replace`` is same-filesystem
    atomic. Previous captures are only removed after the new directory is in place.
    """
    for subdir in _CAPTURE_SUBDIRS:
        src = staged / subdir
        dst = _ASSETS / subdir
        backup = _ASSETS / f".{subdir}.bak"
        _rmtree(backup)
        if not src.is_dir():
            # Keep the previous directory when this refresh did not stage one.
            continue
        if dst.exists():
            dst.replace(backup)
        src.replace(dst)
        _rmtree(backup)


async def main() -> int:
    """Download current index / param / menu JS dumps into ``tests/assets``."""
    email = os.environ["PYBO_EMAIL"].strip()
    password = os.environ["PYBO_PASSWORD"].strip()
    platform = os.environ.get("PYBO_PLATFORM", "bragerone").strip() or "bragerone"
    client = BragerOneApiClient(server=server_for(platform), creds_provider=lambda: (email, password), validate_on_start=False)
    staged_root: Path | None = None
    try:
        await client.ensure_auth(email, password)
        catalog = LiveAssetsCatalog(client)
        await catalog._ensure_index_loaded()
        index_url = catalog._last_index_url or ""
        index_name = Path(index_url).name if index_url else "index-unknown.js"
        if not _INDEX_RE.fullmatch(index_name):
            raise SystemExit(f"unexpected index asset name: {index_name!r}")
        index_bytes = catalog._idx.index_bytes or b""
        if not index_bytes:
            raise SystemExit("index bytes unavailable; refusing to clear captured assets")

        staged_root = Path(await asyncio.to_thread(_mkdtemp_on_assets))
        staged_index = staged_root / "index"
        staged_params = staged_root / "params"
        staged_menus = staged_root / "menus"

        await asyncio.to_thread(_write_bytes, staged_index / index_name, index_bytes)
        print(f"staged {index_name} ({len(index_bytes)} bytes)")

        # Representative mapped params + STATUS samples (skip tokens without dedicated assets).
        wanted = ["PARAM_66", "STATUS_BAR_PUMP", "STATUS_P5_0", "STATUS_P5_22", "STATUS_P5_81"]
        for token in wanted:
            asset = catalog._idx.find_asset_for_basename(token)
            if asset is None:
                print(f"skip missing asset basename={token}")
                continue
            code = await client.get_bytes(asset.url)
            out = staged_params / f"{asset.base}-{asset.hash}.js"
            await asyncio.to_thread(_write_bytes, out, code)
            print(f"staged {out.name} ({len(code)} bytes)")

        # Prefer the hashed menu id from menu_map (basename "0" can collide with other chunks).
        menu_id = catalog._idx.menu_map.get(0)
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
            out = staged_menus / f"{menu_asset.base}-{menu_asset.hash}.js"
            await asyncio.to_thread(_write_bytes, out, code)
            print(f"staged {out.name} ({len(code)} bytes)")
        else:
            print(f"skip menu asset (menu_id={menu_id!r})")

        await asyncio.to_thread(_promote_staged_captures, staged=staged_root)
        print(f"fingerprint index={index_name}")
    finally:
        await client.close()
        if staged_root is not None:
            await asyncio.to_thread(_rmtree, staged_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
