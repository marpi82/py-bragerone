"""Common models shared across API modules."""

from __future__ import annotations

from pydantic import BaseModel


class Permission(BaseModel):
    """Single permission string model for type safety."""

    name: str

    def __str__(self) -> str:
        """Return the permission name when converted to string."""
        return self.name
