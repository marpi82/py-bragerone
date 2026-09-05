"""Gateway package: BragerOneGateway facade and internal helpers.

Public import path stays ``from pybragerone.gateway import BragerOneGateway``.
Internal layout: connectivity / recovery / session mixins behind the facade.
"""

from __future__ import annotations

from ..api import RealtimeManager
from ._gateway import BragerOneGateway
from .helpers import (
    CloudSessionSource,
    ConnectivitySource,
    _gateway_as_dict,
    _is_api_dispatch_timeout,
    _is_http_timeout_error,
    _parse_alarm_quantity,
    _parse_connected_at,
    module_connected_at_means_online,
)
from .protocols import ApiClient, RealtimeManagerClient

__all__ = [
    "ApiClient",
    "BragerOneGateway",
    "CloudSessionSource",
    "ConnectivitySource",
    "RealtimeManager",
    "RealtimeManagerClient",
    "_gateway_as_dict",
    "_is_api_dispatch_timeout",
    "_is_http_timeout_error",
    "_parse_alarm_quantity",
    "_parse_connected_at",
    "module_connected_at_means_online",
]
