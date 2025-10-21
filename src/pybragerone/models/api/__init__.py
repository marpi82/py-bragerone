"""API response models for BragerOne."""

from __future__ import annotations

from .auth import AuthResponse, LoginRequest
from .modules import (
    Module,
    ModuleActivityResponse,
    ModuleCard,
    ModuleGateway,
    ModuleParameterSchema,
    ModuleParametersResponse,
    ModulesListResponse,
)
from .objects import BragerObject, ObjectDetailsResponse, ObjectPermissions
from .system import SystemVersion, VersionInfo
from .user import User, UserInfoResponse, UserPermissions

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
    "SystemVersion",
    "User",
    "UserInfoResponse",
    "UserPermissions",
    "VersionInfo",
]
