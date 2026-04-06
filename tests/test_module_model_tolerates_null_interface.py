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
