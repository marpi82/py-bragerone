"""System-related models for BragerOne API."""

from __future__ import annotations

from pydantic import BaseModel


class VersionInfo(BaseModel):
    """Version information structure."""

    version: str
    devMode: bool


class SystemVersion(BaseModel):
    """System version information."""

    version: VersionInfo
