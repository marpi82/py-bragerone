"""Unit tests for Socket.IO failure reason classification (#380)."""

from __future__ import annotations

from pybragerone.api.ws_reasons import CLOUD_OUTAGE_REASON_TOKENS, classify_ws_failure_reason


def test_classify_ws_failure_reason_tokens() -> None:
    """Map known failure strings to stable tokens; unknown falls back."""
    assert classify_ws_failure_reason("HTTP 503 during handshake") == "handshake_503"
    assert classify_ws_failure_reason({"message": "packet queue is empty"}) == "empty_queue"
    assert classify_ws_failure_reason("Server has stopped communicating") == "server_stop"
    assert classify_ws_failure_reason("Engine.IO close packet 257") == "eio_close"
    assert classify_ws_failure_reason("WSMsgType.CLOSED") == "eio_close"
    assert classify_ws_failure_reason("Connection error to io.brager.pl") == "connect_error"
    assert classify_ws_failure_reason("reconnect_error boom") == "reconnect_error"
    assert classify_ws_failure_reason(None) == "disconnect"
    assert classify_ws_failure_reason("something odd", default="connect_error") == "connect_error"
    assert "handshake_503" in CLOUD_OUTAGE_REASON_TOKENS
    assert "stop" in CLOUD_OUTAGE_REASON_TOKENS
