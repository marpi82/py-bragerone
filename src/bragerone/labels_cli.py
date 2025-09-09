from __future__ import annotations
import argparse
import json
from typing import Any
from .labels import LabelFetcher


# ---------- handlers ----------

def _cmd_set_param(args: argparse.Namespace) -> int:
    lf = LabelFetcher()
    lf.touch_param_alias(args.pool, args.number, args.alias, lang=args.lang)
    print(f"OK: mapped ({args.pool}, {args.number}) -> {args.alias} (lang={args.lang or 'all'})")
    return 0


def _cmd_set_alias(args: argparse.Namespace) -> int:
    lf = LabelFetcher()
    if not args.lang:
        print("ERROR: --lang is required for set-alias")
        return 2
    lf.touch_alias(args.alias, args.label, lang=args.lang)
    print(f"OK: alias {args.alias} = {args.label!r} (lang={args.lang})")
    return 0


def _cmd_set_param_unit(args: argparse.Namespace) -> int:
    lf = LabelFetcher()
    lf.touch_param_unit(args.pool, args.number, args.unit_id, lang=args.lang)
    print(f"OK: param ({args.pool}, {args.number}) uses unit_id={args.unit_id} (lang={args.lang or 'all'})")
    return 0


def _cmd_set_unit_label(args: argparse.Namespace) -> int:
    """
    Accept either:
      - plain string (e.g. "°C"), or
      - JSON object for enum (e.g. '{"10":"Off","11":"Return protection"}').
    """
    lf = LabelFetcher()
    if not args.lang:
        print("ERROR: --lang is required for set-unit-label")
        return 2

    raw = args.label
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("JSON provided but not an object")
        lf.touch_unit_def(args.unit_id, {str(k): str(v) for k, v in parsed.items()}, lang=args.lang)
        print(f"OK: enum unit {args.unit_id} set ({len(parsed)} items) (lang={args.lang})")
    except Exception:
        lf.touch_unit_def(args.unit_id, raw, lang=args.lang)
        print(f"OK: unit {args.unit_id} label = {raw!r} (lang={args.lang})")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    lf = LabelFetcher()
    lang = args.lang or "en"
    lf.ensure(lang)
    st = lf._by_lang.get(lang)
    if not st:
        print(f"No cache for lang={lang}")
        return 0
    print(json.dumps({
        "lang": lang,
        "aliases": st.aliases,
        "param_alias": st.param_alias,
        "param_unit": st.param_unit,
        "unit_defs": st.unit_defs,
    }, ensure_ascii=False, indent=2))
    return 0


# ---------- public entry ----------

def add_subparser(parent: argparse._SubParsersAction) -> None:
    """Attach `labels` subcommands to an existing parser."""
    pl = parent.add_parser("labels", help="Labels cache tools (aliases, units/enums)")
    lsub = pl.add_subparsers(dest="labels_cmd", required=True)

    lp = lsub.add_parser("set-param", help="Map (pool,number) to alias")
    lp.add_argument("pool")
    lp.add_argument("number", type=int)
    lp.add_argument("alias")
    lp.add_argument("--lang", default=None)
    lp.set_defaults(func=_cmd_set_param)

    la = lsub.add_parser("set-alias", help="Set alias -> label for given language")
    la.add_argument("alias")
    la.add_argument("label")
    la.add_argument("--lang", required=True)
    la.set_defaults(func=_cmd_set_alias)

    lpu = lsub.add_parser("set-param-unit", help="Attach unit_id (from 'u') to a parameter")
    lpu.add_argument("pool")
    lpu.add_argument("number", type=int)
    lpu.add_argument("unit_id")
    lpu.add_argument("--lang", default=None)
    lpu.set_defaults(func=_cmd_set_param_unit)

    lul = lsub.add_parser(
        "set-unit-label",
        help="Set unit label (plain text) or enum map (JSON object)"
    )
    lul.add_argument("unit_id")
    lul.add_argument(
        "label",
        help='Plain text (e.g. "°C") or JSON for enum (e.g. \'{"10":"Off","11":"Return"}\')'
    )
    lul.add_argument("--lang", required=True)
    lul.set_defaults(func=_cmd_set_unit_label)

    ls = lsub.add_parser("show", help="Show cached labels for a language")
    ls.add_argument("--lang", required=True)
    ls.set_defaults(func=_cmd_show)

