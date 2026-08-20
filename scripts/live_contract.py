"""Build and compare a structural live-catalog contract (no live register values).

Logs into BragerOne with ``PYBO_*`` credentials, parses the live SPA catalog, and
produces a deterministic JSON snapshot of parameter-map *structure* (symbols,
path shapes, units, status/command kinds). Live ``value`` / connectivity fields
are never recorded.

Baseline behaviour (self-hosted runner)::

    PYBO_BASELINE_DIR=/var/lib/gha/baselines  # default
    # missing live_contract.json → seed and exit 0
    # present → structural compare; drift exits 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from pybragerone import BragerOneApiClient
from pybragerone.api.server import Platform, server_for
from pybragerone.models.catalog import INDEX_ASSET_RE, LiveAssetsCatalog, ParamMap
from pybragerone.models.param_resolver import ParamResolver

SCHEMA_VERSION = 1
DEFAULT_BASELINE_DIR = Path("/var/lib/gha/baselines")
BASELINE_FILENAME = "live_contract.json"
_PATH_CHANNELS = ("value", "unit", "status", "command", "min", "max")
_SYMBOL_TOKEN_RE = re.compile(r"^(?:COMMAND_|URUCHOMIENIE_|PARAM_|STATUS_)[A-Z0-9_]+$")
_TOKEN_CHUNK = 64


def parse_modules(raw: str | None) -> list[str]:
    """Split a comma-separated ``PYBO_MODULES`` string into sorted unique codes."""
    if not raw:
        return []
    return sorted({part.strip() for part in raw.split(",") if part.strip()})


def require_env(name: str) -> str:
    """Return a non-empty environment variable or raise ``SystemExit``."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing {name}: set it in the runner EnvironmentFile or process env.")
    return value


def classify_path_kind(entries: Any) -> str:
    """Classify a path channel list as status rules, address selectors, empty, or other."""
    if entries is None:
        return "empty"
    if isinstance(entries, list) and not entries:
        return "empty"
    if ParamResolver._is_status_rule_list(entries):
        return "status_rules"
    if ParamResolver._is_address_selector_list(entries):
        return "address_selector"
    if isinstance(entries, list):
        return "other"
    return "other"


def normalize_selector(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable address-selector shape (``convert`` as bool, no live values)."""
    out: dict[str, Any] = {}
    group = entry.get("group")
    number = entry.get("number")
    use = entry.get("use")
    if isinstance(group, str) and group:
        out["group"] = group
    if isinstance(number, int):
        out["number"] = number
    elif isinstance(number, float) and number.is_integer():
        out["number"] = int(number)
    if isinstance(use, str) and use:
        out["use"] = use
    convert = entry.get("convert")
    if convert:
        out["convert"] = True
    times = entry.get("times")
    if isinstance(times, bool):
        pass
    elif isinstance(times, int | float) and not isinstance(times, bool):
        out["times"] = times
    return out


def normalize_path_channel(entries: Any, *, kind: str) -> list[dict[str, Any]] | int:
    """Serialize a path channel without live values.

    Address selectors become normalized dicts. Status-rule / other lists keep only
    a count so minified SPA helper names do not churn the baseline.
    """
    if kind == "address_selector" and isinstance(entries, list):
        return [normalize_selector(entry) for entry in entries if isinstance(entry, Mapping)]
    if isinstance(entries, list):
        return len(entries)
    return 0


def _is_multi_word(paths: Mapping[str, Any]) -> bool:
    """Return whether value paths look like a multi-register compose list."""
    value = paths.get("value")
    if not ParamResolver._is_address_selector_list(value):
        return False
    assert isinstance(value, list)
    if len(value) > 1:
        return True
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        times = entry.get("times")
        if isinstance(times, int | float) and not isinstance(times, bool) and times != 1:
            return True
    return False


def _command_rule_summaries(rules: Sequence[Any] | None) -> list[dict[str, Any]]:
    """Extract public command / operation names from command rules."""
    out: list[dict[str, Any]] = []
    if not rules:
        return out
    for rule in rules:
        if not isinstance(rule, Mapping):
            continue
        command = rule.get("command")
        operations: list[str] = []
        for condition in rule.get("conditions") or []:
            if not isinstance(condition, Mapping):
                continue
            operation = condition.get("operation")
            if isinstance(operation, str) and operation:
                operations.append(operation)
        row: dict[str, Any] = {}
        if isinstance(command, str) and command:
            row["command"] = command
        if operations:
            row["operations"] = sorted(set(operations))
        if row:
            out.append(row)
    return sorted(out, key=lambda item: json.dumps(item, sort_keys=True))


def symbol_contract(
    mapping: ParamMap,
    *,
    units_i18n_ok: bool | None = None,
    units_descriptor_ok: bool | None = None,
) -> dict[str, Any]:
    """Build one symbol's structural contract entry from a :class:`ParamMap`."""
    paths_raw = mapping.paths if isinstance(mapping.paths, Mapping) else {}
    path_kinds: dict[str, str] = {}
    paths_out: dict[str, Any] = {}
    for channel in _PATH_CHANNELS:
        entries = paths_raw.get(channel)
        kind = classify_path_kind(entries)
        path_kinds[channel] = kind
        if kind != "empty":
            paths_out[channel] = normalize_path_channel(entries, kind=kind)

    units_raw = mapping.units
    if isinstance(units_raw, float) and units_raw.is_integer():
        units_raw = int(units_raw)

    writable = bool(paths_raw.get("command")) or bool(mapping.command_rules)
    has_status_rules = ParamResolver._mapping_has_computed_rules(mapping)
    status_keys = sorted(str(key) for key in (mapping.status_conditions or {}))

    entry: dict[str, Any] = {
        "key": mapping.key,
        "group": mapping.group,
        "component_type": mapping.component_type,
        "path_kinds": path_kinds,
        "paths": paths_out,
        "units_raw": units_raw if isinstance(units_raw, str | int | float) else None,
        "status_condition_keys": status_keys,
        "command_rules": _command_rule_summaries(mapping.command_rules),
        "writable": writable,
        "multi_word": _is_multi_word(paths_raw),
        "has_status_rules": has_status_rules,
    }
    if units_i18n_ok is not None:
        entry["units_i18n_ok"] = units_i18n_ok
    if units_descriptor_ok is not None:
        entry["units_descriptor_ok"] = units_descriptor_ok
    return entry


def collect_symbol_tokens(assets_by_basename: Mapping[str, object], inline_tokens: Iterable[str]) -> list[str]:
    """Return sorted unique PARAM/STATUS/COMMAND/URUCHOMIENIE tokens from catalog indices."""
    tokens: set[str] = set()
    for name in assets_by_basename:
        if _SYMBOL_TOKEN_RE.fullmatch(name):
            tokens.add(name)
    for name in inline_tokens:
        if _SYMBOL_TOKEN_RE.fullmatch(name):
            tokens.add(name)
    return sorted(tokens)


def build_contract(
    *,
    lang: str,
    object_id: int,
    modules: Sequence[str],
    fingerprint: str | None,
    symbols: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the top-level contract document with sorted keys."""
    return {
        "schema_version": SCHEMA_VERSION,
        "lang": lang,
        "object_id": object_id,
        "modules": list(modules),
        "fingerprint": fingerprint,
        "symbol_count": len(symbols),
        "symbols": dict(sorted(symbols.items())),
    }


def _diff_values(path: str, left: Any, right: Any, out: list[str]) -> None:
    """Append human-readable structural diffs for unequal JSON-like values."""
    if left == right:
        return
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        keys = sorted(set(left) | set(right))
        for key in keys:
            child = f"{path}.{key}" if path else key
            if key not in left:
                out.append(f"+ {child}")
            elif key not in right:
                out.append(f"- {child}")
            else:
                _diff_values(child, left[key], right[key], out)
        return
    if isinstance(left, list) and isinstance(right, list):
        if left == right:
            return
        max_len = max(len(left), len(right))
        if len(left) != len(right):
            out.append(f"~ {path} length {len(left)} -> {len(right)}")
        for index in range(max_len):
            child = f"{path}[{index}]"
            if index >= len(left):
                out.append(f"+ {child}")
            elif index >= len(right):
                out.append(f"- {child}")
            else:
                _diff_values(child, left[index], right[index], out)
        return
    out.append(f"~ {path}: {left!r} -> {right!r}")


def compare_contracts(baseline: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """Return structural diffs between *baseline* and *current* (empty when equal)."""
    diffs: list[str] = []
    _diff_values("", dict(baseline), dict(current), diffs)
    return diffs


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write pretty, sorted JSON with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from *path*."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return raw


async def discover_index_asset(client: BragerOneApiClient) -> str:
    """Read ``index-*.js`` from the public web-app homepage."""
    base = client.one_base.rstrip("/")
    last_error = "no pages fetched"
    for page_url in (f"{base}/", f"{base}/assets/"):
        try:
            html = (await client.get_bytes(page_url)).decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = str(exc)
            continue
        match = INDEX_ASSET_RE.search(html)
        if match:
            return match.group(1)
    raise RuntimeError(f"could not discover index-*.js from {base} ({last_error})")


async def _units_flags(
    catalog: LiveAssetsCatalog,
    *,
    lang: str,
    units_raw: Any,
    units_i18n: Mapping[str, Any],
) -> tuple[bool | None, bool | None]:
    """Return (units_i18n_ok, units_descriptor_ok) for a raw units code."""
    if units_raw is None:
        return None, None
    key = LiveAssetsCatalog._normalize_unit_key(units_raw)
    if key is None:
        return False, False
    i18n_ok = key in units_i18n or str(units_raw) in units_i18n
    descriptor = await catalog.get_unit_descriptor(units_raw)
    return i18n_ok, descriptor is not None


async def collect_live_contract(
    *,
    email: str,
    password: str,
    object_id: int,
    modules: Sequence[str],
    lang: str,
    platform: str,
) -> dict[str, Any]:
    """Authenticate, parse the live catalog, and return a structural contract."""
    server = server_for(platform)
    client = BragerOneApiClient(server=server, creds_provider=lambda: (email, password), validate_on_start=False)
    try:
        await client.ensure_auth(email, password)
        version = await client.get_system_version()
        index_asset = await discover_index_asset(client)
        fingerprint = f"{version.version.strip()}|{index_asset.strip()}"
        index_url = f"{client.one_base.rstrip('/')}/assets/{index_asset}"

        catalog = LiveAssetsCatalog(client)
        await catalog.refresh_index(index_url, allow_recover=False)
        units_i18n_raw = await catalog.get_i18n(lang, "units")
        units_i18n = units_i18n_raw if isinstance(units_i18n_raw, dict) else {}

        inline_maps = catalog._parse_index_token_raw_maps(catalog._idx.index_bytes or b"")
        tokens = collect_symbol_tokens(catalog._idx.assets_by_basename, inline_maps)

        mappings: dict[str, ParamMap] = {}
        for start in range(0, len(tokens), _TOKEN_CHUNK):
            chunk = tokens[start : start + _TOKEN_CHUNK]
            mappings.update(await catalog.get_param_mapping(chunk))

        symbols: dict[str, dict[str, Any]] = {}
        for token in sorted(mappings):
            mapping = mappings[token]
            i18n_ok, descriptor_ok = await _units_flags(
                catalog,
                lang=lang,
                units_raw=mapping.units,
                units_i18n=units_i18n,
            )
            symbols[token] = symbol_contract(
                mapping,
                units_i18n_ok=i18n_ok,
                units_descriptor_ok=descriptor_ok,
            )

        return build_contract(
            lang=lang,
            object_id=object_id,
            modules=list(modules),
            fingerprint=fingerprint,
            symbols=symbols,
        )
    finally:
        await client.close()


def write_github_output(*, seeded: bool, matched: bool, symbol_count: int, diff_count: int) -> None:
    """Append job outputs when running under GitHub Actions."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        return
    with Path(github_output).open("a", encoding="utf-8") as handle:
        handle.write(f"seeded={str(seeded).lower()}\n")
        handle.write(f"matched={str(matched).lower()}\n")
        handle.write(f"symbol_count={symbol_count}\n")
        handle.write(f"diff_count={diff_count}\n")


def write_step_summary(*, seeded: bool, matched: bool, symbol_count: int, diffs: Sequence[str], baseline: Path) -> None:
    """Write a short markdown summary for the Actions UI."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "## Live contract",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| baseline | `{baseline}` |",
        f"| seeded | {str(seeded).lower()} |",
        f"| matched | {str(matched).lower()} |",
        f"| symbols | {symbol_count} |",
        f"| diffs | {len(diffs)} |",
        "",
    ]
    if diffs:
        lines.append("### Structural diffs")
        lines.append("")
        lines.extend(f"- `{item}`" for item in diffs[:50])
        if len(diffs) > 50:
            lines.append(f"- … and {len(diffs) - 50} more")
        lines.append("")
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    """CLI entry: collect live contract, seed or compare against baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path(os.environ.get("PYBO_BASELINE_DIR", str(DEFAULT_BASELINE_DIR))),
        help="Directory for live_contract.json (ENV: PYBO_BASELINE_DIR).",
    )
    parser.add_argument(
        "--write-current",
        type=Path,
        default=None,
        help="Write the current contract JSON here (CI artifact; does not overwrite baseline on drift).",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Always write the baseline from the current snapshot and exit 0.",
    )
    args = parser.parse_args(argv)

    email = require_env("PYBO_EMAIL")
    password = require_env("PYBO_PASSWORD")
    object_id = int(require_env("PYBO_OBJECT_ID"))
    modules = parse_modules(os.environ.get("PYBO_MODULES"))
    if not modules:
        raise SystemExit("Missing PYBO_MODULES: set a comma-separated module list.")
    lang = os.environ.get("PYBO_LANG", "en").strip() or "en"
    platform = os.environ.get("PYBO_PLATFORM", Platform.BRAGERONE.value).strip() or Platform.BRAGERONE.value

    try:
        contract = asyncio.run(
            collect_live_contract(
                email=email,
                password=password,
                object_id=object_id,
                modules=modules,
                lang=lang,
                platform=platform,
            )
        )
    except Exception as exc:
        print(f"live contract failed: {exc}", file=sys.stderr)
        return 1

    if args.write_current is not None:
        write_json(args.write_current, contract)

    baseline_path = args.baseline_dir / BASELINE_FILENAME

    if args.seed_only or not baseline_path.is_file():
        write_json(baseline_path, contract)
        print(
            json.dumps({"seeded": True, "baseline": str(baseline_path), "symbol_count": contract["symbol_count"]}, sort_keys=True)
        )
        write_github_output(seeded=True, matched=True, symbol_count=int(contract["symbol_count"]), diff_count=0)
        write_step_summary(
            seeded=True,
            matched=True,
            symbol_count=int(contract["symbol_count"]),
            diffs=[],
            baseline=baseline_path,
        )
        return 0

    baseline = read_json(baseline_path)
    diffs = compare_contracts(baseline, contract)
    matched = not diffs
    print(
        json.dumps(
            {
                "seeded": False,
                "matched": matched,
                "baseline": str(baseline_path),
                "symbol_count": contract["symbol_count"],
                "diff_count": len(diffs),
                "diffs": diffs[:100],
            },
            indent=2,
            sort_keys=True,
        )
    )
    write_github_output(
        seeded=False,
        matched=matched,
        symbol_count=int(contract["symbol_count"]),
        diff_count=len(diffs),
    )
    write_step_summary(
        seeded=False,
        matched=matched,
        symbol_count=int(contract["symbol_count"]),
        diffs=diffs,
        baseline=baseline_path,
    )
    if diffs:
        print(f"live contract drift: {len(diffs)} structural difference(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
