"""Module src/pybragerone/cli/ha_blueprint.py."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from ..core.client import BragerApiClient

try:
    from ..parsers.live_glue import build_ha_blueprint_live
except Exception as e:
    raise SystemExit(f"Missing parsers: {e}") from None

def build_parser() -> argparse.ArgumentParser:
    """Build parser.

    Returns:
    TODO.
    """
    p = argparse.ArgumentParser(
        prog="pybragerone-ha-blueprint",
        description="Generate Home Assistant blueprint using live web assets (online)"
    )
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--module", required=True)
    p.add_argument("--lang", default=None)
    p.add_argument("--base-url", default="https://one.brager.pl")
    p.add_argument("--out", default="-")
    return p

async def _run(args) -> int:
    """Run.

    Args:
    args: TODO.

    Returns:
    TODO.
    """
    async with BragerApiClient() as api:
        await api.login(args.email, args.password)
        bp = await build_ha_blueprint_live(api.session, args.module, lang=args.lang or "pl", base_url=args.base_url)
        data = json.dumps(bp, ensure_ascii=False, indent=2)
        if args.out in ("-", "stdout", ""):
            print(data)
        else:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(data)
    return 0

def main() -> int:
    """Main.

    Returns:
    TODO.
    """
    parser = build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
