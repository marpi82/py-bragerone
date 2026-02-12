"""Server/platform configuration for BragerOne-compatible backends.

This module provides a small abstraction for selecting which backend service to
use (e.g. BragerOne vs TiSConnect) without mutating global constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Platform(StrEnum):
    """Known BragerOne-compatible platform identifiers."""

    BRAGERONE = "bragerone"
    TISCONNECT = "tisconnect"


@dataclass(frozen=True, slots=True)
class ServerConfig:
    """Base URLs and Socket.IO settings for a backend service."""

    io_base: str
    one_base: str
    container: str
    api_version: str = "v1"
    sock_path: str = "/socket.io"
    ws_namespace: str = "/ws"

    @property
    def api_base(self) -> str:
        """Return the REST API base URL (io_base + api_version)."""
        return f"{self.io_base.rstrip('/')}/{self.api_version}"


BRAGERONE_SERVER = ServerConfig(
    io_base="https://io.brager.pl",
    one_base="https://one.brager.pl",
    container="BragerOne",
)

TISCONNECT_SERVER = ServerConfig(
    io_base="https://io.tisconnect.info",
    one_base="https://www.tisconnect.info",
    container="TisConnect",
)


def server_for(platform: Platform | str) -> ServerConfig:
    """Return a ServerConfig for the given platform identifier.

    Args:
        platform: Platform enum value or string (case-insensitive).

    Returns:
        A matching ServerConfig.

    Raises:
        ValueError: If the platform identifier is unknown.
    """
    plat = Platform(str(platform).strip().lower())
    if plat is Platform.BRAGERONE:
        return BRAGERONE_SERVER
    if plat is Platform.TISCONNECT:
        return TISCONNECT_SERVER
    raise ValueError(f"Unsupported platform: {platform!r}")
