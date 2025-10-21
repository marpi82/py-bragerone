"""Authentication models for the BragerOne API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from pybragerone.models.api.user import User


class AuthResponse(BaseModel):
    """Authentication response model for /v1/auth/user endpoint."""

    accessToken: str
    refreshToken: str | None = None
    type: str | None = None  # e.g., "bearer"
    expiresAt: datetime | str | None = None
    user: User | None = None
    objects: list[dict[str, Any]] | None = None


class LoginRequest(BaseModel):
    """Login request model for /v1/auth/user endpoint."""

    email: str
    password: str
