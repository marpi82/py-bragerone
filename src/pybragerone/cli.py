"""Module src/pybragerone/cli.py."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import re
import signal
from typing import Any

from .api import BragerOneApiClient
from .gateway import BragerGateway
from .models.param_store import ParamStore

LOG = logging.getLogger("pybragerone.cli")
CHAN_RE = re.compile(r"^([a-z])(\d+)$")

last_values = {}  # (pool, chan, idx) -> value

def human(obj):
    """Human.

    Args:
    obj: TODO.

    Returns:
    TODO.
    """
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def jsonl_write(path, obj):
    """Jsonl write.

    Args:
    path: TODO.
    obj: TODO.

    Returns:
    TODO.
    """
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def _setup_logging(debug: bool, quiet: bool):
    """Setup logging.

    Args:
    debug: TODO.
    quiet: TODO.

    Returns:
    TODO.
    """
    level = logging.DEBUG if debug else (logging.WARNING if quiet else logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def _prompt_select_object(api: BragerOneApiClient) -> int | None:
    # spróbuj /v1/objects (lista)
    """Prompt select object.

    Args:
    api: TODO.

    Returns:
    TODO.
    """
    try:
        objs = await api.list_objects()
        items = objs.get("objects") if isinstance(objs, dict) else None
    except Exception:
        items = None
    # fallback: z loginu bywa lista w "objects", ale tu nie mamy payloadu => zrób /user (może brak)
    if not items:
        LOG.warning("Nie udało się pobrać listy obiektów (/v1/objects). Podaj --object-id.")
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
    """Prompt select modules.

    Args:
    api: TODO.
    object_id: TODO.

    Returns:
    TODO.
    """
    rows = await api.list_modules(group_id=object_id, page=1, limit=999)

    if not rows:
        LOG.error("Brak modułów dla object_id=%s", object_id)
        return []

    print("\nDostępne moduły:")
    for i, m in enumerate(rows, 1):
        if isinstance(m, dict):
            code = m.get("devid") or m.get("code") or str(m.get("id"))
            name = m.get("moduleTitle") or m.get("name") or code
            ver  = m.get("moduleVersion") or m.get("version") or "-"
        else:
            code = str(m)
            name = code
            ver = "-"
        print(f"[{i}] {name}  code={code}  ver={ver}")

    print("Wpisz numery rozdzielone przecinkami (np. 1,3) albo * dla wszystkich.")
    while True:
        sel = input("Wybór: ").strip()
        if sel == "*":
            out = []
            for m in rows:
                if isinstance(m, dict):
                    out.append(m.get("devid") or m.get("code") or str(m.get("id")))
                else:
                    out.append(str(m))
            return sorted(set(out))

        try:
            idxs = [int(x) for x in sel.replace(" ", "").split(",") if x]
        except ValueError:
            print("Podaj numery z listy.")
            continue

        out = []
        for idx in idxs:
            if 1 <= idx <= len(rows):
                m = rows[idx - 1]
                code = m.get("devid") or m.get("code") or str(m.get("id")) if isinstance(m, dict) else str(m)
                if code:
                    out.append(code)
        if out:
            return sorted(set(out))

        print("Nieprawidłowy wybór - spróbuj ponownie.")
        with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError):
            await asyncio.Event().wait()

def _print_event_diff(key: str, value: Any, print_json: bool):
    """Print event diff.

    Args:
    key: TODO.
    value: TODO.
    print_json: TODO.

    Returns:
    TODO.
    """
    if print_json:
        print(json.dumps({"type": "param.update", "key": key, "value": value}, ensure_ascii=False))
    else:
        vtxt = human(value)
        print(f"↺ {key} = {vtxt}")


async def run(args):
    """Run.

    Args:
    args: TODO.

    Returns:
    TODO.
    """
    _setup_logging(args.debug, args.quiet)

    # 1) login → wybór object_id / modules (jak dotąd)
    async with BragerOneApiClient() as api:
        _login = await api.login(args.email, args.password)
        # wybór object_id i modules tak jak miałeś wcześniej...
        object_id: int | None = args.object_id or (await _prompt_select_object(api))
        if not object_id:
            LOG.error("Brak object_id - nie można kontynuować.")
            return 1
        modules: list[str] | None = args.module or (await _prompt_select_modules(api, object_id))
        # zamknij tymczasową sesję - Gateway stworzy własną
        await api.close()


    # 2) uruchom Gateway
    param_store = ParamStore()
    gw = BragerGateway(
        email=args.email,
        password=args.password,
        object_id=object_id,
        modules=modules,
        keep_param_store=True,
    )
    async with asyncio.TaskGroup() as tg:
        tg.create_task(param_store.run_with_bus(gw.bus))


        # 3) podłącz drukowanie update'ów
        #    lekkie wypisywanie na STDOUT bez --raw-ws
        if not args.raw_ws and not args.no_diff:
            async def _printer():
                """Printer.

                Returns:
                TODO.
                """
                async for upd in gw.bus.subscribe():
                    print(f"↺ {upd.pool}.{upd.chan}{upd.idx} = {upd.value}")
            tg.create_task(_printer())

    # surowe payloady (INFO) - przez gateway.on_any, jak wcześniej
    #if args.raw_ws:
    #    gw.on_any(lambda ev, payload: LOG.info("WS RAW %s → %s", ev, payload))

    # 4) start/stop
    await gw.start()

    # czekamy na prima żeby zrobić dump
    await asyncio.sleep(5)  # mały oddech dla konsumentów

    param_store.debug_dump()

    LOG.debug("ingested counters: param_store=%d", getattr(param_store, "_ingested", -1))

    print("\n▶ Nasłuch uruchomiony przez Gateway. Ctrl+C aby zakończyć.\n")
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        await gw.stop()


def build_parser() -> argparse.ArgumentParser:
    """Build parser.

    Returns:
    TODO.
    """
    p = argparse.ArgumentParser(prog="pybragerone", description="Brager One — diagnostyczny CLI (REST + WS).")
    p.add_argument("--email", required=True, help="Login e-mail")
    p.add_argument("--password", required=True, help="Hasło")
    p.add_argument("--object-id", type=int, help="ID obiektu (gdy brak — CLI zapyta)")
    p.add_argument("--module", action="append", help="Kod modułu (devid/code). Można podać wiele: --module A --module B")
    p.add_argument("--json", action="store_true", help="Drukuj zdarzenia jako JSON (jedna linia na update)")
    p.add_argument("--pool", help="Filtruj tylko dany pool, np. P4")
    p.add_argument("--only", choices=["v", "s", "u", "n", "x", "t"], help="Filtruj tylko wybrany kanał")
    p.add_argument("--raw-ws", action="store_true", help="Wypisuj surowe eventy WS bez spłaszczania")
    p.add_argument("--no-diff", action="store_true", help="Nie wypisuj zmian (strzałek) na STDOUT")
    p.add_argument("--log-file", help="Zapisuj zdarzenia do JSONL (1 linia = 1 event)")
    p.add_argument("--debug", action="store_true", help="Więcej logów")
    p.add_argument("--quiet", action="store_true", help="Mniej logów")
    return p


def main() -> None:
    """Main.

    Returns:
    TODO.
    """
    parser = build_parser()
    args = parser.parse_args()
    try:
        code = asyncio.run(run(args))
    except KeyboardInterrupt:
        code = 130
    raise SystemExit(code)


if __name__ == "__main__":
    main()
