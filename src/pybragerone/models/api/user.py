"""User-related models for BragerOne API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .common import Permission


class User(BaseModel):
    """User information model."""

    id: int
    name: str
    email: str
    language: str
    allow_email_type_informations: bool
    allow_email_type_alarms: bool
    allow_email_type_marketing: bool
    allow_email_type_warnings: bool
    activated_at: datetime
    show_rate_us_modal: bool


class UserInfoResponse(BaseModel):
    """Response model for user info endpoint."""

    user: User


class UserPermissionsResponse(BaseModel):
    """Response model for user permissions endpoint."""

    permissions: list[str]

    def get_permissions(self) -> list[Permission]:
        """Get permissions as Permission models."""
        return [Permission(name=perm) for perm in self.permissions]
