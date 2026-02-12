"""Constants for pybragerone api."""

from __future__ import annotations

from .server import BRAGERONE_SERVER

# Backwards-compatible constants (defaulting to the BragerOne platform).
IO_BASE = BRAGERONE_SERVER.io_base
ONE_BASE = BRAGERONE_SERVER.one_base
API_VERSION = BRAGERONE_SERVER.api_version
API_BASE = BRAGERONE_SERVER.api_base
SOCK_PATH = BRAGERONE_SERVER.sock_path
WS_NAMESPACE = BRAGERONE_SERVER.ws_namespace
