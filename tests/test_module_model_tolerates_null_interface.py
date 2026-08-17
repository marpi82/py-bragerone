"""Regression test for null module interface fields."""

from __future__ import annotations

from pybragerone.models.api.modules import Module


def test_module_model_tolerates_null_interfaces() -> None:
    """Module model accepts null interfaces from API payloads."""
    payload = {
        "devid": "FTTCTBSLCE",
        "name": "Module name",
        "gateway": {
            "address": "gateway-addr",
            "interface": None,
            "version": "1.0",
        },
        "deviceMenu": 0,
        "deviceLanguageVariant": 0,
        "devices": [],
        "services": [],
        "permissions": [],
        "acceptedAt": 0,
        "connectedAt": 0,
        "moduleAlarms": 0,
        "parameterSchemas": [],
        "id": 1,
        "moduleAddress": "module-addr",
        "moduleInterface": None,
        "moduleVersion": "2.08",
        "moduleServices": [],
        "moduleTitle": "HT DasPell GL 37kW",
        "isAcceptedAt": "2026-04-06T00:00:00Z",
        "isConnectedAt": "2026-04-06T00:00:00Z",
    }

    module = Module.model_validate(payload)

    assert module.gateway.interface == ""
    assert module.moduleInterface == ""


def test_module_model_keeps_non_null_interfaces() -> None:
    """Non-null interface strings are kept as-is."""
    payload = {
        "devid": "[REDACTED]",
        "name": "Module name",
        "gateway": {
            "address": "gateway-addr",
            "interface": "eth0",
            "version": "1.0",
        },
        "deviceMenu": 0,
        "deviceLanguageVariant": 0,
        "devices": [],
        "services": [],
        "permissions": [],
        "acceptedAt": 0,
        "connectedAt": 0,
        "moduleAlarms": 0,
        "parameterSchemas": [],
        "id": 1,
        "moduleAddress": "module-addr",
        "moduleInterface": "wifi",
        "moduleVersion": "2.08",
        "moduleServices": [],
        "moduleTitle": "HT DasPell GL 37kW",
        "isAcceptedAt": "2026-04-06T00:00:00Z",
        "isConnectedAt": "2026-04-06T00:00:00Z",
    }

    module = Module.model_validate(payload)

    assert module.gateway.interface == "eth0"
    assert module.moduleInterface == "wifi"


def test_module_model_tolerates_degraded_disconnected_row() -> None:
    """Live get_modules can send empty gateway and null connectedAt (HA freeze 2026-08-17)."""
    payload = {
        "devid": "[REDACTED]",
        "name": "Module name",
        "gateway": {},
        "deviceMenu": 0,
        "deviceLanguageVariant": 0,
        "devices": [],
        "services": [],
        "permissions": [],
        "acceptedAt": 0,
        "connectedAt": None,
        "moduleAlarms": 0,
        "parameterSchemas": [],
        "id": 1,
        "moduleAddress": None,
        "moduleInterface": None,
        "moduleVersion": None,
        "moduleServices": [],
        "moduleTitle": "HT DasPell GL 37kW",
        "isAcceptedAt": "2026-04-06T00:00:00Z",
        "isConnectedAt": None,
    }

    module = Module.model_validate(payload)

    assert module.devid == "[REDACTED]"
    assert module.connectedAt == 0
    assert module.gateway.address == ""
    assert module.moduleAddress == ""
    assert module.moduleVersion == ""
    assert module.isConnectedAt is None
