# AGENTS.md — py-bragerone

Async Python library for the BragerOne cloud/realtime API (REST + Socket.IO), designed primarily as the data layer for the `ha-bragerone` Home Assistant integration.

## Project shape

- **Layout**: src-layout, single package `src/pybragerone/`, tests in `tests/` (flat `test_*.py`).
- **Python**: `>=3.13.2,<3.15` (CI tests on 3.13).
- **Dependencies**: **uv** (`uv.lock` committed). Groups: `dev` (includes security tools: bandit, semgrep, pip-audit), `test`, `docs`, `fuzz`.
- **Build**: hatchling + **hatch-vcs** — version is CalVer derived from git tags; never hardcode a version in `pyproject.toml`.

## Common commands

```bash
uv sync --group dev --group test --group docs --locked   # full environment
uv run --group dev poe fmt        # ruff format
uv run --group dev poe lint       # ruff check --fix
uv run --group dev poe typecheck  # mypy --strict
uv run --group test poe test      # pytest
uv run --group test poe cov       # pytest + coverage
uv run --group dev --group test poe validate   # fmt + lint + typecheck + security + test (needs both groups: pytest lives in `test`)
uv build                          # wheel + sdist
```

Pre-commit hooks exist; a coverage gate (`--cov-fail-under=80`) runs on pre-push.

## Architecture in one paragraph

REST **primes** the state (snapshots); WebSocket delivers **deltas only** and never replays state — after every reconnect you must re-subscribe and re-prime. `BragerOneApiClient` (`src/pybragerone/api/client.py`, httpx, token auto-refresh, ETag cache) and `RealtimeManager` (`src/pybragerone/api/ws.py`, python-socketio `/ws` namespace) feed `BragerOneGateway` (`src/pybragerone/gateway.py`), which publishes `ParamUpdate` events on the `EventBus` (`src/pybragerone/models/events.py`) into `ParamStore` (`src/pybragerone/models/param.py`). `LiveAssetsCatalog` (`src/pybragerone/models/catalog.py`) parses live JS web-app assets with tree-sitter for menus/i18n/permissions — used at config time, not hot runtime.

Parameter addressing: `P<n>.<chan><idx>` (channels: `v` value, `s` status bitmask, `u` unit/enum, `n`/`x` min/max, `t` type).

## Non-negotiable conventions

1. **English only** in code, comments, docstrings.
2. **mypy --strict** must pass (pydantic plugin enabled). No `Any`, no `# type: ignore` without justification.
3. **Ruff** (`line-length = 130`, rules `E,F,W,I,D,UP,RUF,SIM,B`, Google-style docstrings) must pass; run `poe fix` before committing.
4. **Async-first**: never block the event loop; `asyncio.to_thread()` for sync work; `asyncio.TaskGroup` for structured concurrency; long-lived dispatch tasks must not die silently (suppress + log).
5. **Pydantic v2** for DTOs (`ConfigDict`, `Field(alias=...)`, generics like `ApiResponse[T]`).
6. **Public API** is `pybragerone.__all__` = `["BragerOneApiClient", "BragerOneGateway"]` plus what `docs/reference/ha_integration.rst` documents. Breaking it breaks the HA integration — call it out explicitly in PRs.
7. **Logging**: stdlib `logging.getLogger(__name__)`; the library root attaches a `NullHandler` — never configure logging in library code.

## Testing

- pytest with `asyncio_mode = "auto"`; mock HTTP with **pytest-httpx** (`httpx_mock`).
- Live-API tests must be marked `@pytest.mark.needs_internet`.
- Hypothesis for property-based tests; fuzz harness lives in `fuzz/` (atheris).
- Parser resilience (catalog/tree-sitter) is heavily tested in `tests/test_catalog_*.py` — keep it that way; upstream JS assets change without notice.

## Docs

Sphinx + Furo; `uv run --group docs poe docs-build`. Sphinx runs with `-W` in CI — warnings are errors. Update `docs/` when changing public behavior.

## CI gates (`.github/workflows/ci.yml`)

gitleaks → dependency-review → ruff (check + format) → mypy → pytest (3.13) → Sphinx `-W` → hatch build. pip-audit runs as an artifact-producing advisory job (`continue-on-error: true`, not a blocking gate); CodeQL and OpenSSF Scorecard run separately.
