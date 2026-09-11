"""Offline tests for ``scripts/live_compat_smoke.py``."""

from __future__ import annotations

import importlib.util
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, cast
from unittest.mock import AsyncMock

import pytest

from pybragerone.models.param_resolver import ResolvedValue

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "live_compat_smoke.py"


class _LiveCompatSmokeScript(Protocol):
    """Subset of ``live_compat_smoke`` used by tests."""

    parse_modules: Callable[[str | None], list[str]]
    prime_has_module_data: Callable[[Mapping[str, Any], str], bool]
    evaluate_module_smoke: Callable[[Mapping[str, Any]], list[str]]
    evaluate_smoke_report: Callable[[Mapping[str, Any]], list[str]]
    smoke_module: Callable[..., Awaitable[dict[str, Any]]]
    run_compat_smoke: Callable[..., Awaitable[dict[str, Any]]]
    ParamResolver: Any


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


def test_prime_has_module_data_requires_non_empty_bucket() -> None:
    """Empty or missing module keys in the prime payload are rejected."""
    module = _load()
    assert module.prime_has_module_data({"M1": {"v": {"v1": 1}}}, "M1") is True
    assert module.prime_has_module_data({"M1": {}}, "M1") is False
    assert module.prime_has_module_data({}, "M1") is False


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


def test_evaluate_smoke_report_aggregates_modules_without_duplicating_errors() -> None:
    """Top-level report fails when any module smoke fails; existing errors are not doubled."""
    module = _load()
    assert module.evaluate_smoke_report({"module_count": 0, "modules": [], "errors": []}) == ["no modules smoked"]
    assert module.evaluate_smoke_report({"module_count": 0, "modules": [], "errors": ["RuntimeError: boom"]}) == [
        "RuntimeError: boom"
    ]
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
            "errors": ["stale"],
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
            "errors": ["stale-should-be-ignored"],
        }
    )
    assert "stale-should-be-ignored" not in bad
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


class _FakeResolver:
    """Minimal async ParamResolver stand-in for smoke_module wiring tests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Accept constructor args used by the real resolver."""

    async def build_panel_groups(self, **kwargs: Any) -> dict[str, list[str]]:
        """Return one panel with a single symbol."""
        _ = kwargs
        return {"panel": ["PARAM_1"]}

    async def describe_symbols(self, symbols: Sequence[str]) -> dict[str, dict[str, Any]]:
        """Return describe payloads with a raw unit_code."""
        return {symbol: {"unit": "°C", "unit_code": 1} for symbol in symbols}

    async def resolve_value(self, symbol: str) -> ResolvedValue:
        """Return a resolved display value."""
        return ResolvedValue(
            symbol=symbol,
            kind="direct",
            address="P1.v1",
            value=21,
            value_label=None,
            unit="°C",
        )

    async def resolve_unit(self, unit_code: Any) -> str:
        """Echo the raw unit code path (must not receive the display unit)."""
        if unit_code != 1:
            raise AssertionError(f"expected raw unit_code=1, got {unit_code!r}")
        return "°C"

    async def get_module_menu(self, **kwargs: Any) -> SimpleNamespace:
        """Return an empty menu for visibility iteration."""
        _ = kwargs
        return SimpleNamespace(routes=[])

    @staticmethod
    def _iter_routes_with_ancestors(routes: Sequence[Any]) -> list[tuple[Any, tuple[Any, ...]]]:
        """No routes in the fake menu."""
        _ = routes
        return []

    @staticmethod
    def route_visibility_diagnostics(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        """Visibility always succeeds for the fake."""
        _ = args, kwargs
        return True, "ok"


@pytest.mark.asyncio
async def test_smoke_module_happy_path_uses_unit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """smoke_module primes, builds panels, describes/resolves, and looks up unit_code."""
    module = _load()
    monkeypatch.setattr(module, "ParamResolver", _FakeResolver)

    client = AsyncMock()
    client.modules_parameters_prime = AsyncMock(return_value=(200, {"M1": {"0": {"v1": {"value": 1}}}}))
    catalog = object()

    payload = await module.smoke_module(
        client=client,
        catalog=catalog,
        devid="M1",
        device_menu=1,
        permissions=["perm"],
        lang="en",
        max_resolve=None,
    )
    assert payload["devid"] == "M1"
    assert payload["panel_group_count_all"] == 1
    assert payload["panel_group_count_web_ui"] == 1
    assert payload["symbols_described"] == 1
    assert payload["symbols_resolved"] == 1
    assert payload["describe_error"] is None
    assert payload["resolve_error"] is None
    assert module.evaluate_module_smoke(payload) == []


@pytest.mark.asyncio
async def test_smoke_module_rejects_empty_prime_payload() -> None:
    """Empty prime data for the module is a hard failure before resolver work."""
    module = _load()
    client = AsyncMock()
    client.modules_parameters_prime = AsyncMock(return_value=(200, {"OTHER": {"0": {"v1": {"value": 1}}}}))

    with pytest.raises(RuntimeError, match="no data for this module"):
        await module.smoke_module(
            client=client,
            catalog=object(),
            devid="M1",
            device_menu=1,
            permissions=[],
            lang="en",
            max_resolve=None,
        )


@pytest.mark.asyncio
async def test_run_compat_smoke_surfaces_module_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_compat_smoke marks compat_ok false when a module smoke payload fails evaluation."""
    module = _load()

    class _Client:
        async def ensure_auth(self, *args: Any, **kwargs: Any) -> None:
            _ = args, kwargs

        async def get_modules(self, object_id: int) -> list[SimpleNamespace]:
            _ = object_id
            return [
                SimpleNamespace(devid="M1", deviceMenu=1, permissions=["p"]),
            ]

        async def close(self) -> None:
            return None

    monkeypatch.setattr(module, "BragerOneApiClient", lambda **kwargs: _Client())
    monkeypatch.setattr(module, "LiveAssetsCatalog", lambda client: object())
    monkeypatch.setattr(module, "server_for", lambda platform: object())

    async def _bad_smoke(**kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "devid": "M1",
            "panel_group_count_all": 0,
            "panel_group_count_web_ui": 0,
            "symbols_described": 0,
            "symbols_resolved": 0,
        }

    monkeypatch.setattr(module, "smoke_module", _bad_smoke)
    report = await module.run_compat_smoke(
        email="a@b.c",
        password="x",
        object_id=1,
        modules=["M1"],
        lang="en",
        platform="bragerone",
    )
    assert report["compat_ok"] is False
    assert report["module_count"] == 1
    assert any("M1:" in item for item in report["errors"])


@pytest.mark.asyncio
async def test_run_compat_smoke_success_path_closes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Success path authenticates, filters modules, aggregates counts, and closes the client."""
    module = _load()
    closed = {"done": False}

    class _Client:
        async def ensure_auth(self, *args: Any, **kwargs: Any) -> None:
            _ = args, kwargs

        async def get_modules(self, object_id: int) -> list[SimpleNamespace]:
            _ = object_id
            return [
                SimpleNamespace(devid="M1", deviceMenu=1, permissions=["p"]),
                SimpleNamespace(devid="SKIP", deviceMenu=2, permissions=[]),
            ]

        async def close(self) -> None:
            closed["done"] = True

    async def _ok_smoke(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["devid"] == "M1"
        return {
            "devid": "M1",
            "panel_group_count_all": 2,
            "panel_group_count_web_ui": 1,
            "symbols_described": 3,
            "symbols_resolved": 3,
        }

    monkeypatch.setattr(module, "BragerOneApiClient", lambda **kwargs: _Client())
    monkeypatch.setattr(module, "LiveAssetsCatalog", lambda client: object())
    monkeypatch.setattr(module, "server_for", lambda platform: object())
    monkeypatch.setattr(module, "smoke_module", _ok_smoke)

    report = await module.run_compat_smoke(
        email="a@b.c",
        password="x",
        object_id=1,
        modules=["M1"],
        lang="en",
        platform="bragerone",
    )
    assert closed["done"] is True
    assert report["compat_ok"] is True
    assert report["module_count"] == 1
    assert report["panel_count"] == 2
    assert report["symbols_described"] == 3
    assert report["errors"] == []


@pytest.mark.asyncio
async def test_run_compat_smoke_closes_client_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client.close runs even when get_modules raises."""
    module = _load()
    closed = {"done": False}

    class _Client:
        async def ensure_auth(self, *args: Any, **kwargs: Any) -> None:
            _ = args, kwargs

        async def get_modules(self, object_id: int) -> list[SimpleNamespace]:
            _ = object_id
            raise RuntimeError("modules down")

        async def close(self) -> None:
            closed["done"] = True

    monkeypatch.setattr(module, "BragerOneApiClient", lambda **kwargs: _Client())
    monkeypatch.setattr(module, "LiveAssetsCatalog", lambda client: object())
    monkeypatch.setattr(module, "server_for", lambda platform: object())

    with pytest.raises(RuntimeError, match="modules down"):
        await module.run_compat_smoke(
            email="a@b.c",
            password="x",
            object_id=1,
            modules=["M1"],
            lang="en",
            platform="bragerone",
        )
    assert closed["done"] is True
