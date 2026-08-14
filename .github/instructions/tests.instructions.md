---
applyTo: "tests/**/*.py"
---

# Test suite rules

1. **Async**: `asyncio_mode = "auto"` — async test functions need no marker; do not add event-loop fixtures.
2. **HTTP mocking**: use **pytest-httpx** (`httpx_mock` fixture), not `aioresponses` (the library uses httpx, not aiohttp).
3. **No network by default**: tests must pass offline. Anything hitting the real API needs `@pytest.mark.needs_internet` (skipped by default; opt in with `pytest --run-live`).
4. **Determinism**: no wall-clock sleeps; use `asyncio.Event`/queues to synchronize. Inject clocks for time logic (freezegun is not a project dependency — don't introduce it without adding it first).
5. **Coverage**: pre-push gate is `--cov-fail-under=80`; CI uploads to Codecov (patch target 100%, project informational). `cli.py` and `__main__.py` are omitted (CLI entrypoints, not library runtime). New modules should ship with meaningful tests, not just line coverage.
6. **Style**: same ruff/mypy rules as `src/`; fixtures in `conftest.py` stay minimal.
7. **Naming**: `tests/test_*.py`, flat layout (e.g. `test_api.py`, `test_catalog_parser.py`). CPU micro-benchmarks live in `tests/test_bench_micro.py` (`@pytest.mark.benchmark`; measure with `poe bench`).
8. **Captured assets**: drop live `*.js` dumps into `tests/assets/index`, `params`, `menus`, or `i18n` (gitignored; do not commit vendor JS). `tests/test_catalog_captured_assets.py` loops them through tree-sitter; empty dirs skip (no network). Scheduled CI watch is `.github/workflows/upstream-assets.yml` (no dumps, no login); when it parses, it requires language config, the units descriptor table, and the `units` namespace.
