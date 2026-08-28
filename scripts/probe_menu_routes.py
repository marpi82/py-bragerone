"""Probe live module menu routes and panel inclusion diagnostics (marpi82/ha-bragerone#192).

Logs into BragerOne with ``PYBO_*`` credentials, primes parameters, and dumps
per-route diagnostics for ``build_panel_groups`` / ``panel_route_diagnostics``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from pybragerone import BragerOneApiClient
from pybragerone.api.server import Platform, server_for
from pybragerone.models.catalog import LiveAssetsCatalog
from pybragerone.models.param import ParamStore
from pybragerone.models.param_resolver import ParamResolver

_ROUTE_FILTER_RE = re.compile(
    r"strefy|czasow|schedule|timezone|time.?zone|MAINMENU",
    re.IGNORECASE,
)


def _maybe_load_dotenv() -> None:
    """Load ``.env`` from the current working directory when python-dotenv is installed."""
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)


def parse_modules(raw: str | None) -> list[str]:
    """Split a comma-separated module filter into sorted unique codes."""
    if not raw:
        return []
    return sorted({part.strip() for part in raw.split(",") if part.strip()})


def require_env(name: str) -> str:
    """Return a non-empty environment variable or exit."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing {name}: set it in .env or process env.")
    return value


def _route_row(
    route: Any,
    *,
    ancestors: tuple[Any, ...],
    routes_i18n: dict[str, Any],
    static_route_symbols: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable route summary for probe output."""
    title = ParamResolver._route_title(route, routes_i18n=routes_i18n)
    panel_title = ParamResolver._panel_title_hierarchical(
        route=route,
        ancestors=ancestors,
        routes_i18n=routes_i18n,
    )
    name = str(getattr(route, "name", "") or "")
    path = str(getattr(route, "path", "") or "")
    component = getattr(route, "component", None)
    meta = getattr(route, "meta", None)
    side = getattr(meta, "is_visible_on_side_menu", None) if meta is not None else None
    dropdown = getattr(meta, "display_dropdown", None) if meta is not None else None
    symbols = sorted(ParamResolver._resolve_route_symbols(route, static_route_symbols=static_route_symbols))
    shell = ParamResolver._route_is_panel_shell(route, static_route_symbols=static_route_symbols)
    return {
        "title": title,
        "panel_title": panel_title,
        "name": name,
        "path": path,
        "component": str(component) if component is not None else None,
        "is_visible_on_side_menu": side,
        "display_dropdown": dropdown,
        "symbol_count": len(symbols),
        "symbols": symbols,
        "panel_shell": shell,
        "module_item": ParamResolver._route_allowed_in_module_item(route),
        "web_ui": ParamResolver._route_is_end_user_web_ui(route, ancestors=ancestors),
    }


def _matches_filter(row: dict[str, Any], *, filter_re: re.Pattern[str] | None) -> bool:
    """Return whether a route row matches the optional title/name filter."""
    if filter_re is None:
        return True
    blob = " ".join(str(row.get(key) or "") for key in ("title", "panel_title", "name", "path", "component"))
    return filter_re.search(blob) is not None


async def probe(
    *,
    email: str,
    password: str,
    object_id: int,
    modules: list[str],
    lang: str,
    platform: str,
    filter_text: str | None,
    capture_dir: Path | None,
) -> dict[str, Any]:
    """Authenticate and return per-module menu route probe payload."""
    server = server_for(platform)
    client = BragerOneApiClient(server=server, creds_provider=lambda: (email, password), validate_on_start=False)
    filter_re = re.compile(filter_text, re.IGNORECASE) if filter_text else _ROUTE_FILTER_RE

    try:
        await client.ensure_auth(email, password)
        catalog = LiveAssetsCatalog(client)

        mods = await client.get_modules(object_id)
        if not mods:
            raise SystemExit("get_modules returned no modules for this object.")

        if modules:
            wanted = set(modules)
            mods = [m for m in mods if m.devid in wanted]
            if not mods:
                raise SystemExit("No modules matched PYBO_MODULES filter (devid).")

        out_modules: dict[str, Any] = {}

        for mod in mods:
            store = ParamStore()
            resolver = ParamResolver(store=store, assets=catalog, lang=lang)

            prime = await client.modules_parameters_prime([mod.devid], return_data=True)
            if isinstance(prime, tuple) and len(prime) == 2:
                st, data = prime[0], prime[1]
                if st in (200, 204) and isinstance(data, dict):
                    store.ingest_prime_payload(data)

            flat_values = store.flatten()
            perms = [str(p) for p in getattr(mod, "permissions", []) or []]
            menu = await catalog.get_module_menu(device_menu=mod.deviceMenu, permissions=perms)
            routes_i18n = await resolver._panel_title_i18n(menu)

            if capture_dir is not None:
                menu_payload = json.dumps(menu.model_dump(mode="json", by_alias=True), indent=2, ensure_ascii=False) + "\n"
                menu_path = capture_dir / f"menu_{mod.devid}.json"
                await asyncio.to_thread(capture_dir.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(menu_path.write_text, menu_payload, encoding="utf-8")

            # Discover static overlays before route rows so ``symbol_count`` /
            # ``panel_shell`` match panel diagnostics for timezone shells.
            static_route_symbols = await resolver._static_route_symbols_for_menu(menu)

            route_rows: list[dict[str, Any]] = []
            for route, ancestors in ParamResolver._iter_routes_with_ancestors(menu.routes):
                row = _route_row(
                    route,
                    ancestors=ancestors,
                    routes_i18n=routes_i18n,
                    static_route_symbols=static_route_symbols,
                )
                visible, vis_reason = ParamResolver.route_visibility_diagnostics(
                    route,
                    ancestors=ancestors,
                    flat_values=flat_values,
                    all_panels=True,
                    web_ui_only=False,
                )
                web_visible, web_reason = ParamResolver.route_visibility_diagnostics(
                    route,
                    ancestors=ancestors,
                    flat_values=flat_values,
                    all_panels=True,
                    web_ui_only=True,
                )
                row["route_visible"] = visible
                row["route_visibility_reason"] = vis_reason
                row["web_ui_visible"] = web_visible
                row["web_ui_visibility_reason"] = web_reason
                row["route_visibility_deps"] = sorted(ParamResolver.route_visibility_dependency_keys(route, ancestors=ancestors))
                route_rows.append(row)

            panel_diag = ParamResolver.panel_route_diagnostics_from_menu(
                menu,
                all_panels=True,
                web_ui_only=False,
                routes_i18n=routes_i18n,
                flat_values=flat_values,
                static_route_symbols=static_route_symbols,
            )
            web_diag = ParamResolver.panel_route_diagnostics_from_menu(
                menu,
                all_panels=True,
                web_ui_only=True,
                routes_i18n=routes_i18n,
                flat_values=flat_values,
                static_route_symbols=static_route_symbols,
            )
            groups_all = await resolver.build_panel_groups(
                device_menu=mod.deviceMenu,
                permissions=perms,
                all_panels=True,
                web_ui_only=False,
                flat_values=flat_values,
            )
            groups_web = await resolver.build_panel_groups(
                device_menu=mod.deviceMenu,
                permissions=perms,
                all_panels=True,
                web_ui_only=True,
                flat_values=flat_values,
            )

            filtered_rows = [row for row in route_rows if _matches_filter(row, filter_re=filter_re)]

            out_modules[str(mod.devid)] = {
                "name": mod.name,
                "device_menu": mod.deviceMenu,
                "permissions_count": len(perms),
                "panel_group_count_all": len(groups_all),
                "panel_group_count_web_ui": len(groups_web),
                "panel_groups_all": groups_all,
                "panel_groups_web_ui": groups_web,
                "route_diagnostics_all": panel_diag,
                "route_diagnostics_web_ui": web_diag,
                "filtered_route_rows": filtered_rows,
                "filtered_route_count": len(filtered_rows),
            }

        return {
            "object_id": object_id,
            "lang": lang,
            "module_count": len(out_modules),
            "modules": out_modules,
        }
    finally:
        await client.close()


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    _maybe_load_dotenv()
    parser = argparse.ArgumentParser(description="Probe live BragerOne menu routes (marpi82/ha-bragerone#192).")
    parser.add_argument("--lang", default=os.environ.get("PYBO_LANG", "pl"))
    parser.add_argument("--platform", default=os.environ.get("PYBO_PLATFORM", Platform.BRAGERONE.value))
    parser.add_argument(
        "--filter", dest="filter_text", default=None, help="Regex filter for route titles (default: strefy/schedule)"
    )
    parser.add_argument(
        "--capture-dir",
        type=Path,
        default=None,
        help="Optional directory to write sanitized menu JSON per module",
    )
    args = parser.parse_args(argv)

    email = require_env("PYBO_EMAIL")
    password = require_env("PYBO_PASSWORD")
    object_id = int(os.environ.get("PYBO_OBJECT_ID", "0") or "0")
    if object_id <= 0:
        raise SystemExit("Missing PYBO_OBJECT_ID: set it in .env.")
    modules = parse_modules(os.environ.get("PYBO_MODULES"))

    payload = asyncio.run(
        probe(
            email=email,
            password=password,
            object_id=object_id,
            modules=modules,
            lang=args.lang,
            platform=args.platform,
            filter_text=args.filter_text,
            capture_dir=args.capture_dir,
        )
    )
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
