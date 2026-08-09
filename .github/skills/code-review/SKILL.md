# Code Review — py-bragerone

Review procedure for pull requests to this library. Work through every section; only comment on real issues, with file/line references and a concrete suggested fix.

## 1. Correctness — data-flow contract

- [ ] REST **prime** still happens at startup and after every reconnect; WebSocket is deltas-only.
- [ ] `EventBus` subscribers can't be killed by an unhandled exception (suppress + log).
- [ ] Token refresh in `BragerOneApiClient` is transparent; no caller-side token management added.
- [ ] Meta-only events (`value=None`) handling unchanged — `ParamStore` ignores them by design.

## 2. Async & concurrency

- [ ] No blocking calls in the event loop (sync httpx/requests, `time.sleep`, file I/O in coroutines).
- [ ] New background tasks use `utils.spawn()` or `asyncio.TaskGroup`.
- [ ] Mutable shared state is protected (locks/immutable/actor-style) — do not rely on the GIL.

## 3. Typing & style gates (CI runs these — flag what it can't catch)

- [ ] mypy `--strict`-clean; new `Any`/`cast`/`type: ignore` justified in a comment.
- [ ] Ruff: line length 130, Google docstrings on new public objects, import order.
- [ ] Pydantic v2 idioms only; `ApiResponse[T]` generic reused for new endpoints.
- [ ] English-only code, comments, docstrings.

## 4. Public API & versioning

- [ ] `pybragerone.__all__` and signatures used by ha-bragerone (see `docs/reference/ha_integration.rst`) unchanged, or the breaking change is explicitly called out in the PR description with a migration note.
- [ ] No version string edited in `pyproject.toml` (hatch-vcs/CalVer from git tags).
- [ ] New dependencies justified (license, maintenance, wheel availability) and added via uv.

## 5. Error handling

- [ ] REST errors surface as `ApiError` with status/data/headers.
- [ ] No broad `except Exception` without logging; no silent `pass`.

## 6. Tests

- [ ] New behavior covered; HTTP mocked with pytest-httpx; suite passes offline.
- [ ] Live-API tests marked `@pytest.mark.needs_internet`.
- [ ] Parser changes (catalog/tree-sitter) include malformed-input fixtures.
- [ ] Coverage gate (80%) not weakened.

## 7. Security & secrets

- [ ] No credentials, tokens, or personal account data in code, tests, fixtures, or logs.
- [ ] Secrets never logged — check debug logging of auth payloads and WS frames.
- [ ] New HTTP surface validates/sanitizes server data through Pydantic models.

## 8. Docs

- [ ] Public behavior changes reflected in `docs/` (Sphinx builds with `-W` in CI).
- [ ] README.rst examples still valid if touched surface is covered there.

## How to report

- One comment per issue, severity-tagged: **blocker** (contract break, data loss, crash), **major** (CI gate, typing, missing tests), **minor** (style, docs, naming).
- Prefer suggesting the smallest change that fits existing patterns over proposing new abstractions.
- If the PR mentions an issue, use the GitHub MCP server to read it and verify the change actually addresses it.
