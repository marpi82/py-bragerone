"""Micro-benchmark runner for py-bragerone.

This script provides a lightweight, repeatable benchmark workflow with optional
baseline comparison and simple regression gates.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import socket
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pybragerone.api import Platform, RealtimeManager, server_for
from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import AssetRef, LiveAssetsCatalog
from pybragerone.models.param import ParamStore
from pybragerone.models.param_resolver import ParamResolver


def _maybe_load_dotenv() -> None:
    """Load environment variables from a `.env` file when python-dotenv is available.

    Existing environment variables are preserved.
    """
    try:
        from dotenv import find_dotenv, load_dotenv
    except Exception:
        return

    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)


@dataclass(frozen=True, slots=True)
class BenchResult:
    """Benchmark result for a single case."""

    name: str
    loops: int
    total_seconds: float
    mean_ms: float
    median_ms: float
    stdev_ms: float


class _PerfClient(BragerOneApiClient):
    """Client stub for deterministic local benchmarks."""

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


class _PerfAssetApi:
    """Tiny API stub for catalog benchmark with in-memory asset payloads."""

    def __init__(self, payload_by_url: dict[str, bytes]) -> None:
        self._payload_by_url = payload_by_url
        self.one_base = "https://one.brager.pl"

    async def get_bytes(self, url: str) -> bytes:
        payload = self._payload_by_url.get(url)
        if payload is None:
            raise KeyError(f"No fixture bytes for URL: {url}")
        return payload


async def _bench_module_command_auto_raw(client: _PerfClient, loops: int) -> BenchResult:
    samples: list[float] = []
    for _ in range(loops):
        start = time.perf_counter()
        await client.module_command_auto(devid="FTTCTBSLCE", command="BOILER_FUEL_RESET_HT", value=1)
        samples.append(time.perf_counter() - start)
    return _to_result("module_command_auto_raw", loops, samples)


async def _bench_module_command_auto_param(client: _PerfClient, loops: int) -> BenchResult:
    samples: list[float] = []
    for _ in range(loops):
        start = time.perf_counter()
        await client.module_command_auto(
            devid="FTTCTBSLCE",
            pool="P6",
            parameter="v0",
            value=76,
            parameter_name="parameters.PARAM_0",
            unit=1,
        )
        samples.append(time.perf_counter() - start)
    return _to_result("module_command_auto_param", loops, samples)


async def _bench_module_command_extra_payload(client: _PerfClient, loops: int) -> BenchResult:
    extra = {"source": "perf", "requestId": "bench-1", "trace": {"name": "test"}}
    samples: list[float] = []
    for _ in range(loops):
        start = time.perf_counter()
        await client.module_command(
            devid="FTTCTBSLCE",
            pool="P6",
            parameter="v0",
            value=77,
            parameter_name="parameters.PARAM_0",
            unit=1,
            extra_payload=extra,
        )
        samples.append(time.perf_counter() - start)
    return _to_result("module_command_extra_payload", loops, samples)


def _find_first(pattern: str, *, root: Path) -> Path | None:
    matches = sorted(root.glob(pattern))
    return matches[0] if matches else None


def _discover_asset_fixtures() -> tuple[Path, dict[str, Path]] | None:
    repo_root = Path(__file__).resolve().parents[1]
    cache_dir = repo_root / ".cache"

    index_path = _find_first("index-*.js", root=cache_dir)
    if index_path is None:
        return None

    token_patterns = {
        "PARAM_66": "PARAM_66-*.js",
        "URUCHOMIENIE_KOTLA": "URUCHOMIENIE_KOTLA-*.js",
        "COMMAND_MODULE_RESTART": "COMMAND_MODULE_RESTART-*.js",
    }

    token_paths: dict[str, Path] = {}
    for token, pattern in token_patterns.items():
        found = _find_first(pattern, root=cache_dir)
        if found is None:
            return None
        token_paths[token] = found

    return index_path, token_paths


async def _bench_catalog_param_map_parsing(loops: int) -> BenchResult | None:
    fixtures = _discover_asset_fixtures()
    if fixtures is None:
        return None

    index_path, token_paths = fixtures
    index_bytes = index_path.read_bytes()

    payload_by_url: dict[str, bytes] = {}
    asset_refs: dict[str, list[AssetRef]] = {}

    for token, path in token_paths.items():
        url = f"mem://{path.name}"
        payload_by_url[url] = path.read_bytes()
        asset_refs[token] = [AssetRef(url=url, base=token, hash="fixture")]

    api = _PerfAssetApi(payload_by_url)
    catalog = LiveAssetsCatalog(api=cast(Any, api))
    catalog._idx.index_bytes = index_bytes
    catalog._idx.assets_by_basename = asset_refs

    samples: list[float] = []
    tokens = list(token_paths.keys())
    for _ in range(loops):
        start = time.perf_counter()
        mapping = await catalog.get_param_mapping(tokens)
        if len(mapping) < len(tokens):
            raise RuntimeError(f"Benchmark fixture mismatch: expected >= {len(tokens)} parsed maps, got {len(mapping)}")
        samples.append(time.perf_counter() - start)

    return _to_result("catalog_param_map_parsing", loops, samples)


def _to_result(name: str, loops: int, samples: list[float]) -> BenchResult:
    total_seconds = sum(samples)
    means = statistics.mean(samples) * 1000
    median = statistics.median(samples) * 1000
    stdev = statistics.pstdev(samples) * 1000
    return BenchResult(
        name=name,
        loops=loops,
        total_seconds=total_seconds,
        mean_ms=means,
        median_ms=median,
        stdev_ms=stdev,
    )


async def _run_benchmarks(loops: int) -> list[BenchResult]:
    client = _PerfClient()
    try:
        results: list[BenchResult] = [
            await _bench_module_command_auto_raw(client, loops),
            await _bench_module_command_auto_param(client, loops),
            await _bench_module_command_extra_payload(client, loops),
        ]

        asset_loops = max(1, loops // 50)
        asset_bench = await _bench_catalog_param_map_parsing(asset_loops)
        if asset_bench is not None:
            results.append(asset_bench)
        else:
            print("SKIP: catalog_param_map_parsing (asset fixtures not found in .cache)")

        return results
    finally:
        await client.close()


def _count_routes(routes: list[Any]) -> int:
    total = 0
    stack = list(routes)
    while stack:
        route = stack.pop()
        total += 1
        children = getattr(route, "children", None)
        if isinstance(children, list) and children:
            stack.extend(children)
    return total


async def _ingest_prime_into_store(store: ParamStore, payload: dict[str, Any]) -> int:
    upserts = 0
    for pools in payload.values():
        if not isinstance(pools, dict):
            continue
        for pool, entries in pools.items():
            if not isinstance(entries, dict):
                continue
            for chan_idx, body in entries.items():
                if not isinstance(chan_idx, str) or len(chan_idx) < 2:
                    continue
                chan = chan_idx[0]
                idx_raw = chan_idx[1:]
                if not idx_raw.isdigit():
                    continue
                idx = int(idx_raw)
                value: Any | None = None
                value = body.get("value") if isinstance(body, dict) else body
                if value is None:
                    continue
                key = f"{pool}.{chan}{idx}"
                await store.upsert_async(key, value)
                upserts += 1
    return upserts


async def _single_startup_run(
    *,
    email: str,
    password: str,
    object_id: int,
    modules: list[str],
    lang: str,
    all_panels: bool,
    backend_platform: Platform,
) -> tuple[dict[str, float], dict[str, int]]:
    phase_seconds: dict[str, float] = {}

    def mark(phase: str, start: float) -> None:
        phase_seconds[phase] = time.perf_counter() - start

    api = BragerOneApiClient(server=server_for(backend_platform))
    ws: RealtimeManager | None = None
    try:
        t0 = time.perf_counter()
        await api.ensure_auth(email, password)
        mark("auth.ensure", t0)

        t1 = time.perf_counter()
        module_rows = await api.get_modules(object_id)
        mark("modules.list", t1)

        selected_modules = modules
        if not selected_modules:
            selected_modules = [str(m.devid) for m in module_rows if m.devid is not None][:1]
        if not selected_modules:
            raise RuntimeError("No modules available for startup benchmark")

        t2 = time.perf_counter()
        ws = RealtimeManager(
            token=api.access_token,
            origin=api.one_base,
            referer=f"{api.one_base}/",
            io_base=api.io_base,
        )
        await ws.connect()
        sid_ns = ws.sid()
        sid_engine = ws.engine_sid()
        if not sid_ns:
            raise RuntimeError("No namespace SID after WS connect")
        ok_connect = await api.modules_connect(sid_ns, selected_modules, group_id=object_id, engine_sid=sid_engine)
        if not ok_connect:
            raise RuntimeError("modules_connect returned False")
        ws.group_id = object_id
        await ws.subscribe(selected_modules)
        mark("ws.connect_bind_subscribe", t2)

        t3 = time.perf_counter()
        params_res = await api.modules_parameters_prime(selected_modules, return_data=True)
        if not isinstance(params_res, tuple) or len(params_res) != 2:
            raise RuntimeError("modules_parameters_prime returned unexpected payload shape")
        st_params, data_params = params_res
        if st_params not in (200, 204) or not isinstance(data_params, dict):
            raise RuntimeError(f"modules_parameters_prime failed: status={st_params}")
        mark("prime.parameters", t3)

        t4 = time.perf_counter()
        act_res = await api.modules_activity_quantity_prime(selected_modules, return_data=True)
        if not isinstance(act_res, tuple) or len(act_res) != 2:
            raise RuntimeError("modules_activity_quantity_prime returned unexpected payload shape")
        st_act, _ = act_res
        if st_act not in (200, 204):
            raise RuntimeError(f"modules_activity_quantity_prime failed: status={st_act}")
        mark("prime.activity", t4)

        store = ParamStore()
        t5 = time.perf_counter()
        upserts = await _ingest_prime_into_store(store, data_params)
        mark("store.prime_ingest", t5)

        t6 = time.perf_counter()
        resolver = ParamResolver.from_api(api=api, store=store, lang=lang)
        mark("resolver.init", t6)

        selected_module = next((m for m in module_rows if str(m.devid) == str(selected_modules[0])), None)
        if selected_module is None:
            raise RuntimeError("Selected module not found in module list")

        device_menu = int(selected_module.deviceMenu)
        permissions = list(getattr(selected_module, "permissions", []) or [])

        t7 = time.perf_counter()
        menu = await resolver.get_module_menu(device_menu=device_menu, permissions=permissions)
        mark("menu.load_and_parse", t7)

        t8 = time.perf_counter()
        panel_groups = await resolver.build_panel_groups(
            device_menu=device_menu,
            permissions=permissions,
            all_panels=all_panels,
        )
        mark("panels.build_groups", t8)

        symbols: list[str] = sorted({sym for group in panel_groups.values() for sym in group})

        t9 = time.perf_counter()
        for symbol in symbols:
            await resolver.describe_symbol(symbol)
        mark("symbols.describe_all", t9)

        t10 = time.perf_counter()
        for symbol in symbols:
            await resolver.resolve_value(symbol)
        mark("symbols.resolve_all", t10)

        stats = {
            "modules_selected": len(selected_modules),
            "routes_total": _count_routes(menu.routes),
            "panels_total": len(panel_groups),
            "symbols_total": len(symbols),
            "prime_upserts": upserts,
        }
        return phase_seconds, stats
    finally:
        if ws is not None:
            await ws.disconnect()
        await api.close()


async def _run_startup_benchmark(
    *,
    email: str,
    password: str,
    object_id: int,
    modules: list[str],
    lang: str,
    all_panels: bool,
    backend_platform: Platform,
    repeats: int,
) -> tuple[list[BenchResult], dict[str, int], dict[str, Any]]:
    per_repeat_phase: list[dict[str, float]] = []
    last_stats: dict[str, int] = {}

    for _ in range(repeats):
        phase_seconds, stats = await _single_startup_run(
            email=email,
            password=password,
            object_id=object_id,
            modules=modules,
            lang=lang,
            all_panels=all_panels,
            backend_platform=backend_platform,
        )
        per_repeat_phase.append(phase_seconds)
        last_stats = stats

    all_phases = sorted({name for row in per_repeat_phase for name in row})
    results: list[BenchResult] = []
    for phase in all_phases:
        samples = [row[phase] for row in per_repeat_phase if phase in row]
        results.append(_to_result(f"startup.{phase}", len(samples), samples))

    startup_meta = {
        "repeats": repeats,
        "all_panels": all_panels,
        "lang": lang,
        "platform": str(backend_platform),
        "object_id": object_id,
        "modules_requested": modules,
    }
    return results, last_stats, startup_meta


def _serialize(results: list[BenchResult], loops: int) -> dict[str, Any]:
    return {
        "meta": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
            "loops": loops,
        },
        "results": [
            {
                "name": result.name,
                "loops": result.loops,
                "total_seconds": round(result.total_seconds, 6),
                "mean_ms": round(result.mean_ms, 6),
                "median_ms": round(result.median_ms, 6),
                "stdev_ms": round(result.stdev_ms, 6),
            }
            for result in results
        ],
    }


def _load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _compare_reports(baseline: dict[str, Any], current: dict[str, Any], threshold_percent: float) -> int:
    base_map = {entry["name"]: entry for entry in baseline.get("results", [])}
    curr_map = {entry["name"]: entry for entry in current.get("results", [])}

    names = sorted(set(base_map) & set(curr_map))
    if not names:
        print("No overlapping benchmark names between reports.")
        return 2

    print("name | baseline_mean_ms | current_mean_ms | delta_ms | delta_%")
    print("-----|------------------|-----------------|----------|--------")

    regressions = 0
    for name in names:
        base_mean = float(base_map[name]["mean_ms"])
        curr_mean = float(curr_map[name]["mean_ms"])
        delta = curr_mean - base_mean
        delta_pct = (delta / base_mean * 100.0) if base_mean > 0 else 0.0
        print(f"{name} | {base_mean:.6f} | {curr_mean:.6f} | {delta:.6f} | {delta_pct:.2f}%")
        if delta_pct > threshold_percent:
            regressions += 1

    if regressions:
        print(f"Regression gate failed: {regressions} case(s) above +{threshold_percent:.2f}%")
        return 1

    print("Comparison OK: no regressions above threshold.")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and compare py-bragerone micro-benchmarks.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_cmd = sub.add_parser("run", help="Run benchmarks and write report JSON.")
    run_cmd.add_argument("--loops", type=int, default=2000, help="Iterations per benchmark case.")
    run_cmd.add_argument("--output", type=Path, default=Path("reports/perf/latest.json"), help="Output report path.")
    run_cmd.add_argument("--compare-to", type=Path, default=None, help="Optional baseline report path.")
    run_cmd.add_argument(
        "--regression-threshold-percent",
        type=float,
        default=10.0,
        help="Allowed mean-time increase percentage before failing.",
    )

    compare_cmd = sub.add_parser("compare", help="Compare two existing report JSON files.")
    compare_cmd.add_argument("--baseline", type=Path, required=True, help="Baseline report path.")
    compare_cmd.add_argument("--current", type=Path, required=True, help="Current report path.")
    compare_cmd.add_argument(
        "--regression-threshold-percent",
        type=float,
        default=10.0,
        help="Allowed mean-time increase percentage before failing.",
    )

    startup_cmd = sub.add_parser("startup", help="Run real CLI-like startup benchmark with phase timings.")
    startup_cmd.add_argument("--email", type=str, default=os.getenv("PYBO_EMAIL"), help="Login email")
    startup_cmd.add_argument("--password", type=str, default=os.getenv("PYBO_PASSWORD"), help="Login password")
    startup_cmd.add_argument("--object-id", type=int, default=None, help="Object ID (or env PYBO_OBJECT_ID)")
    startup_cmd.add_argument(
        "--modules",
        type=str,
        default=os.getenv("PYBO_MODULES", ""),
        help="Comma-separated module devids (optional).",
    )
    startup_cmd.add_argument("--lang", type=str, default="pl", help="Resolver language")
    startup_cmd.add_argument("--all-panels", action="store_true", help="Benchmark full all-panels route handling")
    startup_cmd.add_argument(
        "--platform",
        choices=[Platform.BRAGERONE.value, Platform.TISCONNECT.value],
        default=Platform.BRAGERONE.value,
        help="Backend platform",
    )
    startup_cmd.add_argument("--repeats", type=int, default=1, help="How many full startup runs to execute")
    startup_cmd.add_argument(
        "--output",
        type=Path,
        default=Path("reports/perf/startup_latest.json"),
        help="Output report path.",
    )
    startup_cmd.add_argument("--compare-to", type=Path, default=None, help="Optional baseline startup report path.")
    startup_cmd.add_argument(
        "--regression-threshold-percent",
        type=float,
        default=10.0,
        help="Allowed mean-time increase percentage before failing.",
    )

    return parser.parse_args()


def main() -> int:
    """Run benchmark CLI entry point and return process exit code."""
    _maybe_load_dotenv()
    args = _parse_args()

    if args.cmd == "run":
        results = asyncio.run(_run_benchmarks(loops=args.loops))
        payload = _serialize(results, loops=args.loops)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"Wrote benchmark report: {args.output}")
        for item in payload["results"]:
            print(
                f"{item['name']}: mean={item['mean_ms']:.6f} ms, "
                f"median={item['median_ms']:.6f} ms, stdev={item['stdev_ms']:.6f} ms"
            )

        if args.compare_to is not None:
            baseline = _load_report(args.compare_to)
            return _compare_reports(baseline, payload, threshold_percent=args.regression_threshold_percent)

        return 0

    if args.cmd == "compare":
        baseline = _load_report(args.baseline)
        current = _load_report(args.current)
        return _compare_reports(baseline, current, threshold_percent=args.regression_threshold_percent)

    if args.cmd == "startup":
        email = (args.email or "").strip()
        password = args.password or ""
        object_id = args.object_id
        if object_id is None and os.getenv("PYBO_OBJECT_ID"):
            object_id = int(os.getenv("PYBO_OBJECT_ID", "0"))

        if not email:
            print("Missing --email (or PYBO_EMAIL)")
            return 2
        if not password:
            print("Missing --password (or PYBO_PASSWORD)")
            return 2
        if not object_id:
            print("Missing --object-id (or PYBO_OBJECT_ID)")
            return 2

        modules = [m.strip() for m in str(args.modules).split(",") if m.strip()]
        backend_platform = Platform(args.platform)

        startup_results, stats, startup_meta = asyncio.run(
            _run_startup_benchmark(
                email=email,
                password=password,
                object_id=int(object_id),
                modules=modules,
                lang=str(args.lang).strip().lower(),
                all_panels=bool(args.all_panels),
                backend_platform=backend_platform,
                repeats=max(1, int(args.repeats)),
            )
        )

        payload = _serialize(startup_results, loops=max(1, int(args.repeats)))
        payload["meta"]["startup"] = startup_meta
        payload["meta"]["stats"] = stats

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"Wrote startup benchmark report: {args.output}")
        print(
            "stats: "
            f"modules={stats.get('modules_selected', 0)}, "
            f"routes={stats.get('routes_total', 0)}, "
            f"panels={stats.get('panels_total', 0)}, "
            f"symbols={stats.get('symbols_total', 0)}, "
            f"prime_upserts={stats.get('prime_upserts', 0)}"
        )
        for item in payload["results"]:
            print(
                f"{item['name']}: mean={item['mean_ms']:.6f} ms, "
                f"median={item['median_ms']:.6f} ms, stdev={item['stdev_ms']:.6f} ms"
            )

        if args.compare_to is not None:
            baseline = _load_report(args.compare_to)
            return _compare_reports(baseline, payload, threshold_percent=args.regression_threshold_percent)

        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
