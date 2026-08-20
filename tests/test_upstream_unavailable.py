"""Unit tests for expected upstream unavailable classification."""

from __future__ import annotations

from pybragerone.api.client import (
    ApiError,
    format_expected_failure_reason,
    is_expected_upstream_unavailable,
)
from pybragerone.api.ws import _is_expected_ws_reconnect_failure


def test_is_expected_upstream_unavailable_for_api_error_statuses() -> None:
    """Classify ApiError 502/503/504 as expected unavailable statuses."""
    assert is_expected_upstream_unavailable(ApiError(503, "down", {})) is True
    assert is_expected_upstream_unavailable(ApiError(502, "bad gateway", {})) is True
    assert is_expected_upstream_unavailable(ApiError(504, "gateway timeout", {})) is True
    assert is_expected_upstream_unavailable(ApiError(500, "boom", {})) is False
    assert is_expected_upstream_unavailable(ApiError(404, "missing", {})) is False


def test_is_expected_upstream_unavailable_walks_exception_group() -> None:
    """Nested ExceptionGroup members with 503 must still classify as expected."""
    nested = ExceptionGroup("prime", [ApiError(503, "down", {})])
    assert is_expected_upstream_unavailable(nested) is True
    assert is_expected_upstream_unavailable(ExceptionGroup("other", [RuntimeError("x")])) is False


def test_is_expected_upstream_unavailable_walks_cause_chain() -> None:
    """``__cause__`` chains wrapping ApiError 503 must classify as expected."""
    root = ApiError(503, "down", {})
    wrapped = RuntimeError("wrapper")
    wrapped.__cause__ = root
    assert is_expected_upstream_unavailable(wrapped) is True


def test_is_expected_upstream_unavailable_walks_context_chain() -> None:
    """``__context__`` (without ``__cause__``) must still classify as expected."""
    root = ApiError(503, "down", {})
    wrapped = RuntimeError("wrapper")
    wrapped.__context__ = root
    assert is_expected_upstream_unavailable(wrapped) is True


def test_is_expected_upstream_unavailable_skips_exception_cycles() -> None:
    """Cyclic ``__cause__`` graphs must not loop forever and still classify."""
    a = RuntimeError("cycle-a")
    b = RuntimeError("cycle-b")
    a.__cause__ = b
    b.__cause__ = a
    assert is_expected_upstream_unavailable(a) is False
    a.__context__ = ApiError(503, "down", {})
    assert is_expected_upstream_unavailable(a) is True


def test_is_expected_upstream_unavailable_for_code_attribute() -> None:
    """Errors exposing HTTP status via ``code`` (not ``status``) must match."""

    class _CodedError(Exception):
        def __init__(self, code: int) -> None:
            super().__init__(f"code={code}")
            self.code = code

    assert is_expected_upstream_unavailable(_CodedError(503)) is True
    assert is_expected_upstream_unavailable(_CodedError(500)) is False


def test_is_expected_upstream_unavailable_for_status_attribute() -> None:
    """Errors exposing HTTP status via ``status`` (e.g. aiohttp handshake) must match."""

    class _StatusError(Exception):
        def __init__(self, status: int) -> None:
            super().__init__(f"status={status}")
            self.status = status

    assert is_expected_upstream_unavailable(_StatusError(503)) is True
    assert is_expected_upstream_unavailable(_StatusError(500)) is False


def test_format_expected_failure_reason_omits_response_bodies() -> None:
    """Compact reasons must include type/status without embedding response bodies."""
    html = "<html>" + ("x" * 2000) + "</html>"
    reason = format_expected_failure_reason(ApiError(503, html, {}))
    assert reason == "ApiError(status=503)"
    assert html not in reason
    assert format_expected_failure_reason(TimeoutError()) == "TimeoutError"

    class _StatusError(Exception):
        def __init__(self, status: int) -> None:
            super().__init__("ignored body")
            self.status = status

    class _CodedError(Exception):
        def __init__(self, code: int) -> None:
            super().__init__("ignored body")
            self.code = code

    assert format_expected_failure_reason(_StatusError(504)) == "_StatusError(status=504)"
    assert format_expected_failure_reason(_CodedError(502)) == "_CodedError(code=502)"


def test_is_expected_ws_reconnect_failure_covers_timeout_and_sio() -> None:
    """Reconnect helper accepts timeouts, 503, and socketio ConnectionError."""
    assert _is_expected_ws_reconnect_failure(TimeoutError()) is True
    assert _is_expected_ws_reconnect_failure(ApiError(503, "down", {})) is True

    class _SioConnectionError(ConnectionError):
        __module__ = "socketio.exceptions"

    class _EioConnectionError(ConnectionError):
        __module__ = "engineio.exceptions"

    assert _is_expected_ws_reconnect_failure(_SioConnectionError("Connection error")) is True
    assert _is_expected_ws_reconnect_failure(_EioConnectionError("engine down")) is True
    assert _is_expected_ws_reconnect_failure(RuntimeError("guard me")) is False
