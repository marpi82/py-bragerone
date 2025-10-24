"""User-related models for BragerOne API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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
