# py-bragerone

Python client library for [one.brager.pl](https://one.brager.pl).

## Features

- **REST API**: login, list modules, fetch parameters snapshot  
- **WebSocket (Socket.IO)**: real-time parameter & activity changes  
- **Labels cache**: human-readable names, units and enums (lazy + persistent)  
- **Gateway**: thin facade for Home Assistant integrations or console usage  
- **CLI**: `bragerone run` for live session, `bragerone labels` for cache management  

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
    await g.start_ws()  # keeps listening until closed

asyncio.run(main())
```

## CLI
Run and listen for changes:
```bash
bragerone run \
  --email you@example.com \
  --password secret \
  --object-id 439 \
  --lang en \
  --log-level DEBUG
```

Manage labels cache:
```bash
# map param to alias
bragerone labels set-param P6 7 parameters.PARAM_7 --lang en

# alias → label translation
bragerone labels set-alias parameters.PARAM_7 "Pump activation temperature" --lang en

# param → unit id
bragerone labels set-param-unit P6 7 0 --lang en

# unit label
bragerone labels set-unit-label 0 "°C" --lang en

# enum map
bragerone labels set-unit-label 6 '{"11":"Return protection","12":"Heat exchanger"}' --lang en

# show current cache
bragerone labels show --lang en
```

## Development
Code under src/bragerone/
Tests in tests/
Run tests: pytest -q

### License
[MIT](LICENSE.md) © MarPi82

