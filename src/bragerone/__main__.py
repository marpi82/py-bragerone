from __future__ import annotations
import argparse
import asyncio
import logging
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
    pr.add_argument("--email", required=True)
    pr.add_argument("--password", required=True)
    pr.add_argument("--object-id", type=int, required=True)
    pr.add_argument("--lang", default="en")

    # ---- labels (imported from labels_cli.py) ----
    add_labels_subparser(sub)

    return p


async def run_cmd(ns: argparse.Namespace) -> None:
    log = logging.getLogger("BragerOne")
    g = Gateway(ns.email, ns.password, object_id=ns.object_id, lang=ns.lang, logger=log)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    try:
        await g.login()
        await g.pick_modules()
        await g.bootstrap_labels()
        await g.initial_snapshot()
        await g.start_ws()

        log.info("listening for changes… (Ctrl-C to exit)")
        try:
            await stop.wait()   # <-- tu „śpimy”
        except asyncio.CancelledError:
            # Ctrl-C / SIGTERM — bez hałasu
            pass
    finally:
        try:
            await g.close()
        except Exception:
            pass


def main() -> None:
    ns = build_parser().parse_args()

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

