"""Token storage implementations for pybragerone."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

try:
    import keyring  # type: ignore

    _HAS_KEYRING = True
except Exception:
    _HAS_KEYRING = False

log = logging.getLogger(__name__)


class Token(BaseModel):
    """Authentication token payload returned by POST /v1/auth/user."""

    access_token: str | None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_at: datetime | None = None
    user_id: int | None = None
    objects: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(frozen=False)

    @classmethod
    def from_login_payload(cls, data: dict[str, Any]) -> Token:
        """Create a Token instance from a login response payload."""
        exp_raw = data.get("expiresAt")
        exp_dt: datetime | None = None
        if exp_raw:
            with contextlib.suppress(Exception):
                exp_dt = datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
        return cls(
            access_token=data.get("accessToken") or data.get("token") or "",
            refresh_token=data.get("refreshToken"),
            token_type=(data.get("type") or "bearer"),
            expires_at=exp_dt,
            user_id=(data.get("user", {}) or {}).get("id") or None,
            objects=data.get("objects") or [],
        )

    def is_expired(self, *, leeway: int = 60) -> bool:
        """Return True if the token is expired or will expire within `leeway` seconds."""
        if not self.expires_at:
            return False
        now = datetime.now(UTC)
        return now + timedelta(seconds=leeway) >= self.expires_at


@runtime_checkable
class TokenStore(Protocol):
    """Abstract persistence for auth tokens."""

    def load(self) -> Token | None:
        """Return a cached Token or None if not present."""
        ...

    def save(self, token: Token) -> None:
        """Persist the Token atomically."""
        ...

    def clear(self) -> None:
        """Remove any persisted token."""
        ...


# ---------- CLI IMPLEMENTATION ----------


@dataclass
class CLITokenStore:
    """Token persistence for CLI.

    Preference order:
      1) system keyring (if available)
      2) file at ~/.config/pybragerone/token-<email>.json (0600)
    """

    email: str
    service: str = "pybragerone"

    def _file_path(self) -> Path:
        """Return the path to the fallback token file."""
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
        d = base / "pybragerone"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"token-{self.email}.json"

    @staticmethod
    def _write_file_secure(p: Path, content: str) -> None:
        """Write a file with 0600 permissions, ignoring errors."""
        p.write_text(content, encoding="utf-8")
        with contextlib.suppress(Exception):
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

    def load(self) -> Token | None:
        """Return a cached Token or None if not present."""
        # 1) keyring
        if _HAS_KEYRING:
            raw = keyring.get_password(
                self.service, self.email
            )  # -type: ignore[attr-defined]
            if raw:
                with contextlib.suppress(Exception):
                    data = json.loads(raw)
                    return self._to_token(data)
        # 2) fallback file
        p = self._file_path()
        if p.exists():
            with contextlib.suppress(Exception):
                data = json.loads(p.read_text("utf-8"))
                return self._to_token(data)
        return None

    def save(self, token: Token) -> None:
        """Persist the Token atomically."""
        payload = json.dumps(
            {
                "access_token": getattr(token, "access_token", None),
                "token_type": getattr(token, "token_type", "bearer"),
                "refresh_token": getattr(token, "refresh_token", None),
                "expires_at": getattr(token, "expires_at", None),
                "objects": getattr(token, "objects", []) or [],
            },
            ensure_ascii=False,
        )
        if _HAS_KEYRING:
            keyring.set_password(self.service, self.email, payload)
            return
        self._write_file_secure(self._file_path(), payload)

    def clear(self) -> None:
        """Remove any persisted token."""
        if _HAS_KEYRING:
            with contextlib.suppress(Exception):
                keyring.delete_password(self.service, self.email)
        with contextlib.suppress(Exception):
            self._file_path().unlink()

    @staticmethod
    def _to_token(data: dict[str, Any]) -> Token:
        """Convert a dict to a Token instance, ignoring errors."""
        return Token(
            access_token=data.get("access_token"),
            token_type=data.get("token_type", "bearer"),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at"),
            objects=data.get("objects") or [],
        )


# ---------- HA EXAMPLE IMPLEMENTATION ----------


class HATokenStore(TokenStore):
    """Minimal example adapter for Home Assistant storage.

    Expects an object with async load/save/clear; wraps sync API expected by BragerOneApiClient.
    Replace with your concrete implementation in the HA integration.
    """

    def __init__(
        self,
        loader: Callable[[], Token | None],
        saver: Callable[[Token], None],
        clearer: Callable[[], None],
    ) -> None:
        """Initialize with callables to load/save/clear the token.

        Args:
            loader: Callable that returns a Token or None.
            saver: Callable that takes a Token and persists it.
            clearer: Callable that removes any persisted token.

        Returns: None
        """
        # Callables supplied by HA layer:
        #   loader: () -> Optional[dict]
        #   saver: (dict) -> None
        #   clearer: () -> None
        self._loader = loader
        self._saver = saver
        self._clearer = clearer

    def load(self) -> Token | None:
        """Return a cached Token or None if not present."""
        data = None
        with contextlib.suppress(Exception):
            data = self._loader()
        if not isinstance(data, dict):
            return None

        return Token(
            access_token=data.get("access_token"),
            token_type=data.get("token_type", "bearer"),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at"),
            objects=data.get("objects") or [],
        )

    def save(self, token: Token) -> None:
        """Persist the Token atomically."""
        payload = {
            "access_token": getattr(token, "access_token", None),
            "token_type": getattr(token, "token_type", "bearer"),
            "refresh_token": getattr(token, "refresh_token", None),
            "expires_at": getattr(token, "expires_at", None),
            "objects": getattr(token, "objects", []) or [],
        }
        with contextlib.suppress(Exception):
            self._saver(Token.from_login_payload(payload))

    def clear(self) -> None:
        """Remove any persisted token."""
        with contextlib.suppress(Exception):
            self._clearer()
