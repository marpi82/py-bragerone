# Scripts

Utility scripts for development and system setup.

## Available Scripts

### Setup

- `setup_host_env.sh` - Configure development environment (installs uv, sets up git hooks)
- `perf_bench.py` - Local wall-time micro-benchmarks, baseline compare, and real startup timing
- `check_upstream_assets.py` - Unauthenticated probe of BragerOne `/system/version` + live `index-*.js` (used by the scheduled Upstream assets workflow). When the fingerprint changes (or `--always-parse`), the probe also requires a non-empty language config, units descriptor table, and `units` i18n namespace.
- `live_contract.py` - Authenticated structural catalog contract for the self-hosted `bragerone-live` runner. Seeds `/var/lib/gha/baselines/live_contract.json` on first success; later runs compare structure only (no live register values).
- `probe_menu_routes.py` - Authenticated live probe of module menu routes, panel groups, and route visibility diagnostics (issue #192). Requires ``PYBO_*`` credentials in ``.env``.

CPU-bound dispatch/catalog cases also live as pytest tests in `tests/test_bench_micro.py`
(`uv run --group dev --group test poe bench` / `pytest --codspeed`). This script remains the
tool for:

- API command dispatch wall-time loops (optional `.cache/` catalog fixtures)
- Real startup benchmark (`startup`) with CLI-like phases:
  - auth
  - WS connect/bind/subscribe
  - prime (parameters/activity)
  - store ingestion
  - menu/route parsing
  - panel group build
  - describe/resolve all symbols

## Usage

```bash
# Run setup script
./scripts/setup_host_env.sh

# Run pytest CPU micro-benchmarks (CodSpeed plugin; no SaaS reporting locally)
uv run --group dev --group test poe bench

# Run wall-time micro-benchmarks and save latest report
uv run --group dev poe perf

# Compare latest run with baseline report
uv run --group dev poe perf-compare

# Run real startup benchmark (requires credentials/object)
uv run --group dev python scripts/perf_bench.py startup \
	--email "$PYBO_EMAIL" \
	--password "$PYBO_PASSWORD" \
	--object-id "$PYBO_OBJECT_ID" \
	--modules "$PYBO_MODULES" \
	--all-panels \
	--repeats 1 \
	--output reports/perf/startup_latest.json

# If `.env` contains PYBO_EMAIL/PYBO_PASSWORD/PYBO_OBJECT_ID/PYBO_MODULES,
# you can omit those flags - the benchmark loads `.env` automatically.

# Compare startup benchmark against baseline
uv run --group dev python scripts/perf_bench.py compare \
	--baseline reports/perf/startup_baseline.json \
	--current reports/perf/startup_latest.json \
	--regression-threshold-percent 10

# Manual benchmark run with immediate comparison
uv run --group dev python scripts/perf_bench.py run \
	--loops 2000 \
	--output reports/perf/latest.json \
	--compare-to reports/perf/baseline.json

# Asset parsing benchmark uses local fixtures from .cache, e.g.:
# .cache/index-*.js
# .cache/PARAM_66-*.js
# .cache/URUCHOMIENIE_KOTLA-*.js
# .cache/COMMAND_MODULE_RESTART-*.js

# Public catalog watch (no login). Parses the live index when the fingerprint is new.
uv run python scripts/check_upstream_assets.py
uv run python scripts/check_upstream_assets.py --always-parse

# Live structural contract (needs PYBO_* on the process; self-hosted bragerone-live).
# First run with an empty baseline dir seeds live_contract.json and exits 0.
uv run python scripts/live_contract.py --write-current reports/live/contract.json
# Optional override:
# PYBO_BASELINE_DIR=/var/lib/gha/baselines uv run python scripts/live_contract.py
```

## Note

This directory is kept minimal. Old development/debug scripts have been moved to `_archive/old_scripts/`.
