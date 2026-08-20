"""Unit tests for expected upstream unavailable classification."""

from __future__ import annotations

from aiohttp.client_exceptions import WSServerHandshakeError
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from pybragerone.api.client import ApiError, is_expected_upstream_unavailable
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


def test_is_expected_upstream_unavailable_for_aiohttp_handshake() -> None:
    """Aiohttp WS handshake 503 must classify as expected unavailable."""
    req = type("RI", (), {"real_url": URL("wss://example.test/socket.io/")})()
    err = WSServerHandshakeError(
        request_info=req,
        history=(),
        status=503,
        message="Invalid response status",
        headers=CIMultiDictProxy(CIMultiDict()),
    )
    assert is_expected_upstream_unavailable(err) is True


def test_is_expected_ws_reconnect_failure_covers_timeout_and_sio() -> None:
    """Reconnect helper accepts timeouts, 503, and socketio ConnectionError."""
    assert _is_expected_ws_reconnect_failure(TimeoutError()) is True
    assert _is_expected_ws_reconnect_failure(ApiError(503, "down", {})) is True

    class _SioConnectionError(ConnectionError):
        __module__ = "socketio.exceptions"

    assert _is_expected_ws_reconnect_failure(_SioConnectionError("Connection error")) is True
    assert _is_expected_ws_reconnect_failure(RuntimeError("guard me")) is False
