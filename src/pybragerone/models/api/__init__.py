"""API response models for BragerOne."""

from __future__ import annotations

from .auth import AuthResponse, LoginRequest
from .common import ApiResponse, Permission
from .module_events import ModuleActivity, ModuleActivityUser, ModuleAlarm
from .modules import (
    DeviceMenuRef,
    Module,
    ModuleCard,
    ModuleGateway,
    ModuleParameterSchema,
    device_menu_refs_from_module,
)
from .objects import (
    BragerObject,
    ObjectDetails,
)
from .system import SystemVersion
from .user import User

__all__ = [
    "ApiResponse",
    "AuthResponse",
    "BragerObject",
    "DeviceMenuRef",
    "LoginRequest",
    "Module",
    "ModuleActivity",
    "ModuleActivityUser",
    "ModuleAlarm",
    "ModuleCard",
    "ModuleGateway",
    "ModuleParameterSchema",
    "ObjectDetails",
    "Permission",
    "SystemVersion",
    "User",
    "device_menu_refs_from_module",
]
