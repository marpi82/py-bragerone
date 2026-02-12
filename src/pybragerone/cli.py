"""Diagnostic CLI for BragerOne (REST + WS)."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import re
import signal
import threading
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx

from .api import BragerOneApiClient, Platform, server_for
from .api.client import ApiError
from .gateway import BragerOneGateway
from .models import CLITokenStore, ParamResolver, ParamStore
from .utils import bg_tasks, spawn

log = logging.getLogger(__name__)
CHAN_RE = re.compile(r"^([a-z])(\d+)$")


@dataclass(slots=True)
class _WatchItem:
    symbol: str
    label: str
    unit: str | dict[str, str] | None
    address: str | None
    value: Any
    value_label: str | None
    kind: str


def _maybe_load_dotenv() -> None:
    """Load environment variables from a `.env` file, if supported.

    Notes:
        The CLI reads defaults from `os.environ` (e.g. `PYBO_EMAIL`). Typical shells and `uv run` do not
        automatically load `.env`, so we opportunistically load it when `python-dotenv` is installed.

        Existing environment variables are not overridden.
    """
    try:
        from dotenv import find_dotenv, load_dotenv
    except Exception:
        return

    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)


def _setup_logging(debug: bool, quiet: bool) -> None:
    """Setup logging based on debug/quiet flags."""
    level = logging.DEBUG if debug else (logging.WARNING if quiet else logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def _prompt_select_object(api: BragerOneApiClient) -> int | None:
    """Prompt user to select an object from the list of available ones."""
    items = await api.get_objects()
    if not items:
        log.warning("Failed to fetch the list of objects (/v1/objects). Provide --object-id.")
        return None

    print("\nSelect an object (installation):")
    for i, o in enumerate(items, 1):
        name = o.name or f"object-{o.id}"
        print(f"[{i}] {name}  (id={o.id})")
    while True:
        sel = input("Item number: ").strip()
        if not sel.isdigit():
            print("Enter a number from the list.")
            continue
        idx = int(sel)
        if 1 <= idx <= len(items):
            return items[idx - 1].id
        print("Out of range, try again.")


async def _prompt_select_modules(api: BragerOneApiClient, object_id: int) -> list[str]:
    """Prompt user to select modules from the list of available ones."""
    rows = await api.get_modules(object_id=object_id)
    if not rows:
        print("No modules for the selected object.")
        return []

    print("Available modules:")
    for i, m in enumerate(rows, start=1):
        name = str(m.name or "-")
        code = m.devid or str(m.id)
        ver = m.moduleVersion or m.gateway.version or "-"
        print(f"[{i}] {name:24} code={code}  ver={ver}")

    print("Enter numbers separated by commas (e.g. 1,3) or * for all.")
    while True:
        sel = input("Selection: ").strip()
        if sel == "*":
            # all
            all = {str(m.devid or m.id) for m in rows if (m.devid or m.id) is not None}
            return sorted(all)

        try:
            idxs = [int(x) for x in sel.replace(" ", "").split(",") if x]
        except ValueError:
            print("Enter numbers from the list.")
            continue

        choices: set[str] = set()
        for idx in idxs:
            if 1 <= idx <= len(rows):
                m = rows[idx - 1]
                code_obj = m.devid or str(m.id)
                if code_obj is not None:
                    choices.add(str(code_obj))

        if choices:
            return sorted(choices)

        print("Invalid selection — please try again.")


async def run(args: argparse.Namespace) -> int:
    """Run the CLI with given args."""
    _setup_logging(args.debug, args.quiet)

    store = CLITokenStore(args.email)

    # Temporary REST client for object/modules selection
    server = server_for(args.platform)
    api = BragerOneApiClient(server=server)
    api.set_token_store(store)

    gw: BragerOneGateway | None = None

    try:
        await api.ensure_auth(args.email, args.password)

        object_id = args.object_id or (await _prompt_select_object(api))
        if not object_id:
            print("Missing object_id — exiting.")
            return 2

        modules: list[str]
        if args.modules:
            # you can provide: --module FOO --module BAR or PYBO_MODULES="FOO,BAR"
            if isinstance(args.modules, str):
                modules = [m for m in args.modules.split(",") if m]
            else:
                modules = [str(m) for m in args.modules if m]
        else:
            modules = await _prompt_select_modules(api, object_id)
        if not modules:
            print("No modules selected — exiting.")
            return 2

        # Runtime ParamStore is storage-only; opt into heavy resolution via ParamResolver.
        param_store = ParamStore()
        resolver = ParamResolver.from_api(api=api, store=param_store, lang=str(args.lang).strip().lower())

        # Keep a single authenticated ApiClient instance and inject it into the Gateway.
        gw = BragerOneGateway(api=api, object_id=object_id, modules=modules)

        # Start TUI subscriber BEFORE gateway prime so we don't miss the initial snapshot.
        spawn(
            _run_tui(
                api=api,
                gw=gw,
                store=param_store,
                resolver=resolver,
                object_id=object_id,
                module_ids=modules,
                json_events=bool(args.json),
                suppress_log=bool(args.no_diff),
                debug_logging=bool(args.debug),
            ),
            "tui",
            log,
        )

        # Start gateway (REST prime + WS live)
        await gw.start()

        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                asyncio.get_running_loop().add_signal_handler(sig, stop.set)

        await stop.wait()
        return 0
    finally:
        if gw is not None:
            with contextlib.suppress(Exception):
                await gw.stop()

        # Best-effort token revoke (keep behavior, but never crash on exit)
        with contextlib.suppress(Exception):
            await api.revoke()

        # Clean up background tasks
        for t in list(bg_tasks):
            t.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(*bg_tasks, return_exceptions=True)

        await api.close()


def _route_title(route: Any) -> str:
    meta = getattr(route, "meta", None)
    dn = getattr(meta, "display_name", None) if meta is not None else None
    if isinstance(dn, str) and dn.strip():
        return dn.strip()
    name = getattr(route, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    path = getattr(route, "path", None)
    return str(path or "-")


def _iter_routes(routes: Iterable[Any]) -> Iterable[Any]:
    stack = list(routes)[::-1]
    while stack:
        cur = stack.pop()
        yield cur
        children = getattr(cur, "children", None)
        if isinstance(children, list):
            for child in reversed(children):
                stack.append(child)


def _collect_route_symbols(route: Any) -> set[str]:
    symbols: set[str] = set()

    def add_from_container(container: Any) -> None:
        if container is None:
            return
        for kind in ("read", "write", "status", "special"):
            items = getattr(container, kind, None)
            if not isinstance(items, list):
                continue
            for item in items:
                tok = getattr(item, "token", None)
                if isinstance(tok, str) and tok:
                    symbols.add(tok)

    meta = getattr(route, "meta", None)
    if meta is not None:
        add_from_container(getattr(meta, "parameters", None))
    # Legacy / compatibility field
    add_from_container(getattr(route, "parameters", None))
    return symbols


def _normalize(s: str) -> str:
    return "".join(ch for ch in s.casefold() if ch.isalnum() or ch.isspace()).strip()


async def _build_watch_groups(
    *,
    api: BragerOneApiClient,
    resolver: ParamResolver,
    object_id: int,
    module_ids: list[str],
) -> dict[str, list[str]]:
    """Build watch groups using module menu routes.

    This aims to approximate the official UI sections without hardcoding tokens.
    """
    modules = await api.get_modules(object_id=object_id)
    selected = {m.devid: m for m in modules if m.devid is not None and str(m.devid) in set(module_ids)}
    # Use the first module to derive the menu for grouping.
    first_id = module_ids[0]
    mod = selected.get(first_id)
    if mod is None:
        return {"Boiler": [], "DHW": [], "Valve 1": []}

    device_menu = int(mod.deviceMenu)
    perms = list(getattr(mod, "permissions", []) or [])
    menu = await resolver.get_module_menu(device_menu=device_menu, permissions=perms)

    routes_by_title: list[tuple[str, set[str]]] = []
    for r in _iter_routes(menu.routes):
        symbols = _collect_route_symbols(r)
        if symbols:
            routes_by_title.append((_route_title(r), symbols))

    def pick(title_keywords: list[str]) -> set[str]:
        want = [_normalize(k) for k in title_keywords]
        out: set[str] = set()
        for title, symbols in routes_by_title:
            t = _normalize(title)
            if any(w and w in t for w in want):
                out |= symbols
        return out

    boiler = pick(["boiler"])
    dhw = pick(["dhw"])
    valve = pick(["valve_1"])

    groups: dict[str, list[str]] = {
        "Boiler": sorted(boiler),
        "DHW": sorted(dhw),
        "Valve 1": sorted(valve),
    }
    return groups


async def _run_tui(
    *,
    api: BragerOneApiClient,
    gw: BragerOneGateway,
    store: ParamStore,
    resolver: ParamResolver,
    object_id: int,
    module_ids: list[str],
    json_events: bool,
    suppress_log: bool,
    debug_logging: bool = False,
) -> None:
    """Run a minimal Rich TUI with a live values area and a scrolling log."""
    try:
        from rich.console import Console
        from rich.layout import Layout
        from rich.live import Live
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "TUI mode requires optional CLI dependencies. Install the 'cli' extra (e.g. `pip install pybragerone[cli]`)."
        ) from exc

    console = Console()
    log_lines: deque[str] = deque(maxlen=200)
    log_lines.append("▶ Starting… waiting for prime and live updates. Ctrl+C to exit.")

    loop = asyncio.get_running_loop()
    log_lock = threading.Lock()

    watch: dict[str, _WatchItem] = {}
    group_symbols: dict[str, list[str]] = {"Boiler": [], "DHW": [], "Valve 1": []}

    def render_group(name: str) -> Panel:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column("Name", ratio=2, no_wrap=True, overflow="ellipsis")
        table.add_column("Value", ratio=1, no_wrap=True, overflow="ellipsis")

        symbols = group_symbols.get(name, [])
        if not symbols:
            table.add_row("Loading…", "")
            return Panel(table, title=name)

        for sym in symbols[:30]:
            it = watch.get(sym)
            if it is None:
                continue
            val = it.value_label if it.value_label is not None else it.value
            if isinstance(it.unit, str):
                val = f"{val} {it.unit}" if val is not None else "-"
            table.add_row(str(it.label), str(val) if val is not None else "-")

        return Panel(table, title=name)

    def render_log() -> Panel:
        text = Text("\n".join(log_lines))
        return Panel(text, title="Console")

    def build_layout() -> Layout:
        root = Layout(name="root")
        root.split_column(Layout(name="top", ratio=3), Layout(name="bottom", ratio=1))
        root["top"].split_row(
            Layout(name="boiler"),
            Layout(name="dhw"),
            Layout(name="valve"),
        )
        root["bottom"].update(render_log())
        root["boiler"].update(render_group("Boiler"))
        root["dhw"].update(render_group("DHW"))
        root["valve"].update(render_group("Valve 1"))
        return root

    layout = build_layout()

    def refresh_panels() -> None:
        layout["bottom"].update(render_log())
        layout["boiler"].update(render_group("Boiler"))
        layout["dhw"].update(render_group("DHW"))
        layout["valve"].update(render_group("Valve 1"))

    dirty = asyncio.Event()

    def _append_log_line(line: str) -> None:
        with log_lock:
            log_lines.append(line)
        dirty.set()

    class _TuiLogHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            # Keep noise down by default.
            min_level = logging.DEBUG if debug_logging else logging.WARNING
            if record.levelno < min_level:
                return
            msg = self.format(record)
            loop.call_soon_threadsafe(_append_log_line, msg)

    def _format_event_key(upd: Any) -> str:
        pool_raw = getattr(upd, "pool", None)
        pool = str(pool_raw)
        if pool.isdigit():
            pool = f"P{pool}"
        elif not pool.startswith("P") and pool:
            # Best-effort: if upstream provides pool without 'P' but not purely numeric.
            pool = f"P{pool}"
        return f"{pool}.{upd.chan}{upd.idx}"

    async def bus_ingest() -> None:
        async for upd in gw.bus.subscribe():
            if getattr(upd, "value", None) is None:
                continue
            key = _format_event_key(upd)
            await store.upsert_async(key, upd.value)
            if not suppress_log:
                if json_events:
                    log_lines.append(json.dumps({"key": key, "value": upd.value}, ensure_ascii=False))
                else:
                    log_lines.append(f"↺ {key} = {upd.value}")
            dirty.set()

    async def init_watch() -> None:
        groups = await _build_watch_groups(api=api, resolver=resolver, object_id=object_id, module_ids=module_ids)
        group_symbols.clear()
        group_symbols.update(groups)

        # Build watch items (labels + mapping) once; values will be refreshed from ParamStore on dirty ticks.
        for _group_name, symbols in group_symbols.items():
            for sym in symbols[:30]:
                if sym in watch:
                    continue
                desc = await resolver.describe_symbol(sym)
                resolved = await resolver.resolve_value(sym)
                watch[sym] = _WatchItem(
                    symbol=sym,
                    label=str(desc.get("label") or sym),
                    unit=resolved.unit,
                    address=resolved.address,
                    value=resolved.value,
                    value_label=resolved.value_label,
                    kind=resolved.kind,
                )

        dirty.set()

    async def refresh_loop(*, live: Live) -> None:
        # Manual refresh to reduce blinking.
        while True:
            try:
                await asyncio.wait_for(dirty.wait(), timeout=0.25)
            except TimeoutError:
                continue
            dirty.clear()

            # Re-resolve values from ParamStore so we don't depend on matching raw update keys.
            for sym, it in watch.items():
                resolved = await resolver.resolve_value(sym)
                it.value = resolved.value
                it.value_label = resolved.value_label

            refresh_panels()
            live.refresh()

    live = Live(layout, console=console, screen=True, auto_refresh=False)

    root_logger = logging.getLogger()
    prev_handlers = list(root_logger.handlers)
    prev_level = root_logger.level
    prev_httpx_level = logging.getLogger("httpx").level
    prev_ws_eio_level = logging.getLogger("pybragerone.api.ws.eio").level
    prev_ws_sio_level = logging.getLogger("pybragerone.api.ws.sio").level
    prev_catalog_level = logging.getLogger("pybragerone.models.catalog").level

    handler = _TuiLogHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    # In TUI mode, don't print logs to stdout/stderr.
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if debug_logging else logging.WARNING)
    if not debug_logging:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("pybragerone.api.ws.eio").setLevel(logging.WARNING)
        logging.getLogger("pybragerone.api.ws.sio").setLevel(logging.WARNING)
        logging.getLogger("pybragerone.models.catalog").setLevel(logging.WARNING)

    try:
        with live, contextlib.suppress(asyncio.CancelledError):
            refresh_panels()
            live.refresh()
            async with asyncio.TaskGroup() as tg:
                tg.create_task(bus_ingest())
                tg.create_task(init_watch())
                tg.create_task(refresh_loop(live=live))
    finally:
        root_logger.handlers = prev_handlers
        root_logger.setLevel(prev_level)
        logging.getLogger("httpx").setLevel(prev_httpx_level)
        logging.getLogger("pybragerone.api.ws.eio").setLevel(prev_ws_eio_level)
        logging.getLogger("pybragerone.api.ws.sio").setLevel(prev_ws_sio_level)
        logging.getLogger("pybragerone.models.catalog").setLevel(prev_catalog_level)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    p = argparse.ArgumentParser(prog="pybragerone", description="BragerOne — diagnostic CLI (REST + WS).")
    # env-first: if not in CLI, take from environment (easy to debug in VSCode)
    p.add_argument(
        "--email",
        default=os.environ.get("PYBO_EMAIL"),
        help="Login email (ENV: PYBO_EMAIL)",
    )
    p.add_argument(
        "--password",
        default=os.environ.get("PYBO_PASSWORD"),
        help="Password (ENV: PYBO_PASSWORD)",
    )
    p.add_argument(
        "--platform",
        choices=[p.value for p in Platform],
        default=os.environ.get("PYBO_PLATFORM", Platform.BRAGERONE.value),
        help="Backend platform: bragerone or tisconnect (ENV: PYBO_PLATFORM). Default: bragerone",
    )
    p.add_argument(
        "--lang",
        default=os.environ.get("PYBO_LANG", "en"),
        help="Language code for asset-driven labels (ENV: PYBO_LANG). Default: en",
    )
    p.add_argument(
        "--object-id",
        type=int,
        default=os.environ.get("PYBO_OBJECT_ID") and int(os.environ["PYBO_OBJECT_ID"]),
        help="Object ID (ENV: PYBO_OBJECT_ID)",
    )
    p.add_argument(
        "--module",
        dest="modules",
        action="append",
        help="Module code (devid/code). Can be specified multiple times or via ENV PYBO_MODULES=FTTCTBSLCE,OTHER",
        default=os.environ.get("PYBO_MODULES"),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print events as JSON (one line per update)",
    )
    p.add_argument("--raw-ws", action="store_true", help="Print raw WS events (debug)")
    p.add_argument("--raw-http", action="store_true", help="Trace HTTP (warning: logs may contain data)")
    p.add_argument("--no-diff", action="store_true", help="Don't print changes (arrows) on STDOUT")
    p.add_argument("--debug", action="store_true", help="More logs")
    p.add_argument("--quiet", action="store_true", help="Fewer logs")
    return p


def main() -> None:
    """Main entrypoint for CLI."""
    _maybe_load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    # PYBO_MODULES=FOO,BAR → convert to list if --module was not used
    if isinstance(args.modules, str):
        args.modules = [m for m in args.modules.split(",") if m]

    if not args.email or not args.password:
        raise SystemExit("Missing credentials: set PYBO_EMAIL/PYBO_PASSWORD or pass --email/--password.")

    try:
        code = asyncio.run(run(args))
    except ApiError as exc:
        payload = exc.data
        body = json.dumps(payload, ensure_ascii=False) if isinstance(payload, (dict, list)) else str(payload)
        raise SystemExit(f"HTTP {exc.status}: {body}") from None
    except httpx.RequestError as exc:
        raise SystemExit(f"Network error: {exc.__class__.__name__}: {exc}") from None
    except KeyboardInterrupt:
        code = 130
    raise SystemExit(code)


if __name__ == "__main__":
    main()
