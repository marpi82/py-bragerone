"""Module src/pybragerone/cli/parsers.py."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from ..api import BragerOneApiClient
from ..models.catalog import LiveAssetCatalog

default_path = Path("./dump")


async def dump_i18n(
    api: BragerOneApiClient, lang: str, out_dir: Path = default_path, namespaces: list[str] | None = None
) -> None:
    """Fetch and dump i18n JSON assets using the unified LiveAssetCatalog."""
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = LiveAssetCatalog(api)
    if namespaces is None:
        namespaces = ["parameters", "units"]
    for ns in namespaces:
        data: dict[str, Any] = await catalog.get_i18n(lang, ns)
        out_path = out_dir / f"{lang}_{ns}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


async def dump_param_mappings(
    api: BragerOneApiClient,
    filenames: list[str],
    out_dir: Path,
) -> None:
    """Fetch and dump parameter bundles (PARAM_*) using the unified catalog."""
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = LiveAssetCatalog(api)
    for name in filenames:
        data: dict[str, Any] = await catalog.get_param_mapping(name)
        out_path = out_dir / f"{name}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


async def dump_module_menu(
    api: BragerOneApiClient,
    out_path: Path,
) -> None:
    """Fetch and dump module.menu mapping using the unified catalog."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    catalog = LiveAssetCatalog(api)
    data: dict[str, Any] = await catalog.get_module_menu()
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def main_parsers_cli(
    api: BragerOneApiClient,
    lang: str,
    param_files: list[str],
    out_i18n: Path,
    out_params: Path,
    out_menu: Path | None = None,
) -> None:
    """Orchestrate all fetchers with shared session/base URL."""
    tasks = [
        dump_i18n(api, lang, out_i18n, namespaces=["parameters", "units"]),
        dump_param_mappings(api, param_files, out_params),
    ]
    if out_menu is not None:
        tasks.append(dump_module_menu(api, out_menu))
    await asyncio.gather(*tasks)


def main() -> int:
    """Main.

    Returns:
    TODO.
    """
    ap = argparse.ArgumentParser(prog="pybragerconnect-parsers", description="Debug CLI for pybragerconnect parsers")
    ap.add_argument("--i18n", help="path to i18n *.js (generic)")
    ap.add_argument("--i18n-parameters", help="path to parameters i18n *.js")
    ap.add_argument("--i18n-units", help="path to units i18n *.js")
    ap.add_argument("--bundle", help="path to param descriptor *.js (export default {...})")
    ap.add_argument("--menu", help="path to module.menu-*.js")
    ap.add_argument("--module-code", default="UNKNOWN")
    ap.add_argument("--out", default="-", help="output JSON ('-' = stdout)")
    args = ap.parse_args()

    api = BragerOneApiClient()

    out: dict[str, Any] = {}
    if args.i18n:
        out["i18n"] = dump_i18n(api=api, lang=args.i18n)
    if args.bundle:
        out["param_descriptors"] = dump_param_mappings(api=api, filenames=[args.bundle], out_dir=default_path)
    if args.menu:
        out["menu_tree"] = dump_module_menu(api=api, out_path=default_path / "module_menu.json")

    data = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(data)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
