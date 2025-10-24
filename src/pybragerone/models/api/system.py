"""System-related models for BragerOne API."""

from __future__ import annotations

from pydantic import BaseModel


class SystemVersion(BaseModel):
    """System version information.

    Note: API returns this wrapped in {"version": {...}}, but we keep the
    inner structure as the main model. The wrapper is handled at API client level.
    """

    version: str
    devMode: bool
