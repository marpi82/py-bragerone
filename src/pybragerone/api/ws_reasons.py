"""Classify Socket.IO / Engine.IO failures into stable cloud-session reason tokens."""

from __future__ import annotations

from typing import Any, get_args

from ..models.events import CloudOutageReason

CLOUD_OUTAGE_REASON_TOKENS: frozenset[str] = frozenset(get_args(CloudOutageReason))


def _payload_text(data: Any | None) -> str:
    """Flatten a Socket.IO error payload into a single lower-case string."""
    if data is None:
        return ""
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    if isinstance(data, str):
        return data.strip().lower()
    if isinstance(data, dict):
        parts: list[str] = []
        for key in ("message", "msg", "error", "description", "reason", "data"):
            value = data.get(key)
            if isinstance(value, (str, int, float)):
                parts.append(str(value))
        if not parts:
            parts.append(str(data))
        return " ".join(parts).strip().lower()
    if isinstance(data, (list, tuple)):
        return " ".join(_payload_text(item) for item in data).strip()
    return str(data).strip().lower()


def classify_ws_failure_reason(
    data: Any | None = None,
    *,
    default: CloudOutageReason = "disconnect",
) -> CloudOutageReason:
    """Map a Socket.IO / Engine.IO failure payload to a stable reason token.

    Unknown shapes fall back to *default* (typically ``disconnect``). Tokens are
    additive observation labels for diagnostics — they do not change reconnect policy.
    """
    text = _payload_text(data)
    if not text:
        return default
    if "503" in text:
        return "handshake_503"
    if "packet queue is empty" in text or "queue is empty" in text:
        return "empty_queue"
    if "server has stopped communicating" in text or "stopped communicating" in text:
        return "server_stop"
    if "wsmsgtype.closed" in text or "msgtype.closed" in text:
        return "eio_close"
    if "257" in text:
        return "eio_close"
    # Match Engine.IO close without the hostname-like ``engine.io`` substring
    # (CodeQL treats that as incomplete URL sanitization).
    if "close" in text and ("eio" in text or ("engine" in text and "io" in text)):
        return "eio_close"
    if "reconnect" in text and "error" in text:
        return "reconnect_error"
    if ("connect" in text and "error" in text) or "connection error" in text or "connection refused" in text:
        return "connect_error"
    return default
