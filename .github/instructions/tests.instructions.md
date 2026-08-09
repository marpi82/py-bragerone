---
applyTo: "tests/**/*.py"
---

# Test suite rules

1. **Async**: `asyncio_mode = "auto"` — async test functions need no marker; do not add event-loop fixtures.
2. **HTTP mocking**: use **pytest-httpx** (`httpx_mock` fixture), not `aioresponses` (the library uses httpx, not aiohttp).
3. **No network by default**: tests must pass offline. Anything hitting the real API needs `@pytest.mark.needs_internet`.
4. **Determinism**: no wall-clock sleeps; use `asyncio.Event`/queues to synchronize. Inject clocks for time logic (freezegun is not a project dependency — don't introduce it without adding it first).
5. **Coverage**: pre-push gate is `--cov-fail-under=80`; new modules should ship with meaningful tests, not just line coverage.
6. **Style**: same ruff/mypy rules as `src/`; fixtures in `conftest.py` stay minimal.
7. **Naming**: `tests/test_<area>_<aspect>.py`, flat layout.
