"""Pure helpers and type aliases for the gateway package."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from ..api.client import ApiError
from ..models.events import (
    AlarmQuantityChanged,
    CloudOutageReason,
    CloudSessionConnectivity,
    ModuleConnectivity,
    ModuleOutageReason,
)

ConnectivitySource = Literal["rest", "ws", "derived"]
CloudSessionSource = Literal["connect", "disconnect", "stop"]

# Callback signatures
ParametersCb = Callable[[str, dict[str, Any]], Awaitable[None] | None]  # (event_name, payload)
SnapshotCb = Callable[[dict[str, Any]], Awaitable[None] | None]
GenericCb = Callable[[str, Any], Awaitable[None] | None]
ModuleConnectivityCb = Callable[[ModuleConnectivity], Awaitable[None] | None]
CloudSessionCb = Callable[[CloudSessionConnectivity], Awaitable[None] | None]
AlarmQuantityCb = Callable[[AlarmQuantityChanged], Awaitable[None] | None]


def _as_cloud_outage_reason(value: object) -> CloudOutageReason | None:
    """Narrow a snapshot value to a cloud outage reason literal."""
    if value == "disconnect":
        return "disconnect"
    if value == "stop":
        return "stop"
    return None


def _cloud_outage_reason_from_source(source: CloudSessionSource) -> CloudOutageReason:
    """Map a session flip source to an outage reason (never ``connect``)."""
    if source == "stop":
        return "stop"
    return "disconnect"


def _as_module_outage_reason(value: object) -> ModuleOutageReason | None:
    """Narrow a snapshot value to a module outage reason literal."""
    if value == "rest":
        return "rest"
    if value == "ws":
        return "ws"
    if value == "derived":
        return "derived"
    return None


def module_connected_at_means_online(connected_at: int) -> bool:
    """Return whether a ``connectedAt`` value means the module is online.

    Mirrors the SPA ternary ``connectedAt ? 'connected' : 'notConnected'``.
    Upstream uses ``0`` as the offline sentinel (see fixtures and live payloads).
    """
    return int(connected_at) != 0


def _parse_alarm_quantity(raw_qty: Any) -> int | None:
    """Normalize an upstream ``alarmsQuantity`` entry.

    Returns:
        Non-negative integer count, or ``None`` when upstream sends explicit null.

    Raises:
        ValueError: When the payload is malformed (bool, fractional float, negative, etc.).
    """
    if raw_qty is None:
        return None
    if isinstance(raw_qty, bool):
        msg = f"boolean alarm count: {raw_qty!r}"
        raise ValueError(msg)
    if isinstance(raw_qty, int):
        if raw_qty < 0:
            msg = f"negative alarm count: {raw_qty}"
            raise ValueError(msg)
        return raw_qty
    if isinstance(raw_qty, float):
        if raw_qty < 0 or not raw_qty.is_integer():
            msg = f"non-integral alarm count: {raw_qty!r}"
            raise ValueError(msg)
        return int(raw_qty)
    if isinstance(raw_qty, str):
        text = raw_qty.strip()
        if not text:
            msg = "empty alarm count string"
            raise ValueError(msg)
        parsed = int(text)
        if parsed < 0:
            msg = f"negative alarm count: {parsed}"
            raise ValueError(msg)
        return parsed
    msg = f"unsupported alarm count type: {type(raw_qty).__name__}"
    raise ValueError(msg)


def _parse_connected_at(raw: Any) -> int | None:
    """Parse a connectedAt value; return ``None`` when missing/unusable."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _gateway_as_dict(gateway_obj: Any) -> dict[str, Any] | None:
    """Normalize a Module.gateway / WS gateway blob to a plain dict."""
    if gateway_obj is None:
        return None
    dump = getattr(gateway_obj, "model_dump", None)
    if callable(dump):
        raw = dump(mode="json")
        return dict(raw) if isinstance(raw, dict) else None
    if isinstance(gateway_obj, dict):
        return dict(gateway_obj)
    return None


def _is_http_timeout_error(err: Exception) -> bool:
    """Return whether *err* is an HTTP timeout surfaced by httpx/httpcore."""
    module = getattr(type(err), "__module__", "")
    if not (module.startswith("httpx") or module.startswith("httpcore")):
        return False
    return err.__class__.__name__ in {
        "TimeoutException",
        "ReadTimeout",
        "ConnectTimeout",
        "WriteTimeout",
        "PoolTimeout",
    }


def _is_api_dispatch_timeout(err: Exception) -> bool:
    """Return whether *err* is an upstream API timeout response."""
    if not isinstance(err, ApiError) or err.status != 408:
        return False
    data = err.data
    if not isinstance(data, dict):
        return False
    status = data.get("status")
    return isinstance(status, str) and status == "E_DISPATCH_EVENT_TIMEOUT"
