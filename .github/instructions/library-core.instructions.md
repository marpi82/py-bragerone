---
applyTo: "src/pybragerone/**/*.py"
---

# Library core rules (apply to all of src/pybragerone)

When reviewing or changing library code:

1. **Prime/WS contract**: REST prime is mandatory at startup and after reconnect. Reject any change that treats Socket.IO payloads as initial state or skips re-prime on reconnect.
2. **Event-loop hygiene**: no blocking I/O in async code — use `asyncio.to_thread()`. Flag `time.sleep`, sync `httpx`/`requests`, or direct file I/O inside coroutines.
3. **Task lifecycle**: gateway-owned background tasks go through `BragerOneGateway._spawn()` (tracked, cancelled on shutdown); other fire-and-forget tasks use `utils.spawn()`. Dispatch/subscriber loops must catch and log exceptions (`LOG.exception`), never die silently; reserve `contextlib.suppress` for expected outcomes like cancellation. `asyncio.TaskGroup` for structured concurrency.
4. **Typing**: mypy strict. New `Any`, `cast()`, or `# type: ignore` need an inline justification comment. Prefer `Protocol` for injectable dependencies.
5. **Errors**: REST failures raise `ApiError(status, data, headers)` — don't swallow HTTP errors or return bare `None` from the client. ParamStore upserts intentionally soft-fail on malformed keys (`P<n>.<chan><idx>`).
6. **Pydantic v2 only**: `ConfigDict`, `model_validate`, `Field(alias=...)`. Flag v1 idioms (`Config` class, `.dict()`, `.parse_obj()`).
7. **Logging**: `logging.getLogger(__name__)`, no `print`, no logging configuration in library modules. Entry points are exempt: `cli.py` intentionally uses `print()` for user-facing output and sets up `logging.basicConfig`.
8. **Public API**: changes to `__init__.py` exports or signatures used by ha-bragerone (see `docs/reference/ha_integration.rst`) are breaking — require explicit PR discussion.
9. **Docstrings**: Google style, English, on all public objects (ruff `D` rules enforce this).
