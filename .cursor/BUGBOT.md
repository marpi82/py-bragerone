# Bugbot rules — py-bragerone

Project-specific review gates for Cursor Bugbot (PR reviews and local `/review-bugbot`).
Prefer blocking correctness bugs over style already enforced by ruff/mypy/CI.

## Architecture

- REST primes state; WebSocket delivers **deltas only** and never replays full state. Flag reconnect paths that skip re-subscribe + re-prime.
- Flag blocking calls on the event loop; sync work must use `asyncio.to_thread()`. Prefer `asyncio.TaskGroup` for structured concurrency. Long-lived dispatch tasks must not die silently (`LOG.exception`; reserve `contextlib.suppress` for expected cancellation).
- Flag library modules that configure logging (root already attaches `NullHandler`). Entry points (`cli.py`, `__main__.py`) may use `print` / `basicConfig`.

## Public API

- Breaking changes to `BragerOneApiClient`, `BragerOneGateway`, or anything documented in `docs/reference/ha_integration.rst` are **blocking** unless the PR explicitly calls them out for `ha-bragerone`.
- Prefer Pydantic v2 DTOs (`ConfigDict`, `Field(alias=...)`). Avoid unjustified `Any` / bare `# type: ignore`.

## Catalog / parsers

- Upstream Brager JS assets change without notice. Changes to catalog/tree-sitter/i18n/menu parsers without strengthening `tests/test_catalog_*.py` (or equivalent) are blocking when the risk is parse breakage.
- Flag hardcoded translations or unit tables that bypass asset-driven i18n.

## Security & secrets

- Flag committed credentials, live dumps, or logs that leak tokens/passwords.
- Live-API tests must stay behind `@pytest.mark.needs_internet`.

## Quality

- English only in code, comments, and docstrings.
- Docs↔code drift is a defect: public behavior changes need `docs/` updates (Sphinx `-W` clean).
- Never hardcode the package version in `pyproject.toml` (hatch-vcs / CalVer from git tags).

## Non-blocking

- Pure formatting / import-order nits (CI handles them).
- `TODO` / `FIXME` that reference an existing issue number.
