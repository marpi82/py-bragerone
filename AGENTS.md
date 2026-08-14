# AGENTS.md — py-bragerone

Async Python library for the BragerOne cloud/realtime API (REST + Socket.IO), designed primarily as the data layer for the `ha-bragerone` Home Assistant integration.

## Project shape

- **Layout**: src-layout, single package `src/pybragerone/`, tests in `tests/` (flat `test_*.py`).
- **Python**: `>=3.13.2,<3.15` (CI tests on 3.13).
- **Dependencies**: **uv** (`uv.lock` committed). Groups: `dev` (includes security tools: bandit, pip-audit), `test`, `docs`, `fuzz`.
- **Build**: hatchling + **hatch-vcs** — version is CalVer derived from git tags; never hardcode a version in `pyproject.toml`.

## Common commands

```bash
uv sync --group dev --group test --group docs --locked   # full environment
uv run --group dev poe fmt        # ruff format
uv run --group dev poe lint       # ruff check --fix
uv run --group dev poe typecheck  # mypy --strict
uv run --group dev --group test poe test      # pytest (poe lives in `dev`)
uv run --group dev --group test poe cov       # pytest + coverage
uv run --group dev --group test poe bench     # micro-benchmarks (`pytest --codspeed`, no SaaS reporting locally)
uv run --group dev --group test poe validate   # fmt + lint + typecheck + security + test (needs both groups: pytest lives in `test`)
uv build                          # wheel + sdist
```

Pre-commit hooks exist; a coverage gate (`--cov-fail-under=80`) runs on pre-push. CI uploads `coverage.xml` to Codecov (`codecov-commenter` on PRs). Patch coverage target is 100%; project coverage is informational — the 80% floor stays on pre-push. Coverage omits CLI entrypoints (`cli.py`, `__main__.py`); those are not the library runtime used by Home Assistant.

## Architecture in one paragraph

REST **primes** the state (snapshots); WebSocket delivers **deltas only** and never replays state — after every reconnect you must re-subscribe and re-prime. `BragerOneApiClient` (`src/pybragerone/api/client.py`, httpx, token auto-refresh, ETag cache) and `RealtimeManager` (`src/pybragerone/api/ws.py`, python-socketio `/ws` namespace) feed `BragerOneGateway` (`src/pybragerone/gateway.py`), which publishes `ParamUpdate` events on the `EventBus` (`src/pybragerone/models/events.py`) into `ParamStore` (`src/pybragerone/models/param.py`). `LiveAssetsCatalog` (`src/pybragerone/models/catalog.py`) parses live JS web-app assets with tree-sitter for menus/i18n/permissions — used at config time, not hot runtime.

Parameter addressing: `P<n>.<chan><idx>` (channels: `v` value, `s` status bitmask, `u` unit/enum, `n`/`x` min/max, `t` type).

## Non-negotiable conventions

1. **English only** in code, comments, docstrings.
2. **mypy --strict** must pass (pydantic plugin enabled). No `Any`, no `# type: ignore` without justification.
3. **Ruff** (`line-length = 130`, rules `E,F,W,I,D,UP,RUF,SIM,B,S`, Google-style docstrings) must pass; run `poe fix` before committing.
4. **Async-first**: never block the event loop; `asyncio.to_thread()` for sync work; `asyncio.TaskGroup` for structured concurrency; long-lived dispatch tasks must not die silently (catch and log with `LOG.exception`; reserve `contextlib.suppress` for expected outcomes like cancellation).
5. **Pydantic v2** for DTOs (`ConfigDict`, `Field(alias=...)`, generics like `ApiResponse[T]`).
6. **Public API** is `pybragerone.__all__` = `["BragerOneApiClient", "BragerOneGateway"]` plus what `docs/reference/ha_integration.rst` documents. Breaking it breaks the HA integration — call it out explicitly in PRs.
7. **Logging**: stdlib `logging.getLogger(__name__)`; the library root attaches a `NullHandler` — never configure logging in library modules. Entry points are exempt: `cli.py` intentionally uses `print()` and `logging.basicConfig`.

## Testing

- pytest with `asyncio_mode = "auto"`; mock HTTP with **pytest-httpx** (`httpx_mock`).
- Live-API tests must be marked `@pytest.mark.needs_internet`.
- Hypothesis for property-based tests; fuzz harness lives in `fuzz/` (atheris).
- Parser resilience (catalog/tree-sitter) is heavily tested in `tests/test_catalog_*.py` — keep it that way; upstream JS assets change without notice. Optional captured dumps live in `tests/assets/{index,params,menus,i18n}/` (`*.js` gitignored) and are parsed by `tests/test_catalog_captured_assets.py` (skipped when empty). Scheduled watch: `.github/workflows/upstream-assets.yml` (unauthenticated `/system/version` + `index-*.js` fingerprint; when it parses, also requires language config, units descriptor table, and `units` i18n — not a `ci.yml` gate).

## Docs

Sphinx + Furo; `uv run --group dev --group docs poe docs-build` (poe lives in `dev`). Sphinx runs with `-W` in CI — warnings are errors. Update `docs/` when changing public behavior, and treat docs↔code drift in either direction as a defect: docs must describe the code as it is.

## CI gates (`.github/workflows/ci.yml`)

Independent jobs run in parallel: `secrets` (gitleaks), `dependency-review`, `security`, `quality` (ruff check + format, mypy), `tests` (pytest 3.13), `docs-verify` (Sphinx `-W`). `build` (hatch) gates on all of them except `dependency-review` (`needs: [secrets, security, quality, tests, docs-verify]`). pip-audit runs as an artifact-producing advisory job (`continue-on-error: true`, not a blocking gate); CodeQL and OpenSSF Scorecard run separately. A scheduled **Upstream assets** workflow (`.github/workflows/upstream-assets.yml`) probes public BragerOne JS without login; it does not block PRs.

## Cursor Cloud specific instructions

The Cloud Agent environment is provisioned by the committed `.cursor/environment.json` in this repo (the environment's primary repo). Its `install` script installs a pinned `uv` (0.12.3) to `~/.local/bin` — already on `PATH` via the base image's shell profile — when it is absent, then runs `uv sync --locked` for both checked-out repos: `py-bragerone` pinned to `--python 3.13`, and the sibling `ha-bragerone` (Python 3.14, resolved from its own lockfile). After that the environment is ready — use the `uv run ... poe <task>` commands documented above (no extra install steps).

- **Pin Python 3.13 to match CI.** `requires-python` also allows 3.14, so a bare `uv sync` picks the newest interpreter (3.14) and diverges from the CI matrix (3.13). Always pass `--python 3.13` (the update script already does). To rebuild from scratch: `rm -rf .venv && uv sync --group dev --group test --group docs --locked --python 3.13`.
- **This is a library, not a long-running service.** There is no dev server. "Running the app" means the diagnostic CLI (`uv run pybragerone-cli`) or the example scripts in `examples/`.
- **CLI / examples need live credentials + internet.** They log into the BragerOne (or TiSConnect) cloud using `PYBO_EMAIL` / `PYBO_PASSWORD` (see `.env.example`); without them the CLI exits early with either `Missing email: set PYBO_EMAIL or pass --email.` or `Missing password: set PYBO_PASSWORD, pass --password, or run interactively to be prompted.` All offline development — lint, mypy, pytest, build, docs — runs with no credentials. Live-API tests are marked `needs_internet` and skip automatically offline.
- **Docs build doesn't need Graphviz** despite the README note; `docs/conf.py` doesn't load the graphviz extension. Match CI with `uv run --group dev --group docs sphinx-build -W -b html docs docs/_build/html`.
