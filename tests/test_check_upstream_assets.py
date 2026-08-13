"""Offline tests for ``scripts/check_upstream_assets.py``."""

from __future__ import annotations

import importlib.util
import io
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, TextIO, cast

import pytest

from pybragerone.models.api import SystemVersion

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_upstream_assets.py"
_INDEX_ASSET = "index-Ab12Cd.js"
_INDEX_JS = b'const x=()=>import("./module.menu-Xy9.js");'
_HOME_HTML = b'<script src="/assets/index-Ab12Cd.js"></script>'


class _UpstreamProbe(Protocol):
    """Probe dataclass fields used by the tests."""

    changed: bool
    parse_skipped: bool
    fingerprint: str
    previous_fingerprint: str | None
    basename_count: int
    parse_error: str | None


class _UpstreamScript(Protocol):
    """Typed surface of ``scripts/check_upstream_assets.py``."""

    def build_fingerprint(self, *, api_version: str, index_asset: str) -> str:
        """Build ``version|index-asset`` fingerprint."""
        ...

    def pick_sample_tokens(self, assets_by_basename: Mapping[str, object], *, limit: int) -> list[str]:
        """Pick PARAM_* sample tokens."""
        ...

    def write_github_output(self, probe: _UpstreamProbe, stream: TextIO) -> None:
        """Write GitHub Actions output lines."""
        ...

    def read_fingerprint(self, path: Path | None) -> str | None:
        """Read a stored fingerprint file."""
        ...

    def assert_probe_ok(self, probe: _UpstreamProbe) -> None:
        """Raise if the probe result is unusable."""
        ...

    async def probe_upstream(
        self,
        *,
        previous_fingerprint: str | None = None,
        sample_limit: int = 3,
        always_parse: bool = False,
        client: object | None = None,
    ) -> _UpstreamProbe:
        """Run the public catalog probe."""
        ...


def _load_upstream() -> _UpstreamScript:
    """Load the CI helper as a module (``scripts/`` is outside the pytest package)."""
    spec = importlib.util.spec_from_file_location("check_upstream_assets", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(_UpstreamScript, module)


class _FakePublicClient:
    """In-memory public catalog client for offline probe tests."""

    def __init__(self, *, version: str, pages: dict[str, bytes], assets: dict[str, bytes]) -> None:
        """Store canned version, HTML pages, and JS assets."""
        self.one_base = "https://one.brager.pl"
        self._version = version
        self._pages = pages
        self._assets = assets
        self.urls: list[str] = []

    async def get_system_version(self) -> SystemVersion:
        """Return a canned system version."""
        return SystemVersion(version=self._version, devMode=False)

    async def get_bytes(self, url: str) -> bytes:
        """Return canned bytes and record the URL."""
        self.urls.append(url)
        if url in self._pages:
            return self._pages[url]
        if url in self._assets:
            return self._assets[url]
        raise AssertionError(f"unexpected fetch {url}")

    async def close(self) -> None:
        """No-op close for the injected fake."""


def _client(*, version: str = "2.08") -> _FakePublicClient:
    """Build a fake client with a homepage hint and a tiny parseable index."""
    return _FakePublicClient(
        version=version,
        pages={
            "https://one.brager.pl/": _HOME_HTML,
            "https://one.brager.pl/assets/": _HOME_HTML,
        },
        assets={
            f"https://one.brager.pl/assets/{_INDEX_ASSET}": _INDEX_JS,
        },
    )


def test_build_fingerprint_strips_whitespace() -> None:
    """Fingerprint is ``version|index-asset`` with surrounding whitespace stripped."""
    build = _load_upstream().build_fingerprint
    assert build(api_version=" 2.08 ", index_asset=" index-Ab.js ") == "2.08|index-Ab.js"


def test_pick_sample_tokens_prefers_param_66() -> None:
    """Sample list starts with ``PARAM_66`` when present, then other ``PARAM_*`` names."""
    pick = _load_upstream().pick_sample_tokens
    names = {"STATUS_P5": object(), "PARAM_99": object(), "PARAM_66": object(), "PARAM_01": object()}
    assert pick(names, limit=2) == ["PARAM_66", "PARAM_01"]
    assert pick({"menu": object()}, limit=3) == []


@pytest.mark.asyncio
async def test_github_output_and_fingerprint_file(tmp_path: Path) -> None:
    """GitHub output lines and on-disk fingerprint stay one-line and stable."""
    module = _load_upstream()
    probe = await module.probe_upstream(
        previous_fingerprint=f"2.08|{_INDEX_ASSET}",
        client=_client(),
    )
    buf = io.StringIO()
    module.write_github_output(probe, buf)
    text = buf.getvalue()
    assert "changed=false\n" in text
    assert f"fingerprint=2.08|{_INDEX_ASSET}\n" in text
    assert f"previous=2.08|{_INDEX_ASSET}\n" in text

    path = tmp_path / "fingerprint.txt"
    path.write_text("stale\n", encoding="utf-8")
    assert module.read_fingerprint(path) == "stale"
    assert module.read_fingerprint(tmp_path / "missing.txt") is None


@pytest.mark.asyncio
async def test_probe_skips_index_download_when_fingerprint_matches() -> None:
    """Unchanged fingerprint must not fetch ``index-*.js`` or PARAM assets."""
    module = _load_upstream()
    client = _client()
    probe = await module.probe_upstream(
        previous_fingerprint=f"2.08|{_INDEX_ASSET}",
        client=client,
    )
    assert probe.changed is False
    assert probe.parse_skipped is True
    assert probe.fingerprint == f"2.08|{_INDEX_ASSET}"
    assert all(_INDEX_ASSET not in url for url in client.urls)
    module.assert_probe_ok(probe)


@pytest.mark.asyncio
async def test_probe_parses_index_when_fingerprint_changes() -> None:
    """A new fingerprint downloads the index and requires at least one basename."""
    module = _load_upstream()
    client = _client()
    probe = await module.probe_upstream(
        previous_fingerprint="1.0|index-old.js",
        client=client,
    )
    assert probe.changed is True
    assert probe.parse_skipped is False
    assert probe.basename_count >= 1
    assert any(url.endswith(_INDEX_ASSET) for url in client.urls)
    module.assert_probe_ok(probe)


@pytest.mark.asyncio
async def test_probe_first_run_parses_without_previous() -> None:
    """Missing baseline still parses so the first CI run verifies the live catalog."""
    module = _load_upstream()
    probe = await module.probe_upstream(client=_client())
    assert probe.previous_fingerprint is None
    assert probe.changed is True
    assert probe.parse_skipped is False
    assert probe.basename_count >= 1


@pytest.mark.asyncio
async def test_probe_keeps_fingerprint_when_index_parse_fails() -> None:
    """Parse errors after fingerprinting still return outputs for the workflow."""
    module = _load_upstream()
    client = _FakePublicClient(
        version="2.08",
        pages={
            "https://one.brager.pl/": _HOME_HTML,
            "https://one.brager.pl/assets/": _HOME_HTML,
        },
        assets={},
    )
    probe = await module.probe_upstream(
        previous_fingerprint="1.0|index-old.js",
        client=client,
    )
    assert probe.changed is True
    assert probe.parse_skipped is False
    assert probe.fingerprint == f"2.08|{_INDEX_ASSET}"
    assert probe.basename_count == 0
    assert probe.parse_error
    buf = io.StringIO()
    module.write_github_output(probe, buf)
    assert f"fingerprint=2.08|{_INDEX_ASSET}\n" in buf.getvalue()
    assert "changed=true\n" in buf.getvalue()
    with pytest.raises(RuntimeError, match="live catalog parse failed"):
        module.assert_probe_ok(probe)
