"""CPU-bound micro-benchmarks for command dispatch and catalog parsing.

Marked ``benchmark`` so ``pytest --codspeed`` can measure them. Without that flag
they run once as ordinary tests and keep the harness from bitrotting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import AssetRef, LiveAssetsCatalog

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bench"
_PARAM_66_TOKEN = "PARAM_66"
_PARAM_66_ASSET = _FIXTURES / "PARAM_66-fixture.js"
_PARAM_66_URL = f"mem://{_PARAM_66_ASSET.name}"
_PARAM_66_BYTES = _PARAM_66_ASSET.read_bytes()


class _PerfClient(BragerOneApiClient):
    """Client stub that skips HTTP for deterministic local benchmarks."""

    async def _req(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        auth: bool = True,
        _retry: bool = True,
    ) -> tuple[int, Any, dict[str, str]]:
        return 200, {"ok": True, "path": path, "method": method, "json": json}, {}


class _PerfAssetClient(BragerOneApiClient):
    """Client stub that serves committed JS fixtures from memory."""

    def __init__(self, payload_by_url: dict[str, bytes]) -> None:
        super().__init__()
        self._payload_by_url = payload_by_url

    async def get_bytes(self, url: str) -> bytes:
        payload = self._payload_by_url.get(url)
        if payload is None:
            raise KeyError(f"No fixture bytes for URL: {url}")
        return payload


@pytest.mark.benchmark
async def test_bench_module_command_auto_raw() -> None:
    """Benchmark raw ``module_command_auto`` dispatch."""
    client = _PerfClient()
    try:
        await client.module_command_auto(devid="FTTCTBSLCE", command="BOILER_FUEL_RESET_HT", value=1)
    finally:
        await client.close()


@pytest.mark.benchmark
async def test_bench_module_command_auto_param() -> None:
    """Benchmark parameter ``module_command_auto`` dispatch."""
    client = _PerfClient()
    try:
        await client.module_command_auto(
            devid="FTTCTBSLCE",
            pool="P6",
            parameter="v0",
            value=76,
            parameter_name="parameters.PARAM_0",
            unit=1,
        )
    finally:
        await client.close()


@pytest.mark.benchmark
async def test_bench_module_command_extra_payload() -> None:
    """Benchmark ``module_command`` with extra payload fields."""
    client = _PerfClient()
    extra = {"source": "perf", "requestId": "bench-1", "trace": {"name": "test"}}
    try:
        await client.module_command(
            devid="FTTCTBSLCE",
            pool="P6",
            parameter="v0",
            value=77,
            parameter_name="parameters.PARAM_0",
            unit=1,
            extra_payload=extra,
        )
    finally:
        await client.close()


@pytest.mark.benchmark
async def test_bench_catalog_param_map_parsing() -> None:
    """Benchmark ``LiveAssetsCatalog`` param-map parsing from a committed JS fixture."""
    client = _PerfAssetClient({_PARAM_66_URL: _PARAM_66_BYTES})
    try:
        catalog = LiveAssetsCatalog(api=client)
        catalog._idx.assets_by_basename = {_PARAM_66_TOKEN: [AssetRef(url=_PARAM_66_URL, base=_PARAM_66_TOKEN, hash="fixture")]}
        mapping = await catalog.get_param_mapping([_PARAM_66_TOKEN])
        assert _PARAM_66_TOKEN in mapping
        assert mapping[_PARAM_66_TOKEN].group == "P4"
    finally:
        await client.close()
