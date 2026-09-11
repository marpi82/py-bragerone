"""Offline tests for ``scripts/live_compat_smoke.py``."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol, cast

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "live_compat_smoke.py"


class _LiveCompatSmokeScript(Protocol):
    """Subset of ``live_compat_smoke`` used by tests."""

    parse_modules: Callable[[str | None], list[str]]
    evaluate_module_smoke: Callable[[Mapping[str, Any]], list[str]]
    evaluate_smoke_report: Callable[[Mapping[str, Any]], list[str]]


def _load() -> _LiveCompatSmokeScript:
    """Import the script module by path (not a package)."""
    spec = importlib.util.spec_from_file_location("live_compat_smoke", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(_LiveCompatSmokeScript, module)


def test_parse_modules_splits_and_dedupes() -> None:
    """Module filter parsing matches live_contract behaviour."""
    assert _load().parse_modules(None) == []
    assert _load().parse_modules(" b,a, a ") == ["a", "b"]


def test_evaluate_module_smoke_accepts_healthy_payload() -> None:
    """Healthy module payloads produce no hard-failure reasons."""
    errors = _load().evaluate_module_smoke(
        {
            "devid": "M1",
            "panel_group_count_all": 3,
            "panel_group_count_web_ui": 2,
            "symbols_described": 10,
            "symbols_resolved": 10,
            "describe_error": None,
            "resolve_error": None,
            "visibility_error": None,
        }
    )
    assert errors == []


def test_evaluate_module_smoke_flags_empty_panels_and_errors() -> None:
    """Empty panels or nested exceptions are hard failures."""
    errors = _load().evaluate_module_smoke(
        {
            "devid": "M1",
            "panel_group_count_all": 0,
            "panel_group_count_web_ui": 1,
            "symbols_described": 0,
            "symbols_resolved": 0,
            "describe_error": "RuntimeError: boom",
            "resolve_error": None,
            "visibility_error": None,
        }
    )
    assert any("no panels" in item for item in errors)
    assert any("describe_symbols failed" in item for item in errors)
    assert any("zero panel symbols" in item for item in errors)


def test_evaluate_smoke_report_aggregates_modules() -> None:
    """Top-level report fails when any module smoke fails or no modules ran."""
    module = _load()
    assert module.evaluate_smoke_report({"module_count": 0, "modules": [], "errors": []}) == ["no modules smoked"]
    ok = module.evaluate_smoke_report(
        {
            "module_count": 1,
            "modules": [
                {
                    "devid": "M1",
                    "panel_group_count_all": 2,
                    "panel_group_count_web_ui": 1,
                    "symbols_described": 4,
                    "symbols_resolved": 4,
                }
            ],
            "errors": [],
        }
    )
    assert ok == []
    bad = module.evaluate_smoke_report(
        {
            "module_count": 1,
            "modules": [
                {
                    "devid": "M1",
                    "panel_group_count_all": 0,
                    "panel_group_count_web_ui": 0,
                    "symbols_described": 0,
                    "symbols_resolved": 0,
                }
            ],
            "errors": ["top-level"],
        }
    )
    assert "top-level" in bad
    assert any("M1:" in item for item in bad)


def test_evaluate_module_smoke_allows_none_values_without_errors() -> None:
    """None live values are not hard failures (only counts matter)."""
    errors = _load().evaluate_module_smoke(
        {
            "devid": "M1",
            "panel_group_count_all": 1,
            "panel_group_count_web_ui": 1,
            "symbols_described": 5,
            "symbols_resolved": 5,
            "symbols_resolved_none": 5,
        }
    )
    assert errors == []
