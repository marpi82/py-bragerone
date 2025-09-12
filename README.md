[![CI](https://github.com/marpi82/py-bragerone/actions/workflows/ci.yml/badge.svg)](https://github.com/marpi82/py-bragerone/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-latest-blue)](https://marpi82.github.io/py-bragerone/)
[![PyPI version](https://img.shields.io/pypi/v/py-bragerone.svg)](https://pypi.org/project/py-bragerone/)
[![Python versions](https://img.shields.io/pypi/pyversions/py-bragerone.svg)](https://pypi.org/project/py-bragerone/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

# py-bragerone

Python client library for [one.brager.pl](https://one.brager.pl).
Provides a clean Gateway facade for REST + WebSocket access and **human-friendly labels/units** resolved live from the frontend bundles.

## Features

- **REST API**: login, pick device, initial snapshot
- **WebSocket (Socket.IO)**: live parameter & activity updates
- **Live labels from frontend**: fetch **parameters-*.js**, **units-*.js** and **PARAM_*.js** directly from the app bundles (no local JSON files)
- **ParamCatalog**: resolves pretty names, unit strings and enums; formats values for CLI/HA
- **Gateway**: thin orchestrator that exposes a simple interface (great for Home Assistant or CLI)
- **CLI**: `bragerone run` to watch a device, `bragerone labels` to inspect/override cache
- **Tested**: pytest + aioresponses; CI workflow; optional docs build

## Install

```bash
pip install py-bragerone
```
## Quick start
```python
import asyncio
from bragerone.gateway import Gateway

async def main():
    g = Gateway(email="you@example.com", password="secret", object_id=439, lang="pl")
    await g.login()
    await g.pick_modules()

    # Optional: prefetch assets (labels + units) before snapshot
    await g.bootstrap_labels()   # parses index & language chunks
    await g.bootstrap_units()    # parses PARAM_* meta
    # or just do it later with prefetch flag on first snapshot:
    # await g.initial_snapshot(prefetch_assets=True)

    await g.initial_snapshot()   # binds unit enums using current 'uN' values
    await g.start_ws()           # keep listening (Ctrl+C to exit)

asyncio.run(main())
```

## CLI
Run and listen for changes:
```bash
bragerone run \
  --email you@example.com \
  --password secret \
  --object-id 439 \
  --lang pl \
  --log-level DEBUG
```
Manage labels/units cache (overrides):
```bash
# param -> alias (parameters.PARAM_X)
bragerone labels set-param P6 7 parameters.PARAM_7 --lang pl

# alias -> translated label
bragerone labels set-alias parameters.PARAM_7 "Temperatura załączenia pompy" --lang pl

# param -> unit id
bragerone labels set-param-unit P6 7 0 --lang pl

# unit/plain label
bragerone labels set-unit-label 0 "°C" --lang pl

# enum map for a unit id (JSON)
bragerone labels set-unit-label 6 '{"11":"Ochrona powrotu","12":"Wymiennik ciepła"}' --lang pl

# show current cache
bragerone labels show --lang pl
```

##How labels & units are resolved
At runtime we parse the production index-*.js and discover language chunks.
For the selected language we download parameters-*.js and units-*.js and parse them into a catalog.
We additionally scan PARAM_*.js chunks to collect command/raw/status/componentType metadata for future use.
During snapshot binding, ParamCatalog connects parameters to their unit ids (e.g. u6) and formats values using unit strings or enum maps.
Everything is in-memory; no files are persisted.

## Development
Code under src/bragerone/
Tests in tests/
Run tests: pytest -q

##Common tasks
```bash
# create venv and install project + dev extras
make dev

# run linters & tests
make lint
make test

# build wheel/sdist
make build

# docs (if enabled)
make docs-serve
```
We use: ruff (lint/format), pytest, aioresponses, mypy (optional), and GitHub Actions (CI/Docs/Release).

##Releasing
Tag the repo (e.g. v0.2.6) and push. setuptools-scm will infer the version.
Our Release workflow builds wheels/sdist and can upload to PyPI when the ref is a tag.

## License
[MIT](LICENSE.md) © MarPi82

