"""Module-related models for BragerOne API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class ModuleGateway(BaseModel):
    """Gateway information for a module."""

    address: str
    interface: str
    version: str

    @field_validator("interface", mode="before")
    @classmethod
    def _coerce_optional_interface(cls, value: Any) -> Any:
        if value is None:
            return ""
        return value


class ModuleParameterSchema(BaseModel):
    """Parameter schema for a module."""

    name: str
    id: int
    value: dict[str, Any]


class Module(BaseModel):
    """Module information model."""

    devid: str
    name: str
    gateway: ModuleGateway
    deviceMenu: int
    deviceLanguageVariant: int
    devices: list[Any]
    services: list[Any]
    permissions: list[str]
    acceptedAt: int
    connectedAt: int
    moduleAlarms: int
    parameterSchemas: list[ModuleParameterSchema]
    id: int
    moduleAddress: str
    moduleInterface: str
    moduleVersion: str
    moduleServices: list[Any]
    moduleTitle: str
    isAcceptedAt: datetime
    isConnectedAt: datetime

    @field_validator("moduleInterface", mode="before")
    @classmethod
    def _coerce_optional_module_interface(cls, value: Any) -> Any:
        if value is None:
            return ""
        return value


class ModuleCard(BaseModel):
    """Module card information with client details."""

    id: int
    moduleId: int
    clientFullName: str
    clientPhoneNumber: str
    clientAddressStreetAndNumber: str
    clientAddressPostalCode: str
    clientAddressCity: str
    createdAt: datetime
    updatedAt: datetime
