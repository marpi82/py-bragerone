"""Tests for backend platform URL selection."""

from __future__ import annotations

import pytest

from pybragerone.api.server import BRAGERONE_SERVER, TISCONNECT_SERVER, Platform, server_for


def test_server_for_accepts_enum_and_case_insensitive_names() -> None:
    """Known platforms resolve to the matching ServerConfig."""
    assert server_for(Platform.BRAGERONE) is BRAGERONE_SERVER
    assert server_for("  TiSConnect  ") is TISCONNECT_SERVER
    assert BRAGERONE_SERVER.api_base == "https://io.brager.pl/v1"
    assert TISCONNECT_SERVER.api_base == "https://io.tisconnect.info/v1"


def test_server_for_rejects_unknown_platform() -> None:
    """Unknown identifiers raise ValueError from the Platform enum."""
    with pytest.raises(ValueError, match="not-a-platform"):
        server_for("not-a-platform")
