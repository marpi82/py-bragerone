# py-bragerone Copilot Instructions

## Critical AI Guidelines

### Core Principles
1. **Always refer to the latest documentation** - Check docs/ directory for current architecture and patterns
2. **100% English code** - All files, comments, docstrings must be in English. Auto-translate any Polish code/comments to English
3. **Base on existing files** - Never create code blindly. When uncertain, ask instead of guessing
4. **Home Assistant focus** - This library's primary goal is HA integration. Anticipate needed mechanisms and methods for HA components

### Language & Type Requirements (Python 3.13.2+)

**Threading/Concurrency:**
- Never rely on GIL; protect mutable shared structures (locks/immutable/actor-style)
- Avoid "clever" optimizations assuming thread sequentiality (PEP 703 compatible)

**Type Annotations:**
- Write complete annotations (PEP 484/585/604/695)
- Use `typing.get_type_hints()` for introspection, never raw `__annotations__` (PEP 649 future-proof)
- Pass `mypy --strict` with no compromises

**Project Configuration:**
- Follow PEP 621 for `pyproject.toml` metadata

**API Stability:**
- Never use deprecated/removed elements from earlier Python versions
- Regularly check "What's New" and "Porting to" guides for 3.13/3.14

**Distribution/CI:**
- Build on Python 3.13.2, test on latest 3.13
- Must be compatible with `homeassistant>2025.5.0`
- For single-file scripts, consider PEP 723 (e.g., with `uv`)
- **Tooling baseline**: uv for dependency management, Hatch/Hatchling for builds

**Documentation:**
- Sphinx-compatible API docs required
- Use Google-style docstrings (enforced by ruff)
- Document as much code as possible

## Project Overview

**py-bragerone** is an async Python library for the BragerOne cloud/realtime API, primarily designed for Home Assistant integration. It combines REST (httpx) with WebSocket (Socket.IO) for realtime updates using an event-driven architecture.

**Key principle**: REST provides snapshots ("prime"), WebSocket provides deltas. Prime is mandatory at startup and after reconnect—WebSocket never provides initial state.

## Architecture Components

### 1. Three-Layer Data Flow

```
BragerOneApiClient (REST) ──┐
                            ├──> BragerOneGateway ──> EventBus ──> ParamStore
RealtimeManager (WS) ───────┘                                  └──> HA entities/CLI
```
- **BragerOneApiClient** (`src/pybragerone/api/client.py`): Async REST client with token auto-refresh, HTTP cache (ETag/Last-Modified), and Pydantic models
- **RealtimeManager** (`src/pybragerone/api/ws.py`): Socket.IO wrapper, handles reconnect, namespace `/ws`
- **BragerOneGateway** (`src/pybragerone/gateway.py`): Orchestrates login → WS connect → modules.connect → subscribe → prime
- **EventBus** (`src/pybragerone/models/events.py`): Multicast event bus with per-subscriber FIFO queues, publishes `ParamUpdate` events

### 2. ParamStore (Unified Store)

**ParamStore** (`src/pybragerone/models/param.py`) provides two usage modes:

- **Lightweight mode**: Basic key→value store (e.g., `{"P4.v1": 20}`) for runtime. Fast, minimal overhead. Ignores meta-only events.
- **Asset-aware mode**: Optional integration with `LiveAssetsCatalog` for rich metadata (labels/units/enums). Used during HA config flow to build entity descriptors.

Choose lightweight for runtime performance, asset-aware for config/bootstrap when you need i18n and metadata.

### 3. Parameter Addressing

Format: `P<n>.<chan><idx>` (e.g., `P4.v1`, `P5.s40`)

Channels:
- `v`: value (primary reading/setpoint)
- `s`: status (bitmask for binary sensors)
- `u`: unit code or enum index
- `n`/`x`: min/max
- `t`: type

Example: Status bit handling reads mask from `P5.s40`, extracts single bit → binary entity.

### 4. Asset Catalog & tree-sitter

`LiveAssetsCatalog` (`src/pybragerone/models/catalog.py`) parses live JavaScript assets from BragerOne web app using **tree-sitter** to extract:
- Menu routes and parameter mappings
- i18n translations (labels/units/enums)
- Permission schemas

This enables dynamic entity discovery without hardcoding.

## Development Workflows

### Setup & Dependencies

```bash
# Install dependencies with uv (Python 3.13.2+)
uv sync --group dev --group test --group docs --locked

# Or via poe helper
uv run --group dev poe bootstrap
```

**Critical**: This project uses `hatch-vcs` for CalVer versioning from git tags. Version is computed at build time, not stored in pyproject.toml.

### Code Quality Tasks (via Poe)

All tasks run through `poethepoet` (see `[tool.poe.tasks]` in pyproject.toml):

```bash
# Code Quality
uv run --group dev poe fmt       # Format with ruff
uv run --group dev poe lint      # Lint with ruff --fix
uv run --group dev poe fix       # Run lint + format together
uv run --group dev poe typecheck # mypy strict mode
uv run --group dev poe all       # Run fmt + lint + typecheck

# Security
uv run --group dev poe bandit    # Security linting with bandit
uv run --group dev poe semgrep   # Semgrep security checks
uv run --group dev poe pip-audit # Audit dependencies for vulnerabilities
uv run --group dev poe security  # Run all security checks

# Testing
uv run --group dev --group test poe test     # pytest (poe lives in `dev`)
uv run --group dev --group test poe cov      # pytest with coverage

# Full Validation
uv run --group dev --group test poe validate  # Run fmt + lint + typecheck + security + test (pytest lives in `test`)
```

Or use VS Code tasks (defined in `.vscode/tasks.json`):
- **uv: sync dev+test+docs** - Initial environment sync
- **Quality: format / lint / typecheck** - Code quality automation
- **Security: Bandit/Semgrep/pip-audit** - Individual security checks
- **Security: All security checks** - Run all security tools
- **Tests: run / coverage** - Run pytest (with optional coverage)
- **Validate: Full validation** ⭐ **(default build task)** - Complete validation (quality + security + tests)
- **Build dist** - Build wheels/sdist via Hatch
- **Docs: build/serve** - Documentation

**Pre-commit hooks**: Run `pre-commit install` to enable automatic checks before commits. Config in `.pre-commit-config.yaml`.

### Testing Conventions

- **pytest-asyncio** with `asyncio_mode = "auto"` (see `pyproject.toml`)
- Mock HTTP via **pytest-httpx** (`httpx_mock` fixture); in catalog tests fake or mock the injected API client's `get_bytes()` method
- Property-based tests with **Hypothesis** where input space is large
- Live API tests marked with `@pytest.mark.needs_internet` (see `conftest.py`)
- Coverage target: run `uv run --group dev --group test poe cov` for term-missing report (poe lives in `dev`)

Key test patterns:
- `tests/test_api.py`: REST client tests (mocked)
- `tests/test_catalog_permissions.py`: Asset parser resilience
- `tests/test_param_store_i18n_integration.py`: Store + i18n integration

### CLI for Debugging

```bash
pybragerone-cli --email user@example.com --password "***"
```

This launches an interactive gateway session showing live parameter updates. Use for:
- Verifying WS connectivity
- Inspecting parameter flows
- Testing module selection logic

### Documentation

Built with Sphinx + Furo theme:

```bash
uv run --group dev --group docs poe docs-build   # Build to docs/_build/html (poe lives in `dev`)
uv run --group docs poe docs-serve   # Serve on localhost:8000
```

Documentation includes:
- `docs/architecture/overview.rst` / `docs/architecture/operations.rst`: Architecture and runtime operations
- `docs/reference/ha_integration.rst`: HA integration contract (entity descriptors, ParamStore usage)
- `docs/reference/parameter_format.rst`: Parameter addressing (`P<n>.<chan><idx>`) reference
- `docs/guides/typing.rst` / `quality.rst` / `tests_guidelines.rst`: Contributor standards

## Project-Specific Conventions

### 1. Strict Typing (mypy)

All code must pass `mypy --strict`. Use explicit types, no `Any` without justification. Pydantic plugin enabled.

### 2. Ruff Configuration

- Line length: 130 chars
- Docstrings: Google style (enforced by ruff's `pydocstyle`)
- Import sorting: automatic via ruff (no isort needed separately)
- Selected rules: E, F, W, I, D, UP, RUF, SIM, B

### 3. Async Patterns

- Use `asyncio.TaskGroup` for structured concurrency (Python 3.13+)
- Never block event loop; use `asyncio.to_thread()` for sync operations
- EventBus subscribers: always wrap in try/except to prevent task death

Pattern from `gateway.py`:
```python
try:
    res = cb(*args, **kwargs)
    if asyncio.iscoroutine(res):
        await res
except Exception:
    LOG.exception("Callback error")  # never let a callback kill the dispatcher
```

### 4. Error Handling

- REST errors raise `ApiError` with status/data/headers
- WS errors log and attempt reconnect
- ParamStore upserts never fail (returns None on bad key format)

### 5. Module Entry Points

- `pybragerone`: Main module entry (see `__main__.py`)
- `pybragerone-cli`: Interactive CLI (see `cli.py`)
- `pybragerone-parsers`: Asset parser utilities (if implemented)

## Integration Points

### Home Assistant Flow

**Config Flow** (no WS needed):
1. REST login → select object + modules
2. Prime parameters via REST → ingest to ParamStore (asset-aware mode)
3. Parse `parameterSchemas` + i18n via `LiveAssetsCatalog` → build entity descriptors
4. Store descriptors in `config_entry.data`

**Runtime**:
1. Start Gateway + ParamStore subscriber (lightweight mode)
2. WS connect → `modules.connect` → subscribe
3. Prime via REST → EventBus → ParamStore filled
4. HA entities read from ParamStore on `ParamUpdate` events

**Reconnect**: Re-subscribe → prime → continue (WebSocket does not replay state).

### External Dependencies

- **BragerOne API** (`io.brager.pl`): REST + Socket.IO endpoints
- **Asset catalog**: Fetched from web app at runtime for i18n/metadata
- **tree-sitter**: Parses JavaScript assets (bundled language grammar via `tree-sitter-javascript`)

## Common Gotchas

1. **Missing prime**: Always call `api.get_parameters()` after WS subscribe—never assume initial state from WS.
2. **Meta-only events**: EventBus publishes all, but ParamStore ignores events with `value=None`. Check this when debugging missing updates.
3. **Token refresh**: `BragerOneApiClient` handles token refresh automatically; don't manually manage tokens unless using `CLITokenStore`.
4. **CalVer versioning**: Don't edit version in pyproject.toml—it's managed by git tags via `hatch-vcs`.
5. **Parameter addressing**: Use format `P<n>.<chan><idx>` (e.g., `P4.v1`, `P5.s40`). ParamStore.upsert returns None on bad key format.

## CI/CD & GitHub Workflows

The project uses GitHub Actions for automation (`.github/workflows/`):

- **ci.yml**: Lint (ruff), typecheck (mypy), tests (pytest), secrets scan (gitleaks)
- **release.yml**: Automated releases with CalVer tags, PyPI/TestPyPI publishing
- **docs.yml**: Sphinx documentation build and deployment to GitHub Pages

**Dynamic versioning**: Version comes from git tags via `hatch-vcs`. No extra CI setup is required beyond installing Hatch/uv.

## AI Agent Configuration Files

This project provides instructions for multiple AI coding assistants:

- **GitHub Copilot**: `.github/copilot-instructions.md` (this file)
- Future: Can add `.cursorrules`, `.windsurfrules`, or similar for other agents

These files should be kept in sync and updated as the architecture evolves.

## Quick References

- **Architecture**: `docs/architecture/overview.rst`
- **HA integration contract**: `docs/reference/ha_integration.rst`
- **API models**: `src/pybragerone/models/api/`
- **Key examples**: README.rst (ParamStore usage patterns)

## Code Review Priorities

When reviewing pull requests, prioritize (details in `.github/skills/code-review/SKILL.md`):

1. **Prime/WS contract**: REST prime is mandatory at startup and after every reconnect; WebSocket must never be treated as a source of initial state.
2. **Async safety**: no blocking calls in the event loop (`asyncio.to_thread` for sync I/O); dispatcher/subscriber tasks must never die silently (wrap in `try`/`except` and log with `LOG.exception`; reserve `contextlib.suppress` for expected outcomes like cancellation); structured concurrency via `asyncio.TaskGroup`.
3. **mypy --strict compliance**: no new `Any` without justification, no `# type: ignore` without a comment explaining why.
4. **Public API stability**: `pybragerone.__all__` (`BragerOneApiClient`, `BragerOneGateway`) and everything documented in `docs/reference/ha_integration.rst` is consumed by the ha-bragerone integration—flag breaking changes.
5. **Pydantic v2 patterns**: `ConfigDict`, `Field(alias=...)`, `model_validate`; do not introduce v1 idioms.
6. **Tests**: new behavior needs tests (pytest-httpx for HTTP, `asyncio_mode=auto`); live-API tests must be marked `@pytest.mark.needs_internet`.
