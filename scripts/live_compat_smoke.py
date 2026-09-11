"""Read-only live library smoke: prime → panels → describe/resolve.

Logs into BragerOne with ``PYBO_*`` credentials and exercises the same catalog
paths Home Assistant bootstrap depends on. Exit codes::

    0 — smoke passed (individual ``None`` values are allowed)
    1 — hard failure (auth/prime/menu/describe/resolve raised or invariants broken)

Structural catalog drift belongs to ``live_contract.py`` (informational). This
script is the hard gate: when it passes after drift, the workflow may auto-reseed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pybragerone import BragerOneApiClient
from pybragerone.api.server import Platform, server_for
from pybragerone.models.catalog import LiveAssetsCatalog
from pybragerone.models.param import ParamStore
from pybragerone.models.param_resolver import ParamResolver


def parse_modules(raw: str | None) -> list[str]:
    """Split a comma-separated ``PYBO_MODULES`` string into sorted unique codes."""
    if not raw:
        return []
    return sorted({part.strip() for part in raw.split(",") if part.strip()})


def require_env(name: str) -> str:
    """Return a non-empty environment variable or raise ``SystemExit``."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing {name}: set it in the runner EnvironmentFile or process env.")
    return value


def prime_has_module_data(payload: Mapping[str, Any], devid: str) -> bool:
    """Return whether a modules/parameters prime payload includes non-empty data for *devid*."""
    for key in (devid, str(devid)):
        module_data = payload.get(key)
        if isinstance(module_data, Mapping) and module_data:
            return True
    return False


def evaluate_module_smoke(payload: Mapping[str, Any]) -> list[str]:
    """Return hard-failure reasons for one module smoke payload (empty when OK)."""
    errors: list[str] = []
    devid = str(payload.get("devid") or "?")
    if int(payload.get("panel_group_count_all") or 0) <= 0:
        errors.append(f"{devid}: build_panel_groups(all_panels) returned no panels")
    if int(payload.get("panel_group_count_web_ui") or 0) <= 0:
        errors.append(f"{devid}: build_panel_groups(web_ui_only) returned no panels")
    if int(payload.get("symbols_described") or 0) <= 0:
        errors.append(f"{devid}: describe_symbols covered zero panel symbols")
    if int(payload.get("symbols_resolved") or 0) <= 0:
        errors.append(f"{devid}: resolve_value covered zero panel symbols")
    if payload.get("describe_error"):
        errors.append(f"{devid}: describe_symbols failed: {payload['describe_error']}")
    if payload.get("resolve_error"):
        errors.append(f"{devid}: resolve_value failed: {payload['resolve_error']}")
    if payload.get("visibility_error"):
        errors.append(f"{devid}: visibility diagnostics failed: {payload['visibility_error']}")
    return errors


def evaluate_smoke_report(report: Mapping[str, Any]) -> list[str]:
    """Return hard-failure reasons for a full smoke report (empty when OK)."""
    modules = [module for module in (report.get("modules") or []) if isinstance(module, Mapping)]
    if not modules:
        explicit = report.get("errors")
        if isinstance(explicit, list) and explicit:
            return [str(item) for item in explicit if item]
        return ["no modules smoked"]
    errors: list[str] = []
    for module in modules:
        errors.extend(evaluate_module_smoke(module))
    return errors


async def smoke_module(
    *,
    client: BragerOneApiClient,
    catalog: LiveAssetsCatalog,
    devid: str,
    device_menu: int,
    permissions: Sequence[str],
    lang: str,
    max_resolve: int | None,
) -> dict[str, Any]:
    """Prime one module and exercise panel build + describe/resolve."""
    store = ParamStore()
    prime = await client.modules_parameters_prime([devid], return_data=True)
    if not isinstance(prime, tuple) or len(prime) != 2:
        raise RuntimeError(f"{devid}: modules_parameters_prime returned unexpected payload shape")
    status, data = prime
    if status not in (200, 204) or not isinstance(data, dict):
        raise RuntimeError(f"{devid}: modules_parameters_prime failed: status={status}")
    if not prime_has_module_data(data, devid):
        raise RuntimeError(f"{devid}: modules_parameters_prime returned no data for this module")
    store.ingest_prime_payload(data)
    if not store.flatten_for_devid(devid):
        raise RuntimeError(f"{devid}: prime ingest left an empty ParamStore bucket")
    flat_values = store.flatten_for_devid(devid)

    resolver = ParamResolver(store=store, assets=catalog, lang=lang)
    perms = [str(p) for p in permissions]

    groups_all = await resolver.build_panel_groups(
        device_menu=device_menu,
        permissions=perms,
        all_panels=True,
        web_ui_only=False,
        flat_values=flat_values,
    )
    groups_web = await resolver.build_panel_groups(
        device_menu=device_menu,
        permissions=perms,
        all_panels=True,
        web_ui_only=True,
        flat_values=flat_values,
    )
    symbols = sorted({sym for group in groups_all.values() for sym in group})
    symbols_to_resolve = symbols[:max_resolve] if max_resolve is not None and max_resolve >= 0 else symbols

    describe_error: str | None = None
    described = 0
    descriptions: dict[str, dict[str, Any]] = {}
    try:
        descriptions = await resolver.describe_symbols(symbols_to_resolve)
        described = len(descriptions)
    except Exception as exc:
        describe_error = f"{type(exc).__name__}: {exc}"

    resolve_error: str | None = None
    resolved = 0
    resolved_none = 0
    try:
        for symbol in symbols_to_resolve:
            value = await resolver.resolve_value(symbol)
            resolved += 1
            if getattr(value, "value", value) is None:
                resolved_none += 1
            unit_code = None
            desc = descriptions.get(symbol)
            if isinstance(desc, Mapping):
                unit_code = desc.get("unit_code")
            if unit_code is not None:
                await resolver.resolve_unit(unit_code)
    except Exception as exc:
        resolve_error = f"{type(exc).__name__}: {exc}"

    visibility_error: str | None = None
    visibility_checked = 0
    try:
        menu = await resolver.get_module_menu(device_menu=device_menu, permissions=perms)
        for route, ancestors in ParamResolver._iter_routes_with_ancestors(menu.routes):
            ParamResolver.route_visibility_diagnostics(
                route,
                ancestors=ancestors,
                flat_values=flat_values,
                all_panels=True,
                web_ui_only=True,
            )
            visibility_checked += 1
    except Exception as exc:
        visibility_error = f"{type(exc).__name__}: {exc}"

    return {
        "devid": devid,
        "device_menu": device_menu,
        "permissions_count": len(perms),
        "panel_group_count_all": len(groups_all),
        "panel_group_count_web_ui": len(groups_web),
        "symbols_total": len(symbols),
        "symbols_described": described,
        "symbols_resolved": resolved,
        "symbols_resolved_none": resolved_none,
        "visibility_routes_checked": visibility_checked,
        "describe_error": describe_error,
        "resolve_error": resolve_error,
        "visibility_error": visibility_error,
    }


async def run_compat_smoke(
    *,
    email: str,
    password: str,
    object_id: int,
    modules: Sequence[str],
    lang: str,
    platform: str,
    max_resolve: int | None = None,
) -> dict[str, Any]:
    """Authenticate and smoke every selected module."""
    server = server_for(platform)
    client = BragerOneApiClient(server=server, creds_provider=lambda: (email, password), validate_on_start=False)
    module_payloads: list[dict[str, Any]] = []
    try:
        await client.ensure_auth(email, password)
        catalog = LiveAssetsCatalog(client)
        mods = await client.get_modules(object_id)
        if not mods:
            raise RuntimeError("get_modules returned no modules for this object")
        if modules:
            wanted = set(modules)
            by_devid = {str(mod.devid): mod for mod in mods}
            missing = sorted(wanted - by_devid.keys())
            if missing:
                raise RuntimeError("PYBO_MODULES includes module(s) not returned by get_modules: " + ", ".join(missing))
            mods = [by_devid[devid] for devid in sorted(wanted)]

        for mod in mods:
            payload = await smoke_module(
                client=client,
                catalog=catalog,
                devid=str(mod.devid),
                device_menu=int(mod.deviceMenu),
                permissions=list(getattr(mod, "permissions", []) or []),
                lang=lang,
                max_resolve=max_resolve,
            )
            module_payloads.append(payload)
    finally:
        await client.close()

    report: dict[str, Any] = {
        "compat_ok": True,
        "object_id": object_id,
        "lang": lang,
        "module_count": len(module_payloads),
        "panel_count": sum(int(m.get("panel_group_count_all") or 0) for m in module_payloads),
        "symbols_described": sum(int(m.get("symbols_described") or 0) for m in module_payloads),
        "symbols_resolved": sum(int(m.get("symbols_resolved") or 0) for m in module_payloads),
        "modules": module_payloads,
        "errors": [],
    }
    failures = evaluate_smoke_report(report)
    report["errors"] = failures
    report["compat_ok"] = not failures
    return report


def write_github_output(report: Mapping[str, Any]) -> None:
    """Append job outputs when running under GitHub Actions."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        return
    with Path(github_output).open("a", encoding="utf-8") as handle:
        handle.write(f"compat_ok={str(bool(report.get('compat_ok'))).lower()}\n")
        handle.write(f"module_count={int(report.get('module_count') or 0)}\n")
        handle.write(f"panel_count={int(report.get('panel_count') or 0)}\n")
        handle.write(f"symbols_described={int(report.get('symbols_described') or 0)}\n")
        handle.write(f"symbols_resolved={int(report.get('symbols_resolved') or 0)}\n")
        handle.write(f"error_count={len(report.get('errors') or [])}\n")


def write_step_summary(report: Mapping[str, Any]) -> None:
    """Write a short markdown summary for the Actions UI."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "## Live compat smoke",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| compat_ok | {str(bool(report.get('compat_ok'))).lower()} |",
        f"| modules | {int(report.get('module_count') or 0)} |",
        f"| panels | {int(report.get('panel_count') or 0)} |",
        f"| symbols described | {int(report.get('symbols_described') or 0)} |",
        f"| symbols resolved | {int(report.get('symbols_resolved') or 0)} |",
        f"| errors | {len(report.get('errors') or [])} |",
        "",
    ]
    errors = report.get("errors") or []
    if isinstance(errors, list) and errors:
        lines.append("### Errors")
        lines.append("")
        for item in errors[:20]:
            lines.append(f"- `{item}`")
        lines.append("")
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    """CLI entry: run the live library compat smoke."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-json",
        type=Path,
        default=None,
        help="Write the smoke report JSON here (CI artifact).",
    )
    parser.add_argument(
        "--max-resolve",
        type=int,
        default=None,
        help="Optional cap on symbols described/resolved per module (default: all panel symbols).",
    )
    args = parser.parse_args(argv)

    email = require_env("PYBO_EMAIL")
    password = require_env("PYBO_PASSWORD")
    object_id = int(require_env("PYBO_OBJECT_ID"))
    modules = parse_modules(os.environ.get("PYBO_MODULES"))
    if not modules:
        raise SystemExit("Missing PYBO_MODULES: set a comma-separated module list.")
    lang = os.environ.get("PYBO_LANG", "en").strip() or "en"
    platform = os.environ.get("PYBO_PLATFORM", Platform.BRAGERONE.value).strip() or Platform.BRAGERONE.value

    try:
        report = asyncio.run(
            run_compat_smoke(
                email=email,
                password=password,
                object_id=object_id,
                modules=modules,
                lang=lang,
                platform=platform,
                max_resolve=args.max_resolve,
            )
        )
    except Exception as exc:
        report = {
            "compat_ok": False,
            "module_count": 0,
            "panel_count": 0,
            "symbols_described": 0,
            "symbols_resolved": 0,
            "modules": [],
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
        print(f"live compat smoke failed: {exc}", file=sys.stderr)

    failures = evaluate_smoke_report(report)
    report = dict(report)
    report["errors"] = failures
    report["compat_ok"] = not failures

    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    if args.write_json is not None:
        args.write_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_json.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    write_github_output(report)
    write_step_summary(report)
    if failures:
        print(f"live compat smoke: {len(failures)} hard failure(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
