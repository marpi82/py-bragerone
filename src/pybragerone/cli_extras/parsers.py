"""Module src/pybragerone/cli/parsers.py."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from aiohttp import ClientSession

from ..models.catalog import LiveAssetCatalog


async def dump_i18n(
    base_url: str,
    session: ClientSession,
    lang: str,
    out_dir: Path,
    namespaces: list[str] = ("parameters", "units"),
) -> None:
    """Fetch and dump i18n JSON assets using the unified LiveAssetCatalog."""
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = LiveAssetCatalog(base_url, session)
    for ns in namespaces:
        data: dict[str, Any] = await catalog.get_i18n(lang, ns)
        out_path = out_dir / f"{lang}_{ns}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


async def dump_param_mappings(
    base_url: str,
    session: ClientSession,
    filenames: list[str],
    out_dir: Path,
) -> None:
    """Fetch and dump parameter bundles (PARAM_*) using the unified catalog."""
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = LiveAssetCatalog(base_url, session)
    for name in filenames:
        data: dict[str, Any] = await catalog.get_param_mapping(name)
        out_path = out_dir / f"{name}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


async def dump_module_menu(
    base_url: str,
    session: ClientSession,
    out_path: Path,
) -> None:
    """Fetch and dump module.menu mapping using the unified catalog."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    catalog = LiveAssetCatalog(base_url, session)
    data: dict[str, Any] = await catalog.get_module_menu()
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def main_parsers_cli(
    base_url: str,
    session: ClientSession,
    lang: str,
    param_files: list[str],
    out_i18n: Path,
    out_params: Path,
    out_menu: Path | None = None,
) -> None:
    """Orchestrate all fetchers with shared session/base URL."""
    tasks = [
        dump_i18n(base_url, session, lang, out_i18n, namespaces=["parameters", "units"]),
        dump_param_mappings(base_url, session, param_files, out_params),
    ]
    if out_menu is not None:
        tasks.append(dump_module_menu(base_url, session, out_menu))
    await asyncio.gather(*tasks)

def main() -> int:
    """Main.

    Returns:
    TODO.
    """
    ap = argparse.ArgumentParser(prog="pybragerconnect-parsers",
        description="Debug CLI for pybragerconnect parsers")
    ap.add_argument("--i18n", help="path to i18n *.js (generic)")
    ap.add_argument("--i18n-parameters", help="path to parameters i18n *.js")
    ap.add_argument("--i18n-units", help="path to units i18n *.js")
    ap.add_argument("--bundle", help="path to param descriptor *.js (export default {...})")
    ap.add_argument("--menu", help="path to module.menu-*.js")
    ap.add_argument("--module-code", default="UNKNOWN")
    ap.add_argument("--out", default="-", help="output JSON ('-' = stdout)")
    args = ap.parse_args()

    out: dict = {}
    if args.i18n:
        out["i18n"] = load_i18n_generic(open(args.i18n, encoding="utf-8").read())
    if args.bundle:
        out["param_descriptors"] = {k: v.model_dump() for k, v in parse_param_descriptors(open(args.bundle, encoding="utf-8").read()).items()}
    if args.menu:
        out["menu_tree"] = parse_module_menu(open(args.menu, encoding="utf-8").read(), args.module_code).model_dump()

    data = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(data)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(data)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
