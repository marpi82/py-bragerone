# py-bragerone

Python client library for [one.brager.pl](https://one.brager.pl).

Features:
- **REST API**: login, list modules, parameters snapshot
- **WebSocket (Socket.IO)**: real-time parameter changes
- **Labels**: human-readable names & units (safe fallbacks, parser WIP)
- **Gateway**: thin facade for HA/integrations or console usage

## Install

```bash
pip install py-bragerone
```
## Quick start
```python
import asyncio
from bragerone.gateway import Gateway

async def main():
    g = Gateway(email="you@example.com", password="secret", object_id=439, lang="en")
    await g.login()
    await g.pick_modules()
    await g.bootstrap_labels()
    await g.initial_snapshot()
    await g.start_ws()  # keeps listening

asyncio.run(main())
```

## CLI
```bash
python -m bragerone --email you@example.com --password secret --object-id 439 --lang en --log-level DEBUG
```

## DEV
Code under src/bragerone/
Tests in tests/
Run tests: pytest -q

### License
[MIT](LICENSE.md) © MarPi82

