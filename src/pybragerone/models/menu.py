"""Menu models with validation and automatic prefix cleanup.

This module provides Pydantic models for BragerOne menu structure with automatic
cleanup of prefixes (A.*, e.*, a.*) and normalization of parameters.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator

from .api.common import Permission


class MenuParameter(BaseModel):
    """Single parameter in a menu route with automatic cleanup.

    Automatically extracts token from parameter expressions like:
    - e(E.WRITE,"PARAM_123") → "PARAM_123"
    - E(A.READ,"TEMP_SENSOR") → "TEMP_SENSOR"

    And normalizes permissions by removing detected prefixes:
    - A.DISPLAY_PARAMETER_LEVEL_1 → DISPLAY_PARAMETER_LEVEL_1
    - e.HeaterManagement → HeaterManagement
    """

    token: str = Field(description="Clean parameter token extracted from parameter expression")
    permission: Permission | None = Field(None, description="Required permission (prefix-normalized)")
    raw_parameter: str = Field(..., alias="parameter", description="Original parameter expression")
    raw_permission: str | None = Field(None, alias="permissionModule", description="Original permission with prefix")

    # Regex to extract token from parameter expressions
    PARAM_REGEX: ClassVar[re.Pattern[str]] = re.compile(r'[A-Za-z]\([^,]*?,\s*[\'"]([^\'"]+)[\'"]\)')

    @model_validator(mode="before")
    @classmethod
    def extract_fields(cls, data: Any) -> Any:
        """Extract token from parameter and normalize permission."""
        if not isinstance(data, dict):
            return data

        result = dict(data)

        # Extract token from parameter if not already present
        if "token" not in result and "parameter" in result:
            param_str = result["parameter"]
            if isinstance(param_str, str):
                match = cls.PARAM_REGEX.search(param_str)
                if match:
                    result["token"] = match.group(1)
                else:
                    # Fallback: use parameter string as token
                    result["token"] = param_str.strip()

        # Set default token if still missing
        if "token" not in result:
            result["token"] = ""  # nosec B105 - default placeholder token

        # Normalize permission from permissionModule
        if "permission" not in result and "permissionModule" in result:
            perm_str = result["permissionModule"]
            if perm_str:
                # Remove common prefixes
                for prefix in ["A.", "e.", "E."]:
                    if perm_str.startswith(prefix):
                        perm_str = perm_str[len(prefix) :]
                        break
                result["permission"] = Permission(name=perm_str)
            else:
                result["permission"] = None

        return result

    @field_validator("permission", mode="before")
    @classmethod
    def normalize_permission(cls, v: Any) -> Permission | None:
        """Normalize permission by removing common prefixes."""
        if v is None:
            return None

        perm_str = str(v)
        if not perm_str:
            return None

        # Remove common prefixes
        for prefix in ["A.", "e.", "E."]:
            if perm_str.startswith(prefix):
                perm_str = perm_str[len(prefix) :]
                break

        return Permission(name=perm_str)

    @model_validator(mode="after")
    def validate_token_extracted(self) -> MenuParameter:
        """Ensure token was successfully extracted."""
        if not self.token and self.raw_parameter:
            # Try extraction one more time from raw_parameter
            match = self.PARAM_REGEX.search(self.raw_parameter)
            if match:
                self.token = match.group(1)
            else:
                # Last resort: use raw parameter
                self.token = self.raw_parameter

        if not self.token:
            raise ValueError(f"Could not extract token from parameter: {self.raw_parameter}")

        return self


class MenuParameters(BaseModel):
    """Collection of parameters organized by type (read/write/status/special)."""

    read: list[MenuParameter] = Field(default_factory=list)
    write: list[MenuParameter] = Field(default_factory=list)
    status: list[MenuParameter] = Field(default_factory=list)
    special: list[MenuParameter] = Field(default_factory=list)

    def all_tokens(self) -> set[str]:
        """Get all unique tokens from all parameter sections."""
        tokens: set[str] = set()
        for param_list in [self.read, self.write, self.status, self.special]:
            tokens.update(param.token for param in param_list)
        return tokens

    def all_permissions(self) -> set[Permission]:
        """Get all unique permissions from all parameters."""
        permissions: set[Permission] = set()
        for param_list in [self.read, self.write, self.status, self.special]:
            for param in param_list:
                if param.permission:
                    permissions.add(param.permission)
        return permissions


class MenuMeta(BaseModel):
    """Menu route metadata with automatic cleanup."""

    display_name: str = Field(..., alias="displayName")
    icon: str | None = None
    permission: Permission | None = None
    parameters: MenuParameters = Field(default_factory=MenuParameters)
    display_dropdown: str | None = Field(None, alias="displayDropdown")

    # Raw fields for debugging/reference
    raw_permission: str | None = Field(None, alias="permissionModule")
    raw_icon: str | None = None

    @field_validator("icon", mode="before")
    @classmethod
    def clean_icon(cls, v: Any) -> str | None:
        """Remove 'a.' prefix from icons."""
        if v is None:
            return None

        icon_str = str(v)
        if icon_str.startswith("a."):
            return icon_str[2:]  # Remove 'a.' prefix
        return icon_str

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        """Normalize permission and icon fields."""
        if not isinstance(data, dict):
            return data

        result = dict(data)

        # Normalize permission from permissionModule
        if "permission" not in result and "permissionModule" in result:
            perm_str = result["permissionModule"]
            if perm_str:
                # Remove common prefixes
                for prefix in ["A.", "e.", "E."]:
                    if perm_str.startswith(prefix):
                        perm_str = perm_str[len(prefix) :]
                        break
                result["permission"] = Permission(name=perm_str)
            else:
                result["permission"] = None

        return result

    @model_validator(mode="after")
    def store_raw_values(self) -> MenuMeta:
        """Store raw values for reference."""
        # This will be set by alias during parsing
        return self


class MenuRoute(BaseModel):
    """Single menu route with automatic cleanup and validation."""

    path: str
    name: str
    meta: MenuMeta | None = None
    component: str | None = None
    children: list[MenuRoute] = Field(default_factory=list)

    # Legacy parameters field (should be empty after processing)
    parameters: MenuParameters = Field(default_factory=MenuParameters)

    def all_tokens(self) -> set[str]:
        """Get all tokens from this route and its children recursively."""
        tokens: set[str] = set()

        # Add from meta parameters
        if self.meta:
            tokens.update(self.meta.parameters.all_tokens())

        # Add from legacy parameters
        tokens.update(self.parameters.all_tokens())

        # Add from children
        for child in self.children:
            tokens.update(child.all_tokens())

        return tokens

    def all_permissions(self) -> set[Permission]:
        """Get all permissions from this route and its children recursively."""
        permissions: set[Permission] = set()

        # Add route permission
        if self.meta and self.meta.permission:
            permissions.add(self.meta.permission)

        # Add parameter permissions
        if self.meta:
            permissions.update(self.meta.parameters.all_permissions())
        permissions.update(self.parameters.all_permissions())

        # Add from children
        for child in self.children:
            permissions.update(child.all_permissions())

        return permissions


class MenuResult(BaseModel):
    """Complete menu result with validation and statistics."""

    routes: list[MenuRoute] = Field(default_factory=list)
    asset_url: str | None = None

    def all_tokens(self) -> set[str]:
        """Get all unique tokens from all routes."""
        tokens: set[str] = set()
        for route in self.routes:
            tokens.update(route.all_tokens())
        return tokens

    def all_permissions(self) -> set[Permission]:
        """Get all unique permissions from all routes."""
        permissions: set[Permission] = set()
        for route in self.routes:
            permissions.update(route.all_permissions())
        return permissions

    def token_count(self) -> int:
        """Get total number of unique tokens."""
        return len(self.all_tokens())

    def route_count(self) -> int:
        """Get total number of routes (including nested)."""

        def count_routes(routes: list[MenuRoute]) -> int:
            count = len(routes)
            for route in routes:
                count += count_routes(route.children)
            return count

        return count_routes(self.routes)

    def routes_by_path(self) -> dict[str, MenuRoute]:
        """Get flat mapping of path -> route for easy lookup."""
        result: dict[str, MenuRoute] = {}

        def collect_routes(routes: list[MenuRoute], prefix: str = "") -> None:
            for route in routes:
                # Clean path by removing leading slashes and handling double slashes
                clean_path = route.path.lstrip("/")
                full_path = f"{prefix}/{clean_path}" if prefix else clean_path
                result[full_path] = route
                collect_routes(route.children, full_path)

        collect_routes(self.routes)
        return result
