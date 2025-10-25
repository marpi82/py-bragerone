"""HTTP API client for BragerOne."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from pybragerone.models.api import (
    AuthResponse,
    BragerObject,
    Module,
    ModuleCard,
    ObjectDetails,
    Permission,
    SystemVersion,
    User,
)

from ..models.token import Token, TokenStore
from .constants import ONE_BASE
from .endpoints import (
    auth_revoke_url,
    auth_user_url,
    module_card_url,
    modules_activity_quantity_url,
    modules_connect_url,
    modules_parameters_url,
    modules_url,
    object_permissions_url,
    object_url,
    objects_url,
    system_version_url,
    user_permissions_url,
    user_url,
)

LOG = logging.getLogger("pybragerone.api")
LOG_HTTP = logging.getLogger("pybragerone.http")


class ApiError(RuntimeError):
    """Raised for non-2xx HTTP responses.

    Attributes:
        status: HTTP status code.
        data: Response data.
        headers: Response headers.
    """

    def __init__(self, status: int, data: Any, headers: dict[str, str] | None = None):
        """Initialize the API error.

        Args:
            status: HTTP status code.
            data: Response data.
            headers: Response headers dictionary.
        """
        super().__init__(f"HTTP {status}: {data!r}")
        self.status = status
        self.data = data
        self.headers = headers or {}


class HttpCache:
    """Simple HTTP cache using ETag/Last-Modified headers with in-memory body storage.

    This cache implementation stores response bodies along with their cache headers
    to enable efficient HTTP caching with proper conditional request handling.
    """

    def __init__(self) -> None:
        """Initialize an empty HTTP cache.

        Creates an empty cache store that maps URLs to tuples containing
        ETag, Last-Modified, and response body data.
        """
        self._store: dict[str, tuple[str | None, str | None, bytes]] = {}

    def headers_for(self, url: str) -> dict[str, str]:
        """Generate conditional request headers for cached URL.

        Returns appropriate If-None-Match and If-Modified-Since headers
        based on cached ETag and Last-Modified values for the given URL.

        Args:
            url: The URL to generate headers for.

        Returns:
            Dictionary of conditional headers to include in the request.
        """
        etag, last_mod, _ = self._store.get(url, (None, None, b""))
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_mod:
            headers["If-Modified-Since"] = last_mod
        return headers

    def update(self, url: str, headers: Mapping[str, str], body: bytes) -> None:
        """Update cache entry with response data.

        Stores the response body along with ETag and Last-Modified headers
        for the given URL to enable future conditional requests.

        Args:
            url: The URL being cached.
            headers: Response headers containing cache information.
            body: The response body to cache.
        """
        etag = headers.get("ETag")
        last_mod = headers.get("Last-Modified")
        self._store[url] = (etag, last_mod, body)

    def get_body(self, url: str) -> bytes | None:
        """Retrieve cached response body for URL.

        Args:
            url: The URL to retrieve the cached body for.

        Returns:
            Cached response body as bytes, or None if not cached.
        """
        val = self._store.get(url)
        return val[2] if val else None


CredProvider = Callable[[], tuple[str, str]]  # -> (email, password)


class BragerOneApiClient:
    """HTTP API client with idempotent login and auto-refresh.

    Provides a comprehensive HTTP client for the BragerOne API with automatic
    token management, authentication, and retry logic.
    """

    def __init__(
        self,
        *,
        token_store: TokenStore | None = None,
        enable_http_trace: bool = False,
        redact_secrets: bool = True,
        creds_provider: CredProvider | None = None,
        validate_on_start: bool = True,
        refresh_leeway: int = 90,
        timeout: float = 8.0,
        concurrency: int = 4,
    ):
        """Initialize the API client.

        Args:
            token_store: Optional token storage for persistence.
            enable_http_trace: Whether to enable HTTP request/response tracing.
            redact_secrets: Whether to redact sensitive information in logs.
            creds_provider: Function that provides email/password credentials.
            validate_on_start: Whether to validate tokens on first use.
            refresh_leeway: Time in seconds before token expiry to refresh.
            timeout: Request timeout in seconds.
            concurrency: Maximum number of concurrent requests.
        """
        self._session: httpx.AsyncClient | None = None

        self._enable_http_trace = enable_http_trace
        self._redact_secrets = redact_secrets

        self._validate_on_start = validate_on_start
        self._refresh_leeway = refresh_leeway

        self._token: Token | None = None
        self._validated: bool = False
        self._token_loader: Callable[[], Token | None] | None = None
        self._token_saver: Callable[[Token], None] | None = None
        self._token_clearer: Callable[[], None] | None = None  # NEW
        self._skip_load_once = False

        if token_store is not None:
            self.set_token_store(token_store)

        self._creds_provider = creds_provider
        self._auth_lock = asyncio.Lock()
        self._connect_variant: dict[str, Any] | None = None

        self._cache = HttpCache()
        self._timeout = timeout
        self._sem = asyncio.Semaphore(concurrency)

    # ----------------- session helpers -----------------

    def set_token_store(self, store: TokenStore | None) -> None:
        """Wire token persistence to a store that exposes load/save/clear.

        Args:
            store: Token storage instance or None to disable persistence.
        """
        if store is None:
            self._token_loader = None
            self._token_saver = None
            self._token_clearer = None
            return
        self._token_loader = store.load
        self._token_saver = store.save
        self._token_clearer = store.clear

    async def _ensure_session(self) -> httpx.AsyncClient:
        """Ensure we have an AsyncClient (with optional HTTP tracing).

        Returns:
            An active httpx AsyncClient with configured headers and event hooks.
        """
        if self._session and not self._session.is_closed:
            return self._session

        # Configure default headers
        headers = {"Origin": ONE_BASE, "Referer": f"{ONE_BASE}/"}

        # Configure timeout
        timeout = httpx.Timeout(self._timeout)

        # Create client
        self._session = httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

        # Add HTTP tracing event hooks if enabled
        if self._enable_http_trace:
            self._session.event_hooks = {
                "request": [self._log_request],
                "response": [self._log_response],
            }

        return self._session

    async def _log_request(self, request: httpx.Request) -> None:
        """Log HTTP request for tracing.

        Args:
            request: The httpx Request object.
        """
        safe_headers = dict(request.headers)
        if self._redact_secrets and "Authorization" in safe_headers:
            safe_headers["Authorization"] = "<redacted>"
        LOG_HTTP.debug("→ %s %s headers=%s", request.method, request.url, safe_headers)

    async def _log_response(self, response: httpx.Response) -> None:
        """Log HTTP response for tracing.

        Args:
            response: The httpx Response object.
        """
        LOG_HTTP.debug("← %s %s → %s", response.request.method, response.request.url, response.status_code)

    async def close(self) -> None:
        """Close the underlying HTTP session.

        This should be called when the client is no longer needed to properly
        release resources.
        """
        if self._session and not self._session.is_closed:
            await self._session.aclose()

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
        """Perform an HTTP request with optional auth and auto-refresh on 401.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: Request path/URL.
            json: JSON payload for the request body.
            data: Form data for the request body.
            headers: Additional HTTP headers.
            auth: Whether to include authentication headers.
            _retry: Whether to retry on authentication failure.

        Returns:
            Tuple of (status_code, response_data, response_headers).

        Raises:
            ApiError: For HTTP error responses (4xx/5xx).
        """
        sess = await self._ensure_session()
        hdrs = dict(headers or {})
        hdrs["Accept"] = "application/json"
        if auth:
            if not self._token or not self._token.access_token:
                raise ApiError(401, {"message": "No token"}, {})
            hdrs["Authorization"] = f"Bearer {self._token.access_token}"

        resp = await sess.request(method, path, json=json, data=data, headers=hdrs)
        status = resp.status_code
        ctype = resp.headers.get("Content-Type", "")
        try:
            body = resp.json() if "application/json" in ctype else resp.text
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

    # -------- SYSTEM --------

    async def get_system_version(self) -> SystemVersion:
        """Get system version information.

        Returns:
            System version information as a Pydantic model.

        Raises:
            ApiError: If the request fails.
        """
        status, data, _ = await self._req("GET", system_version_url(), auth=False)
        if status != 200:
            raise ApiError(status, data)
        if not isinstance(data, dict):
            raise ApiError(500, {"message": "Unexpected version payload"}, {})
        # API returns {"version": {...}}, extract the inner object
        version_data = data.get("version", data)
        return SystemVersion.model_validate(version_data)

    # ----------------- AUTH -----------------

    async def ensure_auth(self, email: str | None = None, password: str | None = None) -> Token:
        """Ensure valid token: use cache + validation, and if missing/expired — login.

        Args:
            email: User email for authentication.
            password: User password for authentication.

        Returns:
            Valid authentication token.

        Raises:
            ApiError: If authentication fails or credentials are missing.
        """
        async with self._auth_lock:
            # 1) load from persistence (if loader provided)
            if self._token is None and self._token_loader and not self._skip_load_once:
                with contextlib.suppress(Exception):
                    self._token = self._token_loader()
            self._skip_load_once = False

            # 2) if we have token and it's not expired — soft validation (optional) and done
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

            # 3) no token → need credentials
            em = email
            pw = password
            if (not em or not pw) and self._creds_provider:
                em, pw = self._creds_provider()
            if not em or not pw:
                raise ApiError(401, {"message": "No credentials for (re)login"}, {})

            # 4) classic login
            return await self._post_login(em, pw)

    async def _do_login_request(self, email: str, password: str) -> AuthResponse:
        """Execute login request to the authentication endpoint.

        Args:
            email: User email address.
            password: User password.

        Returns:
            Authentication response as a Pydantic model.

        Raises:
            ApiError: If the request fails.
        """
        status, data, _ = await self._req(
            "POST",
            auth_user_url(),
            json={"email": email, "password": password},
            auth=False,
        )
        if status != 200:
            raise ApiError(status, data)
        if not isinstance(data, dict):
            raise ApiError(500, {"message": "Unexpected login payload"}, {})
        return AuthResponse.model_validate(data)

    async def _post_login(self, email: str, password: str) -> Token:
        """Login via /v1/auth/user. On 500/ER_DUP_ENTRY try short backoff and retry.

        Args:
            email: User email address.
            password: User password.

        Returns:
            Authentication token.

        Raises:
            ApiError: If login fails after all retries.
        """
        import random

        delays = [0.2, 0.4, 0.8]  # seconds

        for _, d in enumerate([*delays, None]):  # last attempt without sleep after
            try:
                auth_response = await self._do_login_request(email, password)
            except ApiError as e:
                # only retry 500/duplicate errors
                if e.status == 500 and self._is_duplicate_token_error(e.data) and d is not None:
                    jitter = random.uniform(0.0, 0.15)  # nosec B311 - non-cryptographic jitter for retry backoff
                    await asyncio.sleep(d + jitter)
                    continue
                raise

            # Convert AuthResponse to Token using existing method
            tok = Token.from_login_payload(auth_response.model_dump())
            if not tok.access_token:
                raise ApiError(500, {"message": "No accessToken in login payload"}, {})

            self._token = tok
            self._validated = False
            if self._token_saver:
                with contextlib.suppress(Exception):
                    self._token_saver(tok)
            return tok

        # practically won't reach here, but for safety:
        raise ApiError(500, {"message": "Login failed after retries"}, {})

    async def _try_validate(self) -> None:
        """Try to validate the current token by making a test request.

        Raises:
            ApiError: If validation fails or token is invalid.
        """
        if not self._token:
            raise ApiError(401, {"message": "No token"}, {})
        try:
            status, _data, _hdrs = await self._req("GET", user_url(), auth=True, _retry=False)
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
        """Check if error response indicates a duplicate token error.

        Args:
            data: Error response data.

        Returns:
            True if this is a duplicate token error.
        """
        if not isinstance(data, dict):
            return False
        msg = str(data.get("message", "")).lower()
        return "duplicate entry" in msg or "er_dup_entry" in msg

    async def revoke(self) -> None:
        """Server-side logout + local cleanup of token and persistence.

        Attempts to revoke the token on the server and cleans up local state
        regardless of server response.
        """
        try:
            await self._req("POST", auth_revoke_url(), auth=True)
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
            # "don't load immediately" on the next ensure_auth in the same cycle
            self._skip_load_once = True

    # -------- USER --------

    async def get_user(self) -> User:
        """Get current user information.

        Returns:
            User information as a Pydantic model.

        Raises:
            ApiError: If the request fails.
        """
        status, data, _ = await self._req("GET", user_url())
        if status != 200:
            raise ApiError(status, data)
        if not isinstance(data, dict):
            raise ApiError(500, {"message": "Unexpected user payload"}, {})
        # API returns {"user": {...}}, extract the inner object
        user_data = data.get("user", data)
        return User.model_validate(user_data)

    async def get_user_permissions(self) -> list[Permission]:
        """Get current user permissions.

        Returns:
            List of user permissions.

        Raises:
            ApiError: If the request fails.
        """
        status, data, _ = await self._req("GET", user_permissions_url())
        if status != 200:
            raise ApiError(status, data)
        # API returns {"permissions": [...]} format
        permissions_list: list[str] = []
        if isinstance(data, dict):
            permissions_list = data.get("permissions", [])
        elif isinstance(data, list):
            permissions_list = data
        # Convert strings to Permission objects
        return [Permission.model_validate(perm) for perm in permissions_list]

    # -------- OBJECTS --------

    async def get_objects(self) -> list[BragerObject]:
        """GET /v1/objects → list of objects (with tolerance for different shapes).

        Returns:
            List of BragerObject models.
        """
        st, data, _ = await self._req("GET", objects_url())
        if st != 200:
            return []

        # Extract objects array from different response formats
        objects_data = []
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            objects_data = data["data"]
        elif isinstance(data, dict) and isinstance(data.get("objects"), list):
            objects_data = data["objects"]
        elif isinstance(data, list):
            objects_data = data

        # Convert to Pydantic models
        return [BragerObject.model_validate(obj) for obj in objects_data]

    async def get_object(self, object_id: int) -> ObjectDetails:
        """Get object by ID.

        Args:
            object_id: The object identifier.

        Returns:
            Object details with operational status.

        Raises:
            ApiError: If the request fails.
        """
        status, data, _ = await self._req("GET", object_url(object_id))
        if status != 200:
            raise ApiError(status, data)
        if not isinstance(data, dict):
            raise ApiError(500, {"message": "Unexpected object payload"}, {})
        return ObjectDetails.model_validate(data)

    async def get_object_permissions(self, object_id: int) -> list[Permission]:
        """Get object-specific permissions for the current user.

        Args:
            object_id: The ID of the object to get permissions for.

        Returns:
            List of object-specific permissions.

        Raises:
            ApiError: If the request fails.
        """
        status, data, _ = await self._req("GET", object_permissions_url(object_id))
        if status != 200:
            raise ApiError(status, data)
        # API returns {"permissions": [...]} format
        permissions_list: list[str] = []
        if isinstance(data, dict):
            permissions_list = data.get("permissions", [])
        elif isinstance(data, list):
            permissions_list = data
        # Convert strings to Permission objects
        return [Permission.model_validate(perm) for perm in permissions_list]

    # -------- MODULES --------

    async def get_modules(self, object_id: int) -> list[Module]:
        """GET /v1/modules?page=1&limit=999&group_id=<object_id> → list of modules.

        Args:
            object_id: The object/group identifier.

        Returns:
            List of Module models.
        """
        st, data, _ = await self._req("GET", modules_url(object_id))
        if st != 200:
            return []

        # Extract modules array from different response formats
        modules_data = []
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            modules_data = data["data"]
        elif isinstance(data, list):
            modules_data = data

        # Convert to Pydantic models
        return [Module.model_validate(mod) for mod in modules_data]

    async def get_module_card(self, code: str) -> ModuleCard:
        """Get module card information by code.

        Args:
            code: The module code identifier.

        Returns:
            Module card information as a Pydantic model.

        Raises:
            ApiError: If the request fails.
        """
        status, data, _ = await self._req("GET", module_card_url(code))
        if status != 200:
            raise ApiError(status, data)
        if not isinstance(data, dict):
            raise ApiError(500, {"message": "Unexpected module card payload"}, {})
        return ModuleCard.model_validate(data)

    async def modules_connect(
        self,
        wsid_ns: str,
        modules: list[str],
        group_id: int | None = None,
        engine_sid: str | None = None,
    ) -> bool:
        """Connect to modules via WebSocket.

        Args:
            wsid_ns: WebSocket namespace ID.
            modules: List of module codes to connect to.
            group_id: Optional group/object ID.
            engine_sid: Optional engine session ID as fallback.

        Returns:
            True if connection successful, False otherwise.
        """
        if not modules:
            return True
        modules = sorted(set(modules))
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }

        def bodies(pref_sid: str) -> list[dict[str, Any]]:
            """Generate candidate request bodies for module connection."""
            arr = [
                {"wsid": pref_sid, "modules": modules},
                {"sid": pref_sid, "modules": modules},
            ]
            if group_id is not None:
                arr.append({"wsid": pref_sid, "group_id": str(group_id), "modules": modules})
            return arr

        candidates: list[dict[str, Any]] = []
        if self._connect_variant:
            candidates.append(self._connect_variant)

        # 1) namespace SID
        if wsid_ns:
            for body in bodies(wsid_ns):
                candidates.append(body)
        # 2) engine SID (fallback)
        if engine_sid:
            for body in bodies(engine_sid):
                candidates.append(body)

        # de-dupe
        seen: set[str] = set()
        uniq: list[dict[str, Any]] = []
        for c in candidates:
            # hash payload "shape" as stable JSON
            key = json.dumps(c, sort_keys=True, separators=(",", ":"))
            if key not in seen:
                seen.add(key)
                uniq.append(c)

        for body in uniq:
            status, data, _ = await self._req("POST", modules_connect_url(), json=body, headers=headers)
            LOG.debug("modules.connect try %s → %s %s", body, status, data if isinstance(data, dict) else "")
            if status in (200, 204):
                self._connect_variant = body
                return True
        return False

    async def modules_parameters_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Prime modules parameters.

        Args:
            modules: List of module codes.
            return_data: Whether to return response data or just success status.

        Returns:
            Tuple of (status, data) if return_data=True, otherwise boolean success.
        """
        payload = {"modules": modules}
        status, data, _ = await self._req("POST", modules_parameters_url(), json=payload)
        # log_json_payload(LOG, "prime.modules.parameters", summarize_top_level(data))
        return (status, data) if return_data else (status in (200, 204))

    async def modules_activity_quantity_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        """Prime modules activity quantity.

        Args:
            modules: List of module codes.
            return_data: Whether to return response data or just success status.

        Returns:
            Tuple of (status, data) if return_data=True, otherwise boolean success.
        """
        payload = {"modules": modules}
        status, data, _ = await self._req("POST", modules_activity_quantity_url(), json=payload)
        # log_json_payload(LOG, "prime.modules.activity.quantity", summarize_top_level(data))
        return (status, data) if return_data else (status in (200, 204))

    # -------- ASSETS --------

    async def fetch_text_one(self, path: str) -> tuple[int, str]:
        """Fetch text content from ONE_BASE.

        Args:
            path: The path to fetch from.

        Returns:
            Tuple of (status_code, text_content).
        """
        status, data, _ = await self._req("GET", f"{ONE_BASE}/{path}")
        return (status, data) if isinstance(data, str) else (status, "")

    async def fetch_json_one(self, path: str) -> tuple[int, dict[str, Any] | list[Any] | None]:
        """Fetch JSON content from ONE_BASE.

        Args:
            path: The path to fetch from.

        Returns:
            Tuple of (status_code, json_data).

        Note:
            Assets are JS, so JSON extraction should be done *catalog-side*, not here.
            This method is here only for symmetry; you may not use it.
        """
        st, txt = await self.fetch_text_one(path)
        # NOTE: assets are JS, so JSON extraction should be *catalog-side*, not here
        # This method is here only for symmetry; you may not use it.
        try:
            return st, json.loads(txt)
        except Exception:
            return st, None

    async def get_bytes(self, url: str) -> bytes:
        """Get raw bytes from URL with caching (ETag/Last-Modified).

        Args:
            url: The URL to fetch.

        Returns:
            The raw bytes of the response.

        Raises:
            ApiError: If the request fails.

        Note:
            This method uses an in-memory cache to store ETag and Last-Modified headers
            to optimize subsequent requests to the same URL.
        """
        sess = await self._ensure_session()
        headers = self._cache.headers_for(url)
        async with self._sem:
            LOG.debug("HTTP GET %s", url)
            try:
                r = await sess.get(url, headers=headers)
                if r.status_code == 304:
                    body = self._cache.get_body(url)
                    if body is None:
                        # 304 without previous body - fetch full content
                        r2 = await sess.get(url)
                        r2.raise_for_status()
                        body = r2.content
                        self._cache.update(url, r2.headers, body)
                        return body
                    # Body from cache is guaranteed to be bytes
                    return body
                r.raise_for_status()
                body = r.content
                self._cache.update(url, r.headers, body)
                return body
            except Exception as e:
                LOG.warning("HTTP error for %s: %s", url, e)
                raise
