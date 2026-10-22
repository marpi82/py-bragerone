"""Tests for DeviceMenuRef parsing from Module.devices (#438)."""

from __future__ import annotations

from types import SimpleNamespace

from pybragerone.models.api.modules import DeviceMenuRef, device_menu_refs_from_module


def test_device_menu_refs_from_dicts_and_objects() -> None:
    """Dict and attribute rows both parse; incomplete / duplicates are skipped."""
    refs = device_menu_refs_from_module(
        [
            {"manuf_code": 67, "dev_code": 7, "sw_ver_num": "2.08"},
            SimpleNamespace(manuf_code=67, dev_code=7, sw_ver_num="2.08"),  # duplicate
            {"manuf_code": 1, "dev_code": 2},  # fw default
            {"manuf_code": 3},  # missing dev
            "skip-me",
            {"manuf_code": "x", "dev_code": 1},  # bad manuf
            SimpleNamespace(manuf_code=9, dev_code=8, fw="1.0.0"),
        ]
    )
    assert refs == [
        DeviceMenuRef(manuf_code=67, dev_code=7, fw="2.08"),
        DeviceMenuRef(manuf_code=1, dev_code=2, fw="0.0.0"),
        DeviceMenuRef(manuf_code=9, dev_code=8, fw="1.0.0"),
    ]


def test_device_menu_refs_empty_input() -> None:
    """None / empty sequences yield no refs."""
    assert device_menu_refs_from_module(None) == []
    assert device_menu_refs_from_module([]) == []


def test_device_menu_ref_fingerprint() -> None:
    """Fingerprint is stable for cache keys."""
    assert DeviceMenuRef(manuf_code=67, dev_code=7, fw="2.08").fingerprint() == "67/7/2.08"
