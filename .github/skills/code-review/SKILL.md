---
name: code-review
description: Review checklist for py-bragerone pull requests. Use when reviewing PRs to verify the REST prime / WebSocket delta contract, async safety, mypy strict compliance, public API stability, tests, and security.
---

# Code Review — py-bragerone

Review procedure for pull requests to this library. Work through every section; only comment on real issues, with file/line references and a concrete suggested fix.

## 1. Correctness — data-flow contract

- [ ] REST **prime** still happens at startup and after every reconnect; WebSocket is deltas-only.
- [ ] `EventBus` subscribers can't be killed by an unhandled exception (catch and log; suppress only expected outcomes like cancellation).
- [ ] Token refresh in `BragerOneApiClient` is transparent; no caller-side token management added.
- [ ] Meta-only events (`value=None`) handling unchanged — `ParamStore` ignores them by design.

## 2. Async & concurrency

- [ ] No blocking calls in the event loop (sync httpx/requests, `time.sleep`, file I/O in coroutines).
- [ ] New background tasks: gateway-owned work uses `BragerOneGateway._spawn()` (tracked, cancelled on shutdown); other detached work uses `utils.spawn()`. `asyncio.TaskGroup` is for structured concurrency only — its scope waits for all child tasks, so it is not a fire-and-forget mechanism.
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
- [ ] No broad `except Exception` without logging; no silent `pass` — except explicitly documented soft-fail contracts (e.g. `ParamStore.upsert()` returns `None` on malformed keys by design).

## 6. Resolver / catalog parity (empirical Copilot P0–P1)

Simulate concrete register and payload values; do not stop at "looks plausible".

- [ ] **Transforms on dereferenced readings**: register readings still get unit scale/offset; STATUS-label normalization must not drop/corrupt fractional values (`21.5` / `"21.5"`).
- [ ] **Selector shape parity**: address string, object, list, and nested-under-`value` forms resolve consistently; usable-reading checks match `_resolve_rule_payload()` (skip whitespace / rejectable scalars).
- [ ] **Condition coercion**: numeric strings, bools, bit/mask, and non-finite values share the same rules between visibility and value resolution.
- [ ] **Dependencies**: `mapping.inputs` / refresh tracking includes object-valued `value` and `command` slots, not only lists; computed cards stay on the dependency-driven refresh path.
- [ ] **Catalog merge/priority**: overlapping routes merge parameter sections (do not replace wholesale); layers apply in ascending priority; standalone device menus must not `break` collection of later devices; device refs prefer REST construction over stale JS shortcuts.
- [ ] **Hot-path cost**: avoid full `ParamStore.flatten()` on every ordinary resolve; snapshot only for `raw.any` (or read referenced addresses).
- [ ] **Catalog parse / regex**: watch ReDoS in new patterns; heavy sync parse work stays off the event loop (`asyncio.to_thread`).

## 7. Tests

- [ ] New behavior covered; HTTP mocked with pytest-httpx; suite passes offline.
- [ ] Live-API tests marked `@pytest.mark.needs_internet`.
- [ ] Parser changes (catalog pure JS parser) include malformed-input fixtures.
- [ ] Resolver/catalog fixes include **regression fixtures with concrete register/payload values** (counterexamples).
- [ ] Project coverage floor (80%) and **100% patch** (`uv run --group dev --group test poe patch-cov`, branch coverage + codecov excludes; CLI omitted) are not weakened.

## 8. Security & secrets

- [ ] No credentials, tokens, or personal account data in code, tests, fixtures, or logs.
- [ ] Secrets never logged — check debug logging of auth payloads and WS frames.
- [ ] New HTTP surface validates/sanitizes server data through Pydantic models.

## 9. Docs

- [ ] Public behavior changes reflected in `docs/` (Sphinx builds with `-W` in CI).
- [ ] README.rst examples still valid if touched surface is covered there.
- [ ] **Code↔docs drift (both directions)**: if the PR changes CLI flags/env vars, public API, parameter addressing, or any documented behavior, verify that `docs/**/*.rst`, `README.rst`, and `examples/` still match the code — flag stale claims, commands, or examples. Conversely, for docs-only PRs, spot-check the documented behavior against the actual code in `src/pybragerone/` and flag mismatches.
- [ ] Changelog: retain existing Unreleased notes when adding a new fix entry.

## Stack awareness

- Before flagging stale references or inconsistencies, check whether the PR belongs to a stack: look for "Stacked on #NNN" links or cross-referenced PRs in the PR body and timeline, and fetch those PRs via the GitHub MCP server. If the PR is part of a stack, review the layer in the context of the whole stack — the fix may already exist in a linked layer.

## How to report

- One comment per issue. Use severity to triage what you report — blocker (contract break, data loss, crash), major (CI gate, typing, missing tests), minor (style, docs, naming) — and report blockers/majors first. Treat this as prioritization guidance, not a required comment format.
- Prefer suggesting the smallest change that fits existing patterns over proposing new abstractions.
- Include a concrete counterexample (register/payload values → expected vs actual) and ask for a regression test when behavior is wrong.
- If the PR mentions an issue, use the GitHub MCP server to read it and verify the change actually addresses it.
