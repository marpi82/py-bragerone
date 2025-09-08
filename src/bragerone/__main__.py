from __future__ import annotations
import argparse
import asyncio
import logging
from .gateway import Gateway

def setup_logging(level: str):
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--object-id", type=int, required=True)
    p.add_argument("--lang", default="en")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args()

    setup_logging(args.log_level)
    log = logging.getLogger("bragerone")

    g = Gateway(args.email, args.password, object_id=args.object_id, lang=args.lang)
    try:
        await g.login()
        await g.pick_modules()
        await g.bootstrap_labels()
        await g.initial_snapshot()
        await g.start_ws()
        while True:
            await asyncio.sleep(3600)
    finally:
        await g.close()

if __name__ == "__main__":
    asyncio.run(main())
