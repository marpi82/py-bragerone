"""Module-related models for BragerOne API."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DeviceMenuRef(BaseModel):
    """Identity for SPA ``devices_menu.show`` (``manuf`` / ``dev`` / ``fw``).

    Sourced from ``Module.devices[]`` entries so catalog menu loading can try the
    device-specific REST menu before the generic ``0/0/0.0.0`` default (#438).
    """

    manuf_code: int
    dev_code: int
    fw: str = "0.0.0"

    def fingerprint(self) -> str:
        """Stable cache-key fragment for this device menu identity."""
        return f"{self.manuf_code}/{self.dev_code}/{self.fw}"


def device_menu_refs_from_module(devices: Sequence[Any] | None) -> list[DeviceMenuRef]:
    """Extract ``DeviceMenuRef`` rows from a ``Module.devices`` list.

    Tolerates dicts and objects with ``manuf_code`` / ``dev_code`` / ``sw_ver_num``
    (or ``fw``). Incomplete rows are skipped.
    """
    if not devices:
        return []
    refs: list[DeviceMenuRef] = []
    seen: set[str] = set()
    for row in devices:
        manuf = _device_field(row, "manuf_code")
        dev = _device_field(row, "dev_code")
        if manuf is None or dev is None:
            continue
        try:
            manuf_i = int(manuf)
            dev_i = int(dev)
        except (TypeError, ValueError):
            continue
        fw_raw = _device_field(row, "sw_ver_num")
        if fw_raw is None:
            fw_raw = _device_field(row, "fw")
        fw = str(fw_raw).strip() if fw_raw is not None and str(fw_raw).strip() else "0.0.0"
        ref = DeviceMenuRef(manuf_code=manuf_i, dev_code=dev_i, fw=fw)
        key = ref.fingerprint()
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


def _device_field(row: Any, name: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(name)
    return getattr(row, name, None)


class ModuleGateway(BaseModel):
    """Gateway information for a module."""

    address: str = ""
    interface: str = ""
    version: str = ""

    @field_validator("address", "interface", "version", mode="before")
    @classmethod
    def _coerce_optional_str(cls, value: Any) -> Any:
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
    gateway: ModuleGateway = Field(default_factory=ModuleGateway)
    deviceMenu: int
    deviceLanguageVariant: int
    devices: list[Any]
    services: list[Any]
    permissions: list[str]
    acceptedAt: int
    connectedAt: int = 0
    moduleAlarms: int
    parameterSchemas: list[ModuleParameterSchema]
    id: int
    moduleAddress: str = ""
    moduleInterface: str = ""
    moduleVersion: str = ""
    moduleServices: list[Any]
    moduleTitle: str
    isAcceptedAt: datetime
    isConnectedAt: datetime | None = None

    @field_validator("moduleAddress", "moduleInterface", "moduleVersion", mode="before")
    @classmethod
    def _coerce_optional_str(cls, value: Any) -> Any:
        if value is None:
            return ""
        return value

    @field_validator("connectedAt", mode="before")
    @classmethod
    def _coerce_null_connected_at(cls, value: Any) -> Any:
        """Upstream sends ``null`` for disconnected / placeholder module rows."""
        if value is None:
            return 0
        return value

    @field_validator("gateway", mode="before")
    @classmethod
    def _coerce_empty_gateway(cls, value: Any) -> Any:
        if value is None:
            return {}
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
