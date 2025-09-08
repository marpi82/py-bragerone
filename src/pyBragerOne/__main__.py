from __future__ import annotations
import argparse
import asyncio
import logging
from .client import BragerOneClient

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--object-id", type=int, required=True)
    p.add_argument("--lang", default="pl")
    p.add_argument("--log-level", default="INFO")  # INFO / DEBUG
    return p.parse_args()

async def main():
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    c = BragerOneClient(args.email, args.password, object_id=args.object_id, lang=args.lang)
    try:
        #await c.login()
        await c.run_full_flow()  # etykiety + snapshot + WS + nasłuch
    finally:
        await c.close()

if __name__ == "__main__":
    asyncio.run(main())
