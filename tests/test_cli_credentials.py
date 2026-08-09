"""Tests for CLI credential resolution."""

from __future__ import annotations

import argparse

import pytest

from pybragerone.cli import _resolve_credentials


def _args(email: str | None = "u@example.com", password: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(email=email, password=password)


def test_existing_password_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicitly provided password is used without prompting."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def _boom(_prompt: str) -> str:
        raise AssertionError("getpass must not be called")

    monkeypatch.setattr("getpass.getpass", _boom)
    args = _args(password="secret")
    _resolve_credentials(args)
    assert args.password == "secret"


def test_password_prompted_when_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing password triggers a hidden prompt on a terminal."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "typed-secret")
    args = _args()
    _resolve_credentials(args)
    assert args.password == "typed-secret"


def test_password_missing_non_tty_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a terminal, a missing password exits instead of prompting."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    def _boom(_prompt: str) -> str:
        raise AssertionError("getpass must not be called")

    monkeypatch.setattr("getpass.getpass", _boom)
    with pytest.raises(SystemExit, match="Missing password"):
        _resolve_credentials(_args())


def test_empty_prompt_response_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty password entered at the prompt is rejected."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "")
    with pytest.raises(SystemExit, match="Missing password"):
        _resolve_credentials(_args())


def test_missing_email_exits() -> None:
    """Email is never prompted for; it must come from flag or env."""
    with pytest.raises(SystemExit, match="Missing email"):
        _resolve_credentials(_args(email=None))
