"""Offline tests for ``scripts/live_compat_smoke.py``."""

from __future__ import annotations

import importlib.util
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, cast
from unittest.mock import AsyncMock

import pytest

from pybragerone.api.client import ApiError
from pybragerone.models.param_resolver import ResolvedValue

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "live_compat_smoke.py"


class _LiveCompatSmokeScript(Protocol):
    """Subset of ``live_compat_smoke`` used by tests."""

    parse_modules: Callable[[str | None], list[str]]
    prime_has_module_data: Callable[[Mapping[str, Any], str], bool]
    collect_param_map_tokens: Callable[[Any], list[str]]
    empty_catalog_section: Callable[[], dict[str, Any]]
    evaluate_module_smoke: Callable[[Mapping[str, Any]], list[str]]
    evaluate_smoke_report: Callable[[Mapping[str, Any]], list[str]]
    smoke_module: Callable[..., Awaitable[dict[str, Any]]]
    smoke_catalog_quality: Callable[..., Awaitable[dict[str, Any]]]
    run_compat_smoke: Callable[..., Awaitable[dict[str, Any]]]
    write_step_summary: Callable[[Mapping[str, Any]], None]
    write_github_output: Callable[[Mapping[str, Any]], None]
    ParamResolver: Any
    _SYMBOL_TOKEN_RE: Any


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
            "symbols_requested": 10,
            "symbols_described": 10,
            "symbols_mapped": 10,
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
            "symbols_requested": 0,
            "symbols_described": 0,
            "symbols_mapped": 0,
            "symbols_resolved": 0,
            "describe_error": "RuntimeError: boom",
            "resolve_error": None,
            "visibility_error": None,
        }
    )
    assert any("no panels" in item for item in errors)
    assert any("describe_symbols failed" in item for item in errors)
    assert any("no panel symbols" in item for item in errors)


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
                    "symbols_requested": 4,
                    "symbols_described": 4,
                    "symbols_mapped": 4,
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
                    "symbols_requested": 0,
                    "symbols_described": 0,
                    "symbols_mapped": 0,
                    "symbols_resolved": 0,
                }
            ],
            "errors": ["stale-should-be-ignored"],
        }
    )
    assert "stale-should-be-ignored" not in bad
    assert any("M1:" in item for item in bad)


def test_evaluate_module_smoke_allows_none_values_without_errors() -> None:
    """None live values are not hard failures when ParamMap coverage is complete."""
    errors = _load().evaluate_module_smoke(
        {
            "devid": "M1",
            "panel_group_count_all": 1,
            "panel_group_count_web_ui": 1,
            "symbols_requested": 5,
            "symbols_described": 5,
            "symbols_mapped": 5,
            "symbols_resolved": 5,
            "symbols_resolved_none": 5,
        }
    )
    assert errors == []


def test_evaluate_module_smoke_rejects_unmapped_or_partial_coverage() -> None:
    """Missing ParamMap or incomplete describe/resolve coverage is a hard failure."""
    module = _load()
    unmapped = module.evaluate_module_smoke(
        {
            "devid": "M1",
            "panel_group_count_all": 1,
            "panel_group_count_web_ui": 1,
            "symbols_requested": 3,
            "symbols_described": 3,
            "symbols_mapped": 0,
            "symbols_resolved": 3,
            "symbols_resolved_none": 3,
        }
    )
    assert any("ParamMap missing" in item for item in unmapped)
    partial = module.evaluate_module_smoke(
        {
            "devid": "M1",
            "panel_group_count_all": 1,
            "panel_group_count_web_ui": 1,
            "symbols_requested": 3,
            "symbols_described": 1,
            "symbols_mapped": 1,
            "symbols_resolved": 2,
        }
    )
    assert any("describe_symbols covered 1/3" in item for item in partial)
    assert any("resolve_value covered 2/3" in item for item in partial)


class _FakeResolver:
    """Minimal async ParamResolver stand-in for smoke_module wiring tests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Accept constructor args used by the real resolver."""

    async def build_panel_groups(self, **kwargs: Any) -> dict[str, list[str]]:
        """Return one panel with a single symbol."""
        _ = kwargs
        return {"panel": ["PARAM_1"]}

    async def describe_symbols(self, symbols: Sequence[str]) -> dict[str, dict[str, Any]]:
        """Return describe payloads with a raw unit_code and ParamMap details."""
        return {symbol: {"unit": "°C", "unit_code": 1, "mapping": {"origin": "test"}} for symbol in symbols}

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
    assert payload["symbols_requested"] == 1
    assert payload["symbols_described"] == 1
    assert payload["symbols_mapped"] == 1
    assert payload["symbols_resolved"] == 1
    assert payload["describe_error"] is None
    assert payload["resolve_error"] is None
    assert module.evaluate_module_smoke(payload) == []


async def test_smoke_module_counts_unmapped_descriptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Describe entries without ParamMap details are counted as unmapped."""
    module = _load()

    class _UnmappedResolver(_FakeResolver):
        async def describe_symbols(self, symbols: Sequence[str]) -> dict[str, dict[str, Any]]:
            return {symbol: {"unit": None, "unit_code": None, "mapping": None} for symbol in symbols}

        async def resolve_value(self, symbol: str) -> ResolvedValue:
            return ResolvedValue(
                symbol=symbol,
                kind="direct",
                address=None,
                value=None,
                value_label=None,
                unit=None,
            )

    monkeypatch.setattr(module, "ParamResolver", _UnmappedResolver)
    client = AsyncMock()
    client.modules_parameters_prime = AsyncMock(return_value=(200, {"M1": {"0": {"v1": {"value": 1}}}}))
    payload = await module.smoke_module(
        client=client,
        catalog=object(),
        devid="M1",
        device_menu=1,
        permissions=["perm"],
        lang="en",
        max_resolve=None,
    )
    assert payload["symbols_requested"] == 1
    assert payload["symbols_described"] == 1
    assert payload["symbols_mapped"] == 0
    assert payload["symbols_resolved"] == 1
    assert any("ParamMap missing" in item for item in module.evaluate_module_smoke(payload))


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

    async def _catalog(**kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return module.empty_catalog_section()

    monkeypatch.setattr(module, "smoke_module", _bad_smoke)
    monkeypatch.setattr(module, "smoke_catalog_quality", _catalog)
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
    assert "catalog" in report


async def test_run_compat_smoke_fails_when_configured_module_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hard gate fails if PYBO_MODULES lists a devid absent from get_modules."""
    module = _load()
    closed = {"done": False}

    class _Client:
        async def ensure_auth(self, *args: Any, **kwargs: Any) -> None:
            _ = args, kwargs

        async def get_modules(self, object_id: int) -> list[SimpleNamespace]:
            _ = object_id
            return [SimpleNamespace(devid="M1", deviceMenu=1, permissions=["p"])]

        async def close(self) -> None:
            closed["done"] = True

    monkeypatch.setattr(module, "BragerOneApiClient", lambda **kwargs: _Client())
    monkeypatch.setattr(module, "LiveAssetsCatalog", lambda client: object())
    monkeypatch.setattr(module, "server_for", lambda platform: object())

    with pytest.raises(RuntimeError, match="not returned by get_modules"):
        await module.run_compat_smoke(
            email="a@b.c",
            password="x",
            object_id=1,
            modules=["M1", "MISSING"],
            lang="en",
            platform="bragerone",
        )
    assert closed["done"] is True


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
            "symbols_requested": 3,
            "symbols_described": 3,
            "symbols_mapped": 3,
            "symbols_resolved": 3,
            "device_menu_refs": ["67/7/2.08"],
            "menu_source": "policy:device_refs_then_default_rest",
        }

    async def _catalog(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["devid"] == "M1"
        section = module.empty_catalog_section()
        section.update(
            {
                "param_map_tokens": 10,
                "symbols_requested": 10,
                "described": 10,
                "mapped": 9,
                "resolved_ok": 4,
                "resolved_none": 6,
                "prime_devid": "M1",
            }
        )
        return section

    monkeypatch.setattr(module, "BragerOneApiClient", lambda **kwargs: _Client())
    monkeypatch.setattr(module, "LiveAssetsCatalog", lambda client: object())
    monkeypatch.setattr(module, "server_for", lambda platform: object())
    monkeypatch.setattr(module, "smoke_module", _ok_smoke)
    monkeypatch.setattr(module, "smoke_catalog_quality", _catalog)

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
    assert report["catalog"]["param_map_tokens"] == 10
    assert report["catalog"]["resolved_none"] == 6
    assert report["modules"][0]["device_menu_refs"] == ["67/7/2.08"]


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


def test_evaluate_smoke_report_ignores_catalog_quality_gaps() -> None:
    """Catalog resolved_none / describe gaps are informational, not hard failures."""
    module = _load()
    report = {
        "modules": [
            {
                "devid": "M1",
                "panel_group_count_all": 1,
                "panel_group_count_web_ui": 1,
                "symbols_requested": 2,
                "symbols_described": 2,
                "symbols_mapped": 2,
                "symbols_resolved": 2,
            }
        ],
        "catalog": {
            "param_map_tokens": 100,
            "described": 50,
            "mapped": 40,
            "resolved_ok": 10,
            "resolved_none": 90,
            "describe_errors": 1,
            "resolve_errors": 2,
            "describe_error": "RuntimeError: boom",
            "resolve_error": "PARAM_X: RuntimeError: x",
        },
    }
    assert module.evaluate_smoke_report(report) == []


def test_collect_param_map_tokens_filters_basenames() -> None:
    """Only PARAM_/STATUS_/COMMAND_/URUCHOMIENIE_ basenames become catalog tokens."""
    module = _load()

    class _Catalog:
        def __init__(self) -> None:
            self._idx = SimpleNamespace(
                assets_by_basename={
                    "PARAM_1": [],
                    "STATUS_P5_0": [],
                    "COMMAND_MODULE_RESTART": [],
                    "URUCHOMIENIE_KOTLA": [],
                    "index": [],
                    "module.menu": [],
                },
                index_bytes=b"",
            )

        def _parse_index_token_raw_maps(self, raw: bytes) -> dict[str, object]:
            _ = raw
            return {"PARAM_INLINE": {}, "noise": {}}

    tokens = module.collect_param_map_tokens(_Catalog())
    assert tokens == sorted(
        [
            "COMMAND_MODULE_RESTART",
            "PARAM_1",
            "PARAM_INLINE",
            "STATUS_P5_0",
            "URUCHOMIENIE_KOTLA",
        ]
    )


async def test_smoke_catalog_quality_counts_none_without_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Catalog quality counts resolved_none and never raises on null live values."""
    module = _load()

    class _CatalogResolver(_FakeResolver):
        async def describe_symbols(self, symbols: Sequence[str]) -> dict[str, dict[str, Any]]:
            return {
                "PARAM_1": {"mapping": {"origin": "t"}},
                "PARAM_2": {"mapping": None},
            }

        async def resolve_value(self, symbol: str) -> ResolvedValue:
            value = 1 if symbol == "PARAM_1" else None
            return ResolvedValue(
                symbol=symbol,
                kind="direct",
                address=None,
                value=value,
                value_label=None,
                unit=None,
            )

    class _Catalog:
        def __init__(self) -> None:
            self._idx = SimpleNamespace(assets_by_basename={"PARAM_1": [], "PARAM_2": []}, index_bytes=b"")

        async def _ensure_index_loaded(self) -> None:
            return None

        def _parse_index_token_raw_maps(self, raw: bytes) -> dict[str, object]:
            _ = raw
            return {}

    monkeypatch.setattr(module, "ParamResolver", _CatalogResolver)
    client = AsyncMock()
    client.modules_parameters_prime = AsyncMock(return_value=(200, {"M1": {"0": {"v1": {"value": 1}}}}))
    payload = await module.smoke_catalog_quality(
        client=client,
        catalog=_Catalog(),
        devid="M1",
        lang="en",
        max_resolve=None,
    )
    assert payload["param_map_tokens"] == 2
    assert payload["described"] == 2
    assert payload["mapped"] == 1
    assert payload["resolved_ok"] == 1
    assert payload["resolved_none"] == 1
    assert payload["resolve_errors"] == 0
    assert payload["prime_devid"] == "M1"


async def test_smoke_module_records_device_menu_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Device menu refs from Module.devices are reported on the module payload."""
    module = _load()
    monkeypatch.setattr(module, "ParamResolver", _FakeResolver)
    client = AsyncMock()
    client.modules_parameters_prime = AsyncMock(return_value=(200, {"M1": {"0": {"v1": {"value": 1}}}}))
    payload = await module.smoke_module(
        client=client,
        catalog=object(),
        devid="M1",
        device_menu=0,
        permissions=["perm"],
        lang="en",
        max_resolve=None,
        devices=[{"manuf_code": 67, "dev_code": 7, "sw_ver_num": "2.08"}],
    )
    assert payload["device_menu_refs"] == ["67/7/2.08"]
    assert payload["menu_source"] == "policy:device_refs_then_default_rest"


async def test_smoke_module_menu_source_without_device_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without Module.devices, menu_source records the legacy/default policy label."""
    module = _load()
    monkeypatch.setattr(module, "ParamResolver", _FakeResolver)
    client = AsyncMock()
    client.modules_parameters_prime = AsyncMock(return_value=(200, {"M1": {"0": {"v1": {"value": 1}}}}))
    payload = await module.smoke_module(
        client=client,
        catalog=object(),
        devid="M1",
        device_menu=0,
        permissions=[],
        lang="en",
        max_resolve=None,
        devices=None,
    )
    assert payload["device_menu_refs"] == []
    assert payload["menu_source"] == "policy:legacy_js_or_default_rest"


async def test_smoke_catalog_quality_records_prime_and_resolve_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Catalog quality soft-fails on bad prime / describe / per-symbol resolve."""
    module = _load()

    class _Catalog:
        def __init__(self) -> None:
            self._idx = SimpleNamespace(assets_by_basename={"PARAM_1": [], "PARAM_2": []}, index_bytes=b"")

        async def _ensure_index_loaded(self) -> None:
            return None

        def _parse_index_token_raw_maps(self, raw: bytes) -> dict[str, object]:
            _ = raw
            return {}

    client = AsyncMock()
    client.modules_parameters_prime = AsyncMock(return_value=(500, None))
    bad_prime = await module.smoke_catalog_quality(
        client=client,
        catalog=_Catalog(),
        devid="M1",
        lang="en",
    )
    assert bad_prime["param_map_tokens"] == 2
    assert bad_prime["prime_errors"] == 1
    assert bad_prime["resolve_errors"] == 0
    assert bad_prime["prime_error"] is not None
    assert "prime failed" in str(bad_prime["prime_error"])

    client.modules_parameters_prime = AsyncMock(side_effect=ApiError(503, {"message": "unavailable"}))
    api_err = await module.smoke_catalog_quality(
        client=client,
        catalog=_Catalog(),
        devid="M1",
        lang="en",
    )
    assert api_err["prime_errors"] == 1
    assert api_err["resolve_errors"] == 0
    assert "ApiError HTTP 503" in str(api_err["prime_error"])

    class _BoomDescribe(_FakeResolver):
        async def describe_symbols(self, symbols: Sequence[str]) -> dict[str, dict[str, Any]]:
            _ = symbols
            raise RuntimeError("describe boom")

        async def resolve_value(self, symbol: str) -> ResolvedValue:
            if symbol == "PARAM_2":
                raise RuntimeError("resolve boom")
            return ResolvedValue(
                symbol=symbol,
                kind="direct",
                address=None,
                value=None,
                value_label=None,
                unit=None,
            )

    monkeypatch.setattr(module, "ParamResolver", _BoomDescribe)
    client.modules_parameters_prime = AsyncMock(return_value=(200, {"M1": {"0": {"v1": {"value": 1}}}}))
    payload = await module.smoke_catalog_quality(
        client=client,
        catalog=_Catalog(),
        devid="M1",
        lang="en",
    )
    assert payload["describe_errors"] == 1
    assert payload["describe_error"] is not None
    assert "describe boom" in str(payload["describe_error"])
    assert payload["resolved_none"] == 1
    assert payload["resolve_errors"] == 1
    assert payload["resolve_error"] is not None
    assert "PARAM_2" in str(payload["resolve_error"])


async def test_smoke_catalog_quality_respects_max_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    """max_resolve caps catalog describe/resolve while param_map_tokens stays full."""
    module = _load()

    class _Catalog:
        def __init__(self) -> None:
            self._idx = SimpleNamespace(
                assets_by_basename={"PARAM_1": [], "PARAM_2": [], "PARAM_3": []},
                index_bytes=b"",
            )

        async def _ensure_index_loaded(self) -> None:
            return None

        def _parse_index_token_raw_maps(self, raw: bytes) -> dict[str, object]:
            _ = raw
            return {}

    monkeypatch.setattr(module, "ParamResolver", _FakeResolver)
    client = AsyncMock()
    client.modules_parameters_prime = AsyncMock(return_value=(200, {"M1": {"0": {"v1": {"value": 1}}}}))
    payload = await module.smoke_catalog_quality(
        client=client,
        catalog=_Catalog(),
        devid="M1",
        lang="en",
        max_resolve=1,
    )
    assert payload["param_map_tokens"] == 3
    assert payload["symbols_requested"] == 1
    assert payload["described"] == 1
    assert payload["resolved_ok"] == 1


def test_write_step_summary_emits_catalog_and_device_tables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Step summary includes separate Catalog and Device markdown tables."""
    module = _load()
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    report = {
        "compat_ok": True,
        "module_count": 1,
        "panel_count": 2,
        "symbols_described": 3,
        "symbols_resolved": 3,
        "errors": [],
        "catalog": {
            "param_map_tokens": 10,
            "described": 10,
            "mapped": 9,
            "resolved_ok": 4,
            "resolved_none": 6,
            "prime_errors": 0,
            "describe_errors": 0,
            "resolve_errors": 0,
            "prime_devid": "M1",
        },
        "modules": [
            {
                "devid": "M1",
                "panel_group_count_all": 2,
                "symbols_total": 3,
                "symbols_described": 3,
                "symbols_mapped": 3,
                "symbols_resolved": 3,
                "symbols_resolved_none": 1,
                "menu_source": "policy:device_refs_then_default_rest",
                "device_menu_refs": ["67/7/2.08"],
            }
        ],
    }
    module.write_step_summary(report)
    text = summary.read_text(encoding="utf-8")
    assert "### Compat — Catalog (ParamMap quality, informational)" in text
    assert "| param_map_tokens | 10 |" in text
    assert "| prime_errors | 0 |" in text
    assert "### Compat — Device (PYBO_MODULES hard gate)" in text
    assert "| modules | 1 |" in text
    assert "| panels | 2 |" in text
    assert "| errors | 0 |" in text
    assert "67/7/2.08" in text


def test_write_github_output_includes_catalog_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GitHub Actions outputs expose catalog quality counters."""
    module = _load()
    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    module.write_github_output(
        {
            "compat_ok": True,
            "module_count": 1,
            "panel_count": 2,
            "symbols_described": 3,
            "symbols_resolved": 3,
            "errors": [],
            "catalog": {
                "param_map_tokens": 12,
                "described": 11,
                "mapped": 10,
                "resolved_ok": 5,
                "resolved_none": 6,
                "prime_errors": 0,
                "describe_errors": 0,
                "resolve_errors": 1,
                "prime_devid": "M1",
            },
        }
    )
    text = out.read_text(encoding="utf-8")
    assert "catalog_param_map_tokens=12" in text
    assert "catalog_resolved_none=6" in text
    assert "catalog_prime_errors=0" in text
    assert "catalog_prime_devid=M1" in text


async def test_run_compat_smoke_keeps_device_results_if_catalog_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Escaped catalog quality errors must not wipe module hard-gate results."""
    module = _load()

    class _Client:
        async def ensure_auth(self, *args: Any, **kwargs: Any) -> None:
            _ = args, kwargs

        async def get_modules(self, object_id: int) -> list[SimpleNamespace]:
            _ = object_id
            return [SimpleNamespace(devid="M1", deviceMenu=1, permissions=["p"])]

        async def close(self) -> None:
            return None

    async def _ok_smoke(**kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "devid": "M1",
            "panel_group_count_all": 2,
            "panel_group_count_web_ui": 1,
            "symbols_requested": 3,
            "symbols_described": 3,
            "symbols_mapped": 3,
            "symbols_resolved": 3,
        }

    async def _boom_catalog(**kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        raise RuntimeError("catalog escaped")

    monkeypatch.setattr(module, "BragerOneApiClient", lambda **kwargs: _Client())
    monkeypatch.setattr(module, "LiveAssetsCatalog", lambda client: object())
    monkeypatch.setattr(module, "server_for", lambda platform: object())
    monkeypatch.setattr(module, "smoke_module", _ok_smoke)
    monkeypatch.setattr(module, "smoke_catalog_quality", _boom_catalog)

    report = await module.run_compat_smoke(
        email="a@b.c",
        password="x",
        object_id=1,
        modules=["M1"],
        lang="en",
        platform="bragerone",
    )
    assert report["compat_ok"] is True
    assert report["module_count"] == 1
    assert report["symbols_described"] == 3
    assert report["catalog"]["prime_errors"] == 1
    assert "catalog escaped" in str(report["catalog"]["prime_error"])
