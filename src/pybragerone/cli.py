"""Diagnostic CLI for Brager One (REST + WS)."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import re
import signal
from collections.abc import Coroutine
from typing import Any

from .token_store import CLITokenStore
from .api import BragerOneApiClient
from .gateway import BragerGateway
from .models.param_store import ParamStore  # heavy store with EventBus consumer

log = logging.getLogger(__name__)
CHAN_RE = re.compile(r"^([a-z])(\d+)$")

IO_BASE = "https://io.brager.pl"
ONE_BASE = "https://one.brager.pl"


def _setup_logging(debug: bool, quiet: bool) -> None:
    level = logging.DEBUG if debug else (logging.WARNING if quiet else logging.INFO)
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )


async def _prompt_select_object(api: BragerOneApiClient) -> int | None:
    items = await api.objects_list()
    if not items:
        log.warning(
            "Nie udało się pobrać listy obiektów (/v1/objects). Podaj --object-id."
        )
        return None

    print("\nWybierz obiekt (instalację):")
    for i, o in enumerate(items, 1):
        name = o.get("name") or f"object-{o.get('id')}"
        print(f"[{i}] {name}  (id={o.get('id')})")
    while True:
        sel = input("Nr pozycji: ").strip()
        if not sel.isdigit():
            print("Podaj numer z listy.")
            continue
        idx = int(sel)
        if 1 <= idx <= len(items):
            return int(items[idx - 1]["id"])
        print("Poza zakresem, spróbuj ponownie.")


async def _prompt_select_modules(api: BragerOneApiClient, object_id: int) -> list[str]:
    """
    Poproś użytkownika o wybór modułów (devid/code/id) z listy zwróconej przez API.
    Zwraca posortowaną listę unikalnych stringów (np. ["FTTCTBSLCE"]).
    """
    rows = await api.modules_list(object_id=object_id)
    if not rows:
        print("Brak modułów dla wskazanego obiektu.")
        return []

    print("Dostępne moduły:")
    for i, m in enumerate(rows, start=1):
        name = str(m.get("name") or "-")
        code = m.get("devid") or m.get("code") or m.get("id")
        ver = m.get("moduleVersion") or m.get("gateway", {}).get("version") or "-"
        print(f"[{i}] {name:24} code={code}  ver={ver}")

    print("Wpisz numery rozdzielone przecinkami (np. 1,3) albo * dla wszystkich.")
    while True:
        sel = input("Wybór: ").strip()
        if sel == "*":
            # wszystkie
            all = {
                str(m.get("devid") or m.get("code") or m.get("id"))
                for m in rows
                if (m.get("devid") or m.get("code") or m.get("id")) is not None
            }
            return sorted(all)

        try:
            idxs = [int(x) for x in sel.replace(" ", "").split(",") if x]
        except ValueError:
            print("Podaj numery z listy.")
            continue

        choices: set[str] = set()
        for idx in idxs:
            if 1 <= idx <= len(rows):
                m = rows[idx - 1]
                code_obj = m.get("devid") or m.get("code") or m.get("id")
                if code_obj is not None:
                    choices.add(str(code_obj))

        if choices:
            return sorted(choices)

        print("Nieprawidłowy wybór — spróbuj ponownie.")


async def run(args: argparse.Namespace) -> int:
    _setup_logging(args.debug, args.quiet)

    store = CLITokenStore(args.email)

    # Tymczasowy klient REST do wyboru obiektu/modułów
    api = BragerOneApiClient(base_url=IO_BASE, origin=ONE_BASE, referer=f"{ONE_BASE}/")
    api.set_token_store(store)

    await api.ensure_auth(args.email, args.password)

    object_id = args.object_id or (await _prompt_select_object(api))
    if not object_id:
        print("Brak object_id — kończę.")
        await api.close()
        return 2

    modules: list[str]
    if args.modules:
        # można podać: --module FOO --module BAR lub PYBO_MODULES="FOO,BAR"
        if isinstance(args.modules, str):
            modules = [m for m in args.modules.split(",") if m]
        else:
            modules = list(args.modules)
    else:
        modules = await _prompt_select_modules(api, object_id)
    if not modules:
        print("Nie wybrano żadnych modułów — kończę.")
        await api.close()
        return 2

    # Nie trzymamy tej sesji — Gateway ma własny cykl życia
    await api.close()

    # ParamStore (ciężki) + połączenie z EventBusem gateway’a
    param_store = ParamStore()

    gw = BragerGateway(
        email=args.email,
        password=args.password,
        object_id=object_id,
        modules=modules,
        io_base=IO_BASE,
        origin=ONE_BASE,
        referer=f"{ONE_BASE}/",
    )

    # Konsument EventBusa (ParamStore)
    bg_tasks: set[asyncio.Task[Any]] = set()

    def _spawn(coro: Coroutine[Any, Any, Any], name: str) -> None:
        t = asyncio.create_task(coro, name=name)
        bg_tasks.add(t)

        def _done(task: asyncio.Task[Any]) -> None:
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception("Background task %s failed", name)
            finally:
                bg_tasks.discard(task)

        t.add_done_callback(_done)

    _spawn(param_store.run_with_bus(gw.bus), "ParamStore.run_with_bus")

    try:
        # Start gateway (REST prime + WS live)
        await gw.start()

        # Prosty „drukarz” zdarzeń (jeśli nie prosimy o raw-ws/no-diff)
        if not args.raw_ws and not args.no_diff:

            async def _printer() -> None:
                async for upd in gw.bus.subscribe():
                    print(f"↺ {upd.pool}.{upd.chan}{upd.idx} = {upd.value}")

            _spawn(_printer(), "printer")

        print("\n▶ Nasłuch uruchomiony przez Gateway. Ctrl+C aby zakończyć.\n")
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                asyncio.get_running_loop().add_signal_handler(sig, stop.set)

        try:
            await stop.wait()
        finally:
            # zamknij gateway dopiero przy wyjściu
            await gw.stop()
            await api.revoke()
            log.info("Autch revoked on exit...")
            # posprzątaj taski
            for t in list(bg_tasks):
                t.cancel()
            with contextlib.suppress(Exception):
                await asyncio.gather(*bg_tasks, return_exceptions=True)

    finally:
        # a tu (zewnętrznie) zamknij klienta HTTP
        await api.close()

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pybragerone", description="Brager One — diagnostyczny CLI (REST + WS)."
    )
    # env-first: jeśli brak w CLI, weź z otoczenia (łatwo debugować w VSCode)
    p.add_argument(
        "--email",
        default=os.environ.get("PYBO_EMAIL"),
        help="Login e-mail (ENV: PYBO_EMAIL)",
    )
    p.add_argument(
        "--password",
        default=os.environ.get("PYBO_PASSWORD"),
        help="Hasło (ENV: PYBO_PASSWORD)",
    )
    p.add_argument(
        "--object-id",
        type=int,
        default=os.environ.get("PYBO_OBJECT_ID") and int(os.environ["PYBO_OBJECT_ID"]),
        help="ID obiektu (ENV: PYBO_OBJECT_ID)",
    )
    p.add_argument(
        "--module",
        dest="modules",
        action="append",
        help="Kod modułu (devid/code). Można podać wielokrotnie lub w ENV PYBO_MODULES=FTTCTBSLCE,INNY",
        default=os.environ.get("PYBO_MODULES"),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Drukuj zdarzenia jako JSON (jedna linia na update)",
    )
    p.add_argument(
        "--raw-ws", action="store_true", help="Wypisuj surowe eventy WS (debug)"
    )
    p.add_argument(
        "--raw-http", action="store_true", help="Trace HTTP (uwaga na logi z danymi)"
    )
    p.add_argument(
        "--no-diff", action="store_true", help="Nie drukuj zmian (strzałek) na STDOUT"
    )
    p.add_argument("--debug", action="store_true", help="Więcej logów")
    p.add_argument("--quiet", action="store_true", help="Mniej logów")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # PYBO_MODULES=FOO,BAR → skonwertuj do listy jeśli nie użyto --module
    if isinstance(args.modules, str):
        args.modules = [m for m in args.modules.split(",") if m]

    if not args.email or not args.password:
        raise SystemExit(
            "Brak poświadczeń: ustaw PYBO_EMAIL/PYBO_PASSWORD lub przekaż --email/--password."
        )

    try:
        code = asyncio.run(run(args))
    except KeyboardInterrupt:
        code = 130
    raise SystemExit(code)


if __name__ == "__main__":
    main()
