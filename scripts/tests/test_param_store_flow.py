#!/usr/bin/env python3
"""End-to-end sanity check for ParamStore menu flow.

This script:
1. Logs into the Brager One API using credentials from the local .env file
2. Selects an object and module (first by default, overridable via env vars)
3. Boots a ParamStore wired to the live API
4. Fetches the module menu through ParamStore and prints a structured summary

Usage::

    poetry run python scripts/tests/test_param_store_flow.py

Expected environment variables (typically provided via .env)::

    PYBO_EMAIL       Brager One login (required)
    PYBO_PASSWORD    Brager One password (required)
    PYBO_OBJECT_ID   Optional object id override
    PYBO_DEVICE_MENU Optional module menu id override
    PYBO_LANG        Optional preferred language code (e.g. "en")
    PYBO_MENU_DEBUG  Set to "1" to include routes beyond granted permissions

The script prints a concise textual dump of the module menu so you can quickly
verify the end-to-end flow without opening Home Assistant.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable
from typing import Any

from dotenv import load_dotenv

from pybragerone.api import BragerOneApiClient
from pybragerone.api.client import ApiError
from pybragerone.models.param import ParamStore

load_dotenv()


def _ensure_credentials() -> tuple[str, str]:
    email = os.getenv("PYBO_EMAIL")
    password = os.getenv("PYBO_PASSWORD")
    if not email or not password:
        raise RuntimeError("Set PYBO_EMAIL and PYBO_PASSWORD in your environment/.env file")
    return email, password


async def _select_object(client: BragerOneApiClient, object_id_override: str | None) -> Any:
    objects = await client.get_objects()
    if not objects:
        raise RuntimeError("No objects available for this account")

    if object_id_override:
        for obj in objects:
            if str(obj.id) == object_id_override:
                return obj
        raise RuntimeError(f"Object with id {object_id_override!r} not found for this user")

    return objects[0]


async def _select_module(client: BragerOneApiClient, object_id: int, menu_override: str | None) -> Any:
    modules = await client.get_modules(object_id)
    if not modules:
        raise RuntimeError(f"No modules returned for object id {object_id}")

    if menu_override is not None:
        for module in modules:
            if str(module.deviceMenu) == menu_override:
                return module
        raise RuntimeError(f"Module with deviceMenu {menu_override!r} not found for object id {object_id}")

    return modules[0]


def _collect_tokens(route: Any) -> set[str]:
    tokens: set[str] = set()

    def extract(parameters: Iterable[Any]) -> None:
        for param in parameters:
            token = getattr(param, "token", None)
            if isinstance(token, str):
                tokens.add(token)

    meta = route.meta
    if meta:
        params = meta.parameters
        extract(params.read)
        extract(params.write)
        extract(params.status)
        extract(params.special)

    extract(route.parameters.read)
    extract(route.parameters.write)
    extract(route.parameters.status)
    extract(route.parameters.special)

    return tokens


async def _print_route_details(store: ParamStore, route: Any) -> None:
    meta = route.meta
    display_name = meta.display_name if meta and meta.display_name else route.name
    print(f"\nRoute focus: {display_name} ({route.path})")
    if meta and meta.permission:
        print(f"  permission: {meta.permission.name}")

    tokens = sorted(_collect_tokens(route))
    if not tokens:
        print("  (No tokens discovered for this route)")
        return

    print("\n  Tokens detail")
    print("  ------------")
    for token in tokens:
        info = await store.describe_symbol(token)
        label = info.get("label") or "<missing label>"
        unit = info.get("unit") or "<no unit>"
        pool = info.get("pool")
        idx = info.get("idx")
        chan = info.get("chan")
        value = info.get("value")
        address = f"{pool}.{chan}{idx}" if pool and chan and idx is not None else "<no mapping>"
        print(f"  - {token}")
        print(f"    label: {label}")
        print(f"    unit: {unit}")
        print(f"    address: {address}")
        print(f"    value: {value}")
        unit_code = info.get("unit_code")
        if unit_code is not None and unit_code != unit:
            print(f"    unit code: {unit_code}")
        min_value = info.get("min")
        max_value = info.get("max")
        status_raw = info.get("status")
        if min_value is not None or max_value is not None:
            print(f"    range: min={min_value} max={max_value}")
        if status_raw is not None:
            print(f"    status raw: {status_raw}")
        mapping_info = info.get("mapping") or {}
        component_type = mapping_info.get("component_type")
        if component_type:
            print(f"    component: {component_type}")
        channels = mapping_info.get("channels") or {}
        if channels:

            def _fmt_addresses(entries: list[dict[str, Any]], *, include_condition: bool = True) -> str:
                parts: list[str] = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    condition = entry.get("condition")
                    if not include_condition and isinstance(condition, str):
                        continue
                    address = entry.get("channel") or entry.get("address")
                    if not address:
                        continue
                    bit = entry.get("bit")
                    suffix: list[str] = []
                    if isinstance(bit, int):
                        suffix.append(f"bit {bit}")
                    if include_condition and isinstance(condition, str):
                        suffix.append(condition)
                    if suffix:
                        parts.append(f"{address} ({', '.join(suffix)})")
                    else:
                        parts.append(address)
                return ", ".join(parts)

            value_path = _fmt_addresses(channels.get("value") or [])
            command_path = _fmt_addresses(channels.get("command") or [])
            unit_path = _fmt_addresses(channels.get("unit") or [])
            status_path = _fmt_addresses(channels.get("status") or [], include_condition=False)
            min_path = _fmt_addresses(channels.get("min") or [])
            max_path = _fmt_addresses(channels.get("max") or [])
            if value_path:
                print(f"    value channel: {value_path}")
            if command_path:
                print(f"    command channel: {command_path}")
            if unit_path:
                print(f"    unit channel: {unit_path}")
            if status_path:
                print(f"    status channel: {status_path}")
            if min_path or max_path:
                print(f"    limit channels: min={min_path or '-'} max={max_path or '-'}")
        command_rules = mapping_info.get("command_rules") or []
        if command_rules:
            print("    command rules:")
            for rule in command_rules:
                descriptors: list[str] = []
                logic = rule.get("logic")
                if isinstance(logic, str):
                    descriptors.append(logic)
                kind = rule.get("kind")
                if isinstance(kind, str):
                    descriptors.append(kind)
                heading = "/".join(descriptors) if descriptors else "-"
                command = rule.get("command") or "<no command>"
                value = rule.get("value")
                if value is not None:
                    print(f"      {heading}: {command} -> {value}")
                else:
                    print(f"      {heading}: {command}")
                conditions = rule.get("conditions") or []
                if conditions:
                    for condition in conditions:
                        operation = condition.get("operation") or "operation?"
                        expected = condition.get("expected")
                        expected_repr = "None" if expected is None else str(expected)
                        targets = condition.get("targets") or []
                        target_parts: list[str] = []
                        for target in targets:
                            if not isinstance(target, dict):
                                continue
                            channel_addr = target.get("channel") or target.get("address")
                            if not channel_addr:
                                continue
                            bit = target.get("bit")
                            if isinstance(bit, int):
                                target_parts.append(f"{channel_addr} (bit {bit})")
                            else:
                                target_parts.append(channel_addr)
                        target_repr = ", ".join(target_parts)
                        if target_repr:
                            print(f"        - {operation} {expected_repr} on {target_repr}")
                        else:
                            print(f"        - {operation} {expected_repr}")
                else:
                    print("        (no conditions)")
        status_conditions = mapping_info.get("status_conditions")
        if isinstance(status_conditions, dict) and status_conditions:
            print("    status conditions:")
            for condition, entries in sorted(status_conditions.items()):
                rendered: list[str] = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    channel_addr = entry.get("channel") or entry.get("address")
                    if not channel_addr:
                        continue
                    bit = entry.get("bit")
                    payload_parts = [f"channel: {channel_addr}"]
                    if isinstance(bit, int):
                        payload_parts.append(f"bit: {bit}")
                    rendered.append("{" + ", ".join(payload_parts) + "}")
                if not rendered:
                    rendered_text = "-"
                elif len(rendered) == 1:
                    rendered_text = rendered[0]
                else:
                    rendered_text = "[" + ", ".join(rendered) + "]"
                print(f"      {condition}: {rendered_text}")
        status_flags = mapping_info.get("status_flags") or []
        if status_flags:
            print(f"    status flags: {status_flags}")
        limits = mapping_info.get("limits")
        if isinstance(limits, dict) and limits:
            print(f"    limits: {limits}")


def _print_menu_summary(menu_result: Any, *, focus_path: str) -> Any:
    print("\nModule menu summary")
    print("====================")
    print(f"routes: {menu_result.route_count()}")
    print(f"unique tokens: {menu_result.token_count()}")
    print(f"asset url: {menu_result.asset_url}")

    focus_map = menu_result.routes_by_path()
    search_candidates = [focus_path]
    if "routes.modules.menu." in focus_path:
        shortened = focus_path.split("routes.modules.menu.", 1)[1]
        search_candidates.append(shortened)
    for candidate in search_candidates:
        focus_route = focus_map.get(candidate)
        if focus_route:
            print(f"\nFocused route: {candidate}")
            return focus_route
    available = ", ".join(sorted(focus_map.keys())[:10])
    print(f"\nFocus route '{focus_path}' not found. Available sample: {available}")
    return None


async def main() -> None:
    """Run the full ParamStore validation flow against live services."""
    email, password = _ensure_credentials()
    object_override = os.getenv("PYBO_OBJECT_ID")
    menu_override = os.getenv("PYBO_DEVICE_MENU")
    lang_override = os.getenv("PYBO_LANG")
    debug_override = os.getenv("PYBO_MENU_DEBUG", "0").strip().lower()
    debug_mode = debug_override in {"1", "true", "yes", "on"}
    focus_route_path = os.getenv("PYBO_MENU_ROUTE", "routes.modules.menu.boiler")

    client = BragerOneApiClient()
    try:
        token = await client.ensure_auth(email, password)
        print(f"Authenticated. Token expires at: {token.expires_at}")

        target_object = await _select_object(client, object_override)
        print(f"Selected object: {target_object.name} (id={target_object.id})")

        module = await _select_module(client, target_object.id, menu_override)
        print(f"Selected module: {module.name} (deviceMenu={module.deviceMenu}, permissions={len(module.permissions)})")

        store = ParamStore()
        store.init_with_api(client, lang=lang_override)

        prime_modules: list[str] = []
        if isinstance(module.devid, str) and module.devid:
            prime_modules.append(module.devid)
        if not prime_modules and isinstance(module.moduleAddress, str) and module.moduleAddress:
            prime_modules.append(module.moduleAddress)
        if not prime_modules:
            prime_modules.append(str(module.id))

        try:
            prime_result = await client.modules_parameters_prime(prime_modules, return_data=True)
        except ApiError as exc:
            print(f"Prime request failed: {exc}")
            prime_status, prime_payload = None, None
        else:
            if isinstance(prime_result, tuple):
                prime_status, prime_payload = prime_result
            else:
                prime_status, prime_payload = (200 if prime_result else None), None

        if prime_status in (200, 204) and isinstance(prime_payload, dict):
            store.ingest_prime_payload(prime_payload)
        else:
            print("Prime snapshot unavailable or malformed; units may remain unresolved until WS updates arrive.")

        permissions = module.permissions
        menu_result = await store.get_module_menu(
            device_menu=module.deviceMenu,
            permissions=permissions,
            debug_mode=debug_mode,
        )
        if debug_mode:
            print("\nDebug mode enabled: showing routes irrespective of permissions")
        else:
            print("\nApplied module permissions for route visibility")
        focus_route = _print_menu_summary(menu_result, focus_path=focus_route_path)

        if focus_route is not None:
            await _print_route_details(store, focus_route)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
