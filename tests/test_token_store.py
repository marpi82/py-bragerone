"""Tests for CLI and Home Assistant token persistence adapters."""

from __future__ import annotations

import json
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from pybragerone.models.token import CLITokenStore, HATokenStore, Token


class _FakeKeyring:
    """In-memory stand-in for the optional keyring backend."""

    def __init__(self) -> None:
        """Initialize empty keyring storage."""
        self.payload: str | None = None
        self.deleted = False

    def get_password(self, service: str, username: str) -> str | None:
        """Return the stored payload, if any."""
        del service, username
        return self.payload

    def set_password(self, service: str, username: str, password: str) -> None:
        """Persist a payload string."""
        del service, username
        self.payload = password
        self.deleted = False

    def delete_password(self, service: str, username: str) -> None:
        """Forget the stored payload."""
        del service, username
        self.payload = None
        self.deleted = True


def test_cli_token_store_file_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without keyring, tokens are stored in a 0600 file under XDG_CONFIG_HOME."""
    monkeypatch.setattr("pybragerone.models.token._HAS_KEYRING", False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    store = CLITokenStore(email="user@example.com")
    assert store.load() is None

    token = Token(access_token="tok", refresh_token="ref", objects=[{"id": 1}])
    store.save(token)

    path = tmp_path / "pybragerone" / "token-user@example.com.json"
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "tok"
    assert loaded.refresh_token == "ref"
    assert loaded.objects == [{"id": 1}]

    store.clear()
    assert store.load() is None
    assert not path.exists()


def test_cli_token_store_ignores_corrupt_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Unreadable JSON in the fallback file is treated as a cache miss."""
    monkeypatch.setattr("pybragerone.models.token._HAS_KEYRING", False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    store = CLITokenStore(email="user@example.com")
    path = store._file_path()
    path.write_text("not-json", encoding="utf-8")
    assert store.load() is None


def test_cli_token_store_prefers_keyring(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When keyring is available, load/save/clear go there and skip the file."""
    fake = _FakeKeyring()
    monkeypatch.setattr("pybragerone.models.token._HAS_KEYRING", True)
    monkeypatch.setattr("pybragerone.models.token.keyring", fake)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    store = CLITokenStore(email="user@example.com")
    store.save(Token(access_token="from-kr"))
    assert fake.payload is not None
    assert json.loads(fake.payload)["access_token"] == "from-kr"
    assert not (tmp_path / "pybragerone" / "token-user@example.com.json").exists()

    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "from-kr"

    store.clear()
    assert fake.deleted is True
    assert store.load() is None


def test_cli_token_store_keyring_invalid_json_falls_back_to_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Corrupt keyring data is ignored; a valid fallback file still loads."""
    fake = _FakeKeyring()
    fake.payload = "not-json"
    monkeypatch.setattr("pybragerone.models.token._HAS_KEYRING", True)
    monkeypatch.setattr("pybragerone.models.token.keyring", fake)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    store = CLITokenStore(email="user@example.com")
    path = store._file_path()
    path.write_text(json.dumps({"access_token": "file-tok"}), encoding="utf-8")

    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "file-tok"


def test_ha_token_store_load_save_clear() -> None:
    """HA adapter loads dicts, invokes saver/clearer, and swallows callback errors."""
    stored: dict[str, Any] | None = None
    saved: list[Token] = []
    cleared = False

    def loader() -> dict[str, Any] | None:
        return stored

    def saver(token: Token) -> None:
        saved.append(token)

    def clearer() -> None:
        nonlocal cleared
        cleared = True

    # Runtime accepts dict payloads; the annotated loader type is Token | None.
    store = HATokenStore(loader=cast(Callable[[], Token | None], loader), saver=saver, clearer=clearer)
    assert store.load() is None

    stored = {"access_token": "ha-tok", "objects": [{"id": 9}]}
    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "ha-tok"
    assert loaded.objects == [{"id": 9}]

    store.save(Token(access_token="abc"))
    assert saved

    store.clear()
    assert cleared is True


def test_ha_token_store_swallows_callback_failures() -> None:
    """Loader/saver/clearer exceptions must not propagate."""

    def boom() -> Token | None:
        raise RuntimeError("storage down")

    def boom_save(_token: Token) -> None:
        raise RuntimeError("cannot save")

    store = HATokenStore(loader=boom, saver=boom_save, clearer=boom)
    assert store.load() is None
    store.save(Token(access_token="x"))
    store.clear()


def test_ha_token_store_rejects_non_dict_loader() -> None:
    """A loader that returns a Token (or other non-dict) is a cache miss."""

    def loader() -> Token:
        return Token(access_token="nope")

    store = HATokenStore(loader=loader, saver=lambda _t: None, clearer=lambda: None)
    assert store.load() is None
