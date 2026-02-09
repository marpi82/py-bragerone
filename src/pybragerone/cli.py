"""Diagnostic CLI for BragerOne (REST + WS)."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import re
import signal

from .api import BragerOneApiClient
from .gateway import BragerOneGateway
from .models import CLITokenStore, ParamStore
from .utils import bg_tasks, spawn

log = logging.getLogger(__name__)
CHAN_RE = re.compile(r"^([a-z])(\d+)$")


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
    api = BragerOneApiClient()
    api.set_token_store(store)

    await api.ensure_auth(args.email, args.password)

    object_id = args.object_id or (await _prompt_select_object(api))
    if not object_id:
        print("Missing object_id — exiting.")
        await api.close()
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
        await api.close()
        return 2

    # ParamStore (heavy) + connection to the gateway's EventBus
    param_store = ParamStore()

    # Keep a single authenticated ApiClient instance and inject it into the Gateway.
    gw = BragerOneGateway(api=api, object_id=object_id, modules=modules)

    spawn(param_store.run_with_bus(gw.bus), "ParamStore.run_with_bus", log)

    try:
        # Start gateway (REST prime + WS live)
        await gw.start()

        # Simple event "printer" (if not requesting raw-ws/no-diff)
        if not args.raw_ws and not args.no_diff:

            async def _printer() -> None:
                async for upd in gw.bus.subscribe():
                    print(f"↺ {upd.pool}.{upd.chan}{upd.idx} = {upd.value}")

            spawn(_printer(), "printer", log)

        print("\n▶ Listening started by Gateway. Ctrl+C to exit.\n")
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                asyncio.get_running_loop().add_signal_handler(sig, stop.set)

        try:
            await stop.wait()
        finally:
            # close gateway only on exit
            await gw.stop()
            await api.revoke()
            log.info("Auth revoked on exit...")
            # clean up tasks
            for t in list(bg_tasks):
                t.cancel()
            with contextlib.suppress(Exception):
                await asyncio.gather(*bg_tasks, return_exceptions=True)

    finally:
        # and here (externally) close HTTP client
        await api.close()

    return 0


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
    except KeyboardInterrupt:
        code = 130
    raise SystemExit(code)


if __name__ == "__main__":
    main()
