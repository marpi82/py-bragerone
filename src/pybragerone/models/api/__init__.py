"""API response models for BragerOne."""

from __future__ import annotations

from .auth import AuthResponse, LoginRequest
from .common import Permission
from .modules import (
    Module,
    ModuleActivityResponse,
    ModuleCard,
    ModuleGateway,
    ModuleParameterSchema,
    ModuleParametersResponse,
    ModulesListResponse,
)
from .objects import (
    BragerObject,
    ObjectDetailsResponse,
    ObjectPermissionsResponse,
)
from .system import SystemVersion, VersionInfo
from .user import User, UserInfoResponse, UserPermissionsResponse

__all__ = [
    "AuthResponse",
    "BragerObject",
    "LoginRequest",
    "Module",
    "ModuleActivityResponse",
    "ModuleCard",
    "ModuleGateway",
    "ModuleParameterSchema",
    "ModuleParametersResponse",
    "ModulesListResponse",
    "ObjectDetailsResponse",
    "ObjectPermissions",
    "ObjectPermissionsResponse",
    "Permission",
    "SystemVersion",
    "User",
    "UserInfoResponse",
    "UserPermissions",
    "UserPermissionsResponse",
    "VersionInfo",
]
