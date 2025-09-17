from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import signal

from .gateway import Gateway
from .labels_cli import add_subparser as add_labels_subparser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("bragerone")
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Global log level",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    # ---- run ----
    pr = sub.add_parser("run", help="Login + pick modules + snapshot + WebSocket listen")
    pr.add_argument("--email")
    pr.add_argument("--password")
    pr.add_argument("--object-id", type=int)
    pr.add_argument("--lang", default="en")

    # ---- labels (imported from labels_cli.py) ----
    add_labels_subparser(sub)

    return p


def _env_override(value: str | None, env_name: str) -> str | None:
    """Zwraca ENV jeśli ustawione (nawet nadpisując podany arg),
    w przeciwnym razie zwraca pierwotny argument."""
    env_val = os.getenv(env_name)
    if env_val is not None and env_val != "":
        return env_val
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "run":
        # ENV ma pierwszeństwo:
        args.email = _env_override(args.email, "PYBO_EMAIL")
        args.password = _env_override(args.password, "PYBO_PASSWORD")

        # object_id: jeśli ENV ustawione, nadpisz i zrzutuj na int
        obj_env = os.getenv("PYBO_OBJECT_ID")
        if obj_env is not None and obj_env != "":
            try:
                args.object_id = int(obj_env)
            except ValueError:
                parser.error("PYBO_OBJECT_ID must be an integer")

        # lang: ENV (PYBO_LANG) ma pierwszeństwo
        args.lang = _env_override(args.lang, "PYBO_LANG") or args.lang

        # Walidacja wymaganych po scaleniau:
        missing = []
        if not args.email:
            missing.append("email (or PYBO_EMAIL)")
        if not args.password:
            missing.append("password (or PYBO_PASSWORD)")
        if args.object_id is None:
            missing.append("object-id (or PYBO_OBJECT_ID)")

        if missing:
            parser.error("Missing required values for 'run': " + ", ".join(missing))

    return args


async def run_cmd(ns: argparse.Namespace) -> None:
    log = logging.getLogger("BragerOne")
    g = Gateway(ns.email, ns.password, object_id=ns.object_id, lang=ns.lang, logger=log)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, stop.set)

    try:
        await g.login()
        await g.pick_modules()
        # await g.bootstrap_labels()
        await g.initial_snapshot(prefetch_assets=True)
        await g.start_ws()

        log.info("listening for changes… (Ctrl-C to exit)")
        with contextlib.suppress(asyncio.CancelledError):
            await stop.wait()
    finally:
        with contextlib.suppress(Exception):
            await g.close()


def main(argv: list[str] | None = None) -> None:
    ns = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, ns.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if ns.cmd == "run":
        asyncio.run(run_cmd(ns))
        return

    if ns.cmd == "labels":
        rc = ns.func(ns)  # set by labels_cli
        raise SystemExit(rc)

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
