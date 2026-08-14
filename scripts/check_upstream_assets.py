"""Probe BragerOne public catalog (no login) and parse the live index when it changes.

Fetches unauthenticated ``GET /v1/system/version`` and the web-app homepage to
read the current ``index-*.js`` filename. Heavy tree-sitter parsing runs only
when that fingerprint is new or ``--always-parse`` is set.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, TextIO

from pybragerone import BragerOneApiClient
from pybragerone.models.api import SystemVersion
from pybragerone.models.catalog import (
    INDEX_ASSET_RE,
    LiveAssetsCatalog,
    ParamMap,
    _PUBLIC_PARAM_PATTERN,
    _count_js_escape_leaks,
)
from pybragerone.models.menu import MenuResult

_SAMPLE_LIMIT = 3
_ISSUE_FINGERPRINT_SEP = "|"
# Keep the upstream watch token gate identical to catalog leftover/helper matching.
_PARAM_TOKEN_RE = re.compile(_PUBLIC_PARAM_PATTERN)
_WATCH_MENU_PERMISSIONS = frozenset(
    {
        "DISPLAY_PARAMETER_LEVEL_1",
        "DISPLAY_PARAMETER_LEVEL_MAX",
        "DISPLAY_MENU_DHW",
    }
)


class _PublicCatalogClient(Protocol):
    """Minimal client surface used by the upstream catalog probe."""

    one_base: str

    async def get_system_version(self) -> SystemVersion:
        """Return the unauthenticated system version payload."""
        ...

    async def get_bytes(self, url: str) -> bytes:
        """Return raw bytes for a public URL."""
        ...

    async def close(self) -> None:
        """Close the HTTP session."""
        ...


@dataclass(slots=True)
class UpstreamProbe:
    """Public catalog fingerprint plus optional parse stats."""

    api_version: str
    dev_mode: bool
    index_asset: str
    index_url: str
    fingerprint: str
    previous_fingerprint: str | None
    changed: bool
    parse_skipped: bool
    basename_count: int
    menu_count: int
    language_ok: bool
    sample_param_tokens: list[str]
    sample_param_resolved: list[str]
    parse_error: str | None = None
    descriptor_table_count: int = 0
    units_count: int = 0
    escape_leaks: int = 0
    menu_gated_tokens: int = -1
    menu_permissions_ok: bool = True
    param_semantics_mangled: int = 0
    inline_param_tokens: int = -1


def build_fingerprint(*, api_version: str, index_asset: str) -> str:
    """Return a stable fingerprint of API version plus frontend index asset."""
    return f"{api_version.strip()}{_ISSUE_FINGERPRINT_SEP}{index_asset.strip()}"


def _count_mangled_permission_names(menu: MenuResult) -> int:
    """Count permission names that still look like leftover ``_0x…['NAME']`` text."""
    count = 0
    for permission in menu.all_permissions():
        name = permission.name
        if "_0x" in name or "['" in name or '["' in name:
            count += 1
    return count


def _count_mangled_param_semantics(param_maps: Mapping[str, ParamMap]) -> int:
    """Count sampled PARAM_* maps whose semantics still read as ``_0x…['NAME']`` text.

    A map that merely parses proves an object came back. Component type, status
    condition keys and command operations are what the resolver actually acts on,
    so those are the fields that must carry public names.
    """
    count = 0
    for param in param_maps.values():
        fields: list[str] = [str(param.component_type or "")]
        fields.extend(str(key) for key in (param.status_conditions or {}))
        for rule in param.command_rules:
            fields.append(str(rule.get("command") or ""))
            for condition in rule.get("conditions") or []:
                fields.append(str(condition.get("operation") or ""))
        if any("_0x" in field for field in fields):
            count += 1
    return count


def pick_sample_tokens(assets_by_basename: Mapping[str, object], *, limit: int) -> list[str]:
    """Prefer ``PARAM_66``, then other ``PARAM_*`` basenames, up to ``limit``."""
    names = list(assets_by_basename)
    preferred = [name for name in names if name == "PARAM_66"]
    rest = sorted(name for name in names if name.startswith("PARAM_") and name != "PARAM_66")
    return (preferred + rest)[:limit]


async def discover_index_asset(client: _PublicCatalogClient) -> str:
    """Read ``index-*.js`` from the public web-app homepage (no login)."""
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


async def probe_upstream(
    *,
    previous_fingerprint: str | None = None,
    sample_limit: int = _SAMPLE_LIMIT,
    always_parse: bool = False,
    client: _PublicCatalogClient | None = None,
) -> UpstreamProbe:
    """Fetch public version + index name, and parse the catalog when it changed."""
    own_client = client is None
    api: _PublicCatalogClient = client or BragerOneApiClient(validate_on_start=False)
    try:
        version = await api.get_system_version()
        index_asset = await discover_index_asset(api)
        index_url = f"{api.one_base.rstrip('/')}/assets/{index_asset}"
        fingerprint = build_fingerprint(api_version=version.version, index_asset=index_asset)
        changed = previous_fingerprint is None or previous_fingerprint != fingerprint
        probe = UpstreamProbe(
            api_version=version.version,
            dev_mode=bool(version.devMode),
            index_asset=index_asset,
            index_url=index_url,
            fingerprint=fingerprint,
            previous_fingerprint=previous_fingerprint,
            changed=changed,
            parse_skipped=not (changed or always_parse),
            basename_count=0,
            menu_count=0,
            language_ok=False,
            sample_param_tokens=[],
            sample_param_resolved=[],
            parse_error=None,
        )
        if probe.parse_skipped:
            return probe
        try:
            return await _parse_live_catalog(api, probe, sample_limit=sample_limit)
        except Exception as exc:
            probe.parse_error = str(exc)
            return probe
    finally:
        if own_client:
            await api.close()


async def _parse_live_catalog(api: _PublicCatalogClient, probe: UpstreamProbe, *, sample_limit: int) -> UpstreamProbe:
    """Download and tree-sitter-parse the live index (and a few PARAM_* assets)."""
    catalog = LiveAssetsCatalog(api)  # type: ignore[arg-type]
    await catalog.refresh_index(probe.index_url, allow_recover=False)
    language = await catalog.list_language_config()
    sample_tokens = pick_sample_tokens(catalog._idx.assets_by_basename, limit=sample_limit)
    resolved: list[str] = []
    if sample_tokens:
        mapping = await catalog.get_param_mapping(sample_tokens)
        resolved = sorted(mapping)
        probe.param_semantics_mangled = _count_mangled_param_semantics(mapping)
    table = catalog._parse_units_descriptor_table_from_index(catalog._idx.index_bytes)
    units = await catalog.get_i18n("en", "units")
    units_map = units if isinstance(units, dict) else {}
    probe.basename_count = len(catalog._idx.assets_by_basename)
    probe.menu_count = len(catalog._idx.menu_map)
    probe.language_ok = bool(language and language.translations and language.default_translation)
    probe.sample_param_tokens = sample_tokens
    probe.sample_param_resolved = resolved
    probe.descriptor_table_count = len(table)
    probe.units_count = len(units_map)
    probe.escape_leaks = _count_js_escape_leaks(units_map)
    # Inline tokens never appear as asset basenames, so `pick_sample_tokens` cannot reach
    # them. They were 91 of 100 descriptors on a live device, yet the watch stayed green
    # through a total outage of that path — count them explicitly.
    inline_maps = catalog._parse_index_token_raw_maps(catalog._idx.index_bytes)
    probe.inline_param_tokens = sum(1 for token in inline_maps if _PARAM_TOKEN_RE.fullmatch(token))
    if 0 in catalog._idx.menu_map:
        ungated = await catalog.get_module_menu(0, permissions=None)
        gated = await catalog.get_module_menu(0, permissions=_WATCH_MENU_PERMISSIONS)
        probe.menu_gated_tokens = len(gated.all_tokens())
        probe.menu_permissions_ok = _count_mangled_permission_names(ungated) == 0
    return probe


def read_fingerprint(path: Path | None) -> str | None:
    """Return the one-line fingerprint stored at ``path``, if any."""
    if path is None or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    return require_one_line(text, field="previous_fingerprint")


def require_one_line(value: str, *, field: str) -> str:
    """Reject CR/LF so GitHub Actions ``name=value`` output cannot be rewritten."""
    if "\n" in value or "\r" in value:
        raise RuntimeError(f"upstream probe: {field} must be a single line")
    return value


def write_github_output(probe: UpstreamProbe, stream: TextIO) -> None:
    """Append GitHub Actions outputs for the workflow notify step."""
    fingerprint = require_one_line(probe.fingerprint, field="fingerprint")
    previous = require_one_line(probe.previous_fingerprint or "", field="previous")
    api_version = require_one_line(probe.api_version, field="api_version")
    index_asset = require_one_line(probe.index_asset, field="index_asset")
    stream.write(f"changed={'true' if probe.changed else 'false'}\n")
    stream.write(f"parse_skipped={'true' if probe.parse_skipped else 'false'}\n")
    stream.write(f"fingerprint={fingerprint}\n")
    stream.write(f"previous={previous}\n")
    stream.write(f"api_version={api_version}\n")
    stream.write(f"index_asset={index_asset}\n")
    stream.write(f"language_ok={'true' if probe.language_ok else 'false'}\n")
    stream.write(f"descriptor_table_count={probe.descriptor_table_count}\n")
    stream.write(f"units_count={probe.units_count}\n")
    stream.write(f"escape_leaks={probe.escape_leaks}\n")
    stream.write(f"param_semantics_mangled={probe.param_semantics_mangled}\n")
    stream.write(f"inline_param_tokens={probe.inline_param_tokens}\n")


def assert_probe_ok(probe: UpstreamProbe) -> None:
    """Raise if the fingerprint or (when parsed) the live catalog looks empty."""
    if not probe.api_version:
        raise RuntimeError("upstream probe: empty API version")
    if INDEX_ASSET_RE.search(f"/assets/{probe.index_asset}") is None:
        raise RuntimeError(f"upstream probe: unexpected index asset {probe.index_asset!r}")
    if probe.parse_skipped:
        return
    if probe.parse_error:
        raise RuntimeError(f"upstream probe: live catalog parse failed: {probe.parse_error}")
    if probe.basename_count < 1:
        raise RuntimeError("upstream probe: live index parsed to zero asset basenames")
    if probe.sample_param_tokens and not probe.sample_param_resolved:
        raise RuntimeError(f"upstream probe: failed to parse sample params {probe.sample_param_tokens}")
    if probe.param_semantics_mangled:
        raise RuntimeError(
            f"upstream probe: {probe.param_semantics_mangled} sample PARAM_* maps still contain "
            "leftover _0x subscript text in component/status/operation"
        )
    if not probe.language_ok:
        raise RuntimeError("upstream probe: language config did not parse")
    if probe.descriptor_table_count < 1:
        raise RuntimeError("upstream probe: units descriptor table is empty")
    if probe.units_count < 1:
        raise RuntimeError("upstream probe: units i18n namespace is empty")
    if probe.escape_leaks:
        raise RuntimeError(f"upstream probe: {probe.escape_leaks} JS escape leaks in units i18n")
    if probe.inline_param_tokens == 0:
        raise RuntimeError(
            "upstream probe: no inline PARAM_*/STATUS_* tokens parsed from the index; the inline parameter shape changed again"
        )
    if probe.menu_gated_tokens >= 0:
        if not probe.menu_permissions_ok:
            raise RuntimeError("upstream probe: menu 0 permissionModule still contains leftover _0x subscript text")
        if probe.menu_gated_tokens < 1:
            raise RuntimeError("upstream probe: menu 0 gated by DISPLAY_* permissions yielded zero tokens")


def main(argv: list[str] | None = None) -> int:
    """CLI entry: probe public catalog and optionally persist the fingerprint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, default=None, help="File with the last fingerprint (one line).")
    parser.add_argument("--write", type=Path, default=None, help="Write the new fingerprint here after a successful probe.")
    parser.add_argument("--json-out", type=Path, default=None, help="Write the full probe JSON here.")
    parser.add_argument("--sample-limit", type=int, default=_SAMPLE_LIMIT, help="Max PARAM_* assets to fetch and parse.")
    parser.add_argument(
        "--always-parse",
        action="store_true",
        help="Parse the live index even when the fingerprint is unchanged.",
    )
    args = parser.parse_args(argv)

    try:
        previous = read_fingerprint(args.previous)
        probe = asyncio.run(
            probe_upstream(
                previous_fingerprint=previous,
                sample_limit=args.sample_limit,
                always_parse=args.always_parse,
            )
        )
    except Exception as exc:
        print(f"upstream probe failed: {exc}", file=sys.stderr)
        return 1

    payload = asdict(probe)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as handle:
            write_github_output(probe, handle)

    try:
        assert_probe_ok(probe)
    except Exception as exc:
        print(f"upstream probe failed: {exc}", file=sys.stderr)
        return 1

    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(probe.fingerprint + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
