"""Common models shared across API modules."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiResponse[T](BaseModel):
    """Standard API response wrapper with status and data.

    This wrapper provides a consistent interface for all API responses,
    including HTTP status code, response data, and optional headers.

    Examples:
        Single object response:
            >>> response: ApiResponse[User] = await client.get_user()
            >>> if response.is_success:
            ...     user = response.data

        List response:
            >>> response: ApiResponse[list[Module]] = await client.get_modules(obj_id)
            >>> modules = response.data if response.is_success else []

        Raw data response:
            >>> response: ApiResponse[dict[str, Any]] = await client.get_parameters(...)
            >>> params = response.data

    Attributes:
        status: HTTP status code (e.g., 200, 404, 500).
        data: Response data of type T.
        headers: Optional HTTP response headers.
    """

    status: int
    data: T
    headers: dict[str, str] | None = None

    @property
    def is_success(self) -> bool:
        """Check if response was successful (2xx status).

        Returns:
            True if status is in range 200-299, False otherwise.
        """
        return 200 <= self.status < 300

    @property
    def is_client_error(self) -> bool:
        """Check if response was client error (4xx status).

        Returns:
            True if status is in range 400-499, False otherwise.
        """
        return 400 <= self.status < 500

    @property
    def is_server_error(self) -> bool:
        """Check if response was server error (5xx status).

        Returns:
            True if status is in range 500-599, False otherwise.
        """
        return 500 <= self.status < 600

    @property
    def is_error(self) -> bool:
        """Check if response was any error (4xx or 5xx status).

        Returns:
            True if status is 400 or higher, False otherwise.
        """
        return self.status >= 400


class Permission(BaseModel):
    """Single permission string model for type safety.

    Permissions in BragerOne API are uppercase strings with underscores,
    such as 'DISPLAY_MENU_OBJECTS', 'SUBMISSION_CREATE', etc.

    Automatically converts from string or dict format.

    Examples:
        From string:
            >>> perm = Permission(name="DISPLAY_MENU_OBJECTS")
            >>> perm = Permission.model_validate("DISPLAY_MENU_DHW")

        From dict (API response):
            >>> perm = Permission.model_validate({"name": "SUBMISSION_CREATE"})

        As list (from API):
            >>> perms = ["DISPLAY_MENU_CIRCUITS", "DISPLAY_PARAMETER_LEVEL_1"]
            >>> permissions = [Permission.model_validate(p) for p in perms]

        String representation:
            >>> perm = Permission(name="DISPLAY_MENU_ALERTS")
            >>> str(perm)
            'DISPLAY_MENU_ALERTS'
    """

    name: str

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> Permission:
        """Validate and convert value to Permission.

        Args:
            obj: String, dict, or Permission instance.
            **kwargs: Additional validation arguments.

        Returns:
            Permission instance.

        Raises:
            ValueError: If obj cannot be converted to Permission.
        """
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, str):
            return cls(name=obj)
        if isinstance(obj, dict):
            return super().model_validate(obj, **kwargs)
        raise ValueError(f"Cannot convert {type(obj)} to Permission")

    def __str__(self) -> str:
        """Return the permission name when converted to string."""
        return self.name

    def __hash__(self) -> int:
        """Make Permission hashable for use in sets."""
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        """Compare permissions by name."""
        if isinstance(other, Permission):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return False
