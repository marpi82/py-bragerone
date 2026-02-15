# Scripts

Utility scripts for development and system setup.

## Available Scripts

### Setup

- `setup_host_env.sh` - Configure development environment (installs uv, sets up git hooks)
- `perf_bench.py` - Run micro-benchmarks and compare timing reports

	Includes:
	- API command dispatch micro-benchmarks
	- Asset parser benchmark (`catalog_param_map_parsing`) when fixture files are present in `.cache/`
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

# Run micro-benchmarks and save latest report
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
```

## Note

This directory is kept minimal. Old development/debug scripts have been moved to `_archive/old_scripts/`.
