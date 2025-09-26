"""HTTP API client for BragerOne."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from types import SimpleNamespace
from aiohttp import (
    ClientSession,
    TraceConfig,
    TraceRequestStartParams,
    TraceRequestEndParams,
)

from collections.abc import Callable
from typing import Any, Optional

from .token_store import Token, TokenStore


LOG = logging.getLogger("pybragerone.api")
LOG_HTTP = logging.getLogger("pybragerone.http")

# TODO: add this endpoint?
# GET /v1/system/version?container=BragerOne&platform=0 → 200


class ApiError(RuntimeError):
    """Raised for non-2xx HTTP responses."""

    def __init__(self, status: int, data: Any, headers: dict[str, str] | None = None):
        super().__init__(f"HTTP {status}: {data!r}")
        self.status = status
        self.data = data
        self.headers = headers or {}


CredProvider = Callable[[], tuple[str, str]]  # -> (email, password)


class BragerOneApiClient:
    """HTTP API client with idempotent login and auto-refresh."""

    def __init__(
        self,
        base_url: str,
        *,
        token_store: TokenStore | None = None,
        enable_http_trace: bool = False,
        redact_secrets: bool = True,
        creds_provider: CredProvider | None = None,
        validate_on_start: bool = True,
        refresh_leeway: int = 90,
        origin: str = "https://one.brager.pl",
        referer: str = "https://one.brager.pl/",
    ):
        self._base = base_url.rstrip("/")
        self._session: ClientSession | None = None

        self._enable_http_trace = enable_http_trace
        self._redact_secrets = redact_secrets

        self._validate_on_start = validate_on_start
        self._refresh_leeway = refresh_leeway

        self._token: Token | None = None
        self._validated: bool = False
        self._token_loader: Optional[Callable[[], Optional[Token]]] = None
        self._token_saver: Optional[Callable[[Token], None]] = None
        self._token_clearer: Optional[Callable[[], None]] = None  # NEW
        self._skip_load_once = False

        if token_store is not None:
            self.set_token_store(token_store)

        self._creds_provider = creds_provider
        self._auth_lock = asyncio.Lock()

        self._origin = origin
        self._referer = referer

    # ----------------- session helpers -----------------

    def set_token_store(self, store: TokenStore | None) -> None:
        """Wire token persistence to a store that exposes load/save/clear."""
        if store is None:
            self._token_loader = None
            self._token_saver = None
            self._token_clearer = None
            return
        self._token_loader = store.load
        self._token_saver = store.save
        self._token_clearer = store.clear

    async def _ensure_session(self) -> ClientSession:
        if self._session and not self._session.closed:
            return self._session

        trace_configs: list[TraceConfig] = []
        if self._enable_http_trace:
            trace = TraceConfig()

            @trace.on_request_start.append
            async def _on_start(
                session: ClientSession,
                ctx: SimpleNamespace,
                params: TraceRequestStartParams,
            ) -> None:
                """Log the request.

                Args:
                    session: The aiohttp ClientSession.
                    ctx: The aiohttp TraceRequestStartParams.
                    params: The aiohttp TraceRequestStartParams.

                Returns:
                    None
                """
                safe_headers = dict(params.headers or {})
                if self._redact_secrets and "Authorization" in safe_headers:
                    safe_headers["Authorization"] = "<redacted>"
                LOG_HTTP.debug(
                    "→ %s %s headers=%s", params.method, params.url, safe_headers
                )

            @trace.on_request_end.append
            async def _on_end(
                session: ClientSession,
                ctx: SimpleNamespace,
                params: TraceRequestEndParams,
            ) -> None:
                """Log the response.

                Args:
                    session: The aiohttp ClientSession.
                    ctx: The aiohttp TraceRequestEndParams.
                    params: The aiohttp TraceRequestEndParams.

                Returns:
                    None
                """
                resp = params.response
                LOG_HTTP.debug("← %s %s → %s", params.method, params.url, resp.status)

            trace_configs.append(trace)

        self._session = ClientSession(
            headers={
                "Accept": "application/json",
                "Origin": self._origin,
                "Referer": self._referer,
            },
            trace_configs=trace_configs,
        )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ----------------- request -----------------

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
        sess = await self._ensure_session()
        url = f"{self._base}/{path.lstrip('/')}"
        hdrs = dict(headers or {})
        if auth:
            if not self._token or not self._token.access_token:
                raise ApiError(401, {"message": "No token"}, {})
            hdrs["Authorization"] = f"Bearer {self._token.access_token}"

        async with sess.request(
            method, url, json=json, data=data, headers=hdrs
        ) as resp:
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
            try:
                body = await (
                    resp.json(content_type=None)
                    if "application/json" in ctype
                    else resp.text()
                )
            except Exception:
                body = None

            if status == 401 and auth and _retry:
                LOG.debug("401 received — attempting token refresh & single retry")
                em, pw = (None, None)
                if self._creds_provider:
                    with contextlib.suppress(Exception):
                        em, pw = self._creds_provider()
                with contextlib.suppress(Exception):
                    await self.ensure_auth(em, pw)
                    return await self._req(
                        method,
                        path,
                        json=json,
                        data=data,
                        headers=headers,
                        auth=auth,
                        _retry=False,
                    )

            if status >= 400:
                raise ApiError(status, body, dict(resp.headers))

            return status, body, dict(resp.headers)

    # ----------------- auth -----------------

    async def ensure_auth(
        self, email: str | None = None, password: str | None = None
    ) -> Token:
        """Zapewnij ważny token: użyj cache + walidacji, a w razie braku/wygaszenia — zaloguj."""
        async with self._auth_lock:
            # 1) wczytaj z persistence (jeśli dostarczono loader)
            if self._token is None and self._token_loader and not self._skip_load_once:
                with contextlib.suppress(Exception):
                    self._token = self._token_loader()
            self._skip_load_once = False

            # 2) jeśli mamy token i nie wygasa — miękka walidacja (opcjonalna) i koniec
            if self._token and not self._token.is_expired(leeway=self._refresh_leeway):
                if self._validate_on_start and not self._validated:
                    try:
                        await self._try_validate()
                        return self._token
                    except ApiError as e:
                        if e.status in (401, 403):
                            self._token = None
                            self._validated = False
                        else:
                            raise
                else:
                    return self._token

            # 3) nie mamy tokenu → potrzebne poświadczenia
            em = email
            pw = password
            if (not em or not pw) and self._creds_provider:
                em, pw = self._creds_provider()
            if not em or not pw:
                raise ApiError(401, {"message": "No credentials for (re)login"}, {})

            # 4) klasyczny login
            return await self._post_login(em, pw)

    async def _do_login_request(
        self, email: str, password: str
    ) -> tuple[int, dict[str, Any] | None, dict[str, Any]]:
        return await self._req(
            "POST",
            "/v1/auth/user",
            json={"email": email, "password": password},
            auth=False,
        )

    async def _post_login(self, email: str, password: str) -> Token:
        """Zaloguj przez /v1/auth/user. Na 500/ER_DUP_ENTRY spróbuj krótki backoff i ponów."""
        import random

        delays = [0.2, 0.4, 0.8]  # sekundy

        for i, d in enumerate(delays + [None]):  # ostatnia próba bez sleepa po
            try:
                status, data, _ = await self._do_login_request(email, password)
            except ApiError as e:
                # tylko 500/duplikat próbujemy ponowić
                if (
                    e.status == 500
                    and self._is_duplicate_token_error(e.data)
                    and d is not None
                ):
                    jitter = random.uniform(0.0, 0.15)
                    await asyncio.sleep(d + jitter)
                    continue
                raise

            if not isinstance(data, dict):
                raise ApiError(500, {"message": "Unexpected login payload"}, {})

            tok = Token.from_login_payload(data)
            if not tok.access_token:
                raise ApiError(500, {"message": "No accessToken in login payload"}, {})

            self._token = tok
            self._validated = False
            if self._token_saver:
                with contextlib.suppress(Exception):
                    self._token_saver(tok)
            return tok

        # tu praktycznie nie trafisz, ale dla pewności:
        raise ApiError(500, {"message": "Login failed after retries"}, {})

    async def _try_validate(self) -> None:
        if not self._token:
            raise ApiError(401, {"message": "No token"}, {})
        try:
            status, _data, _hdrs = await self._req(
                "GET", "/v1/user", auth=True, _retry=False
            )
            if status == 200:
                self._validated = True
                return
        except ApiError as e:
            if e.status == 401:
                self._token = None
                self._validated = False
                raise
            raise
        self._validated = True

    @staticmethod
    def _is_duplicate_token_error(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        msg = str(data.get("message", "")).lower()
        return "duplicate entry" in msg or "er_dup_entry" in msg

    async def revoke(self) -> None:
        """Server-side logout + lokalny cleanup tokenu i persistence."""
        try:
            await self._req("POST", "/v1/auth/revoke", auth=True)
        except ApiError as e:
            if e.status not in (401, 403, 404):
                raise
        finally:
            # RAM
            self._token = None
            self._validated = False
            # PERSISTENCE
            if self._token_clearer:
                with contextlib.suppress(Exception):
                    self._token_clearer()
            # „nie ładuj od razu” na kolejnym ensure_auth w tym samym cyklu
            self._skip_load_once = True

    # ----------------- API endpoints -----------------

    async def objects_list(self) -> list[dict[str, Any]]:
        """GET /v1/objects → listę obiektów (z tolerancją na różne kształty)."""
        st, data, _ = await self._req("GET", "/v1/objects")
        if st != 200:
            return []
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return list(data["data"])
        if isinstance(data, dict) and isinstance(data.get("objects"), list):
            return list(data["objects"])
        if isinstance(data, list):
            return list(data)
        return []

    async def modules_list(self, object_id: int) -> list[dict[str, Any]]:
        """GET /v1/modules?page=1&limit=999&group_id=<object_id> → listę modułów."""
        path = f"/v1/modules?page=1&limit=999&group_id={object_id}"
        st, data, _ = await self._req("GET", path)
        if st != 200:
            return []
        # zwykle jest {data:[...]} lub po prostu lista
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return list(data["data"])
        if isinstance(data, list):
            return list(data)
        return []
