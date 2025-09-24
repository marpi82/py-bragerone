"""Module src/pybragerone/core/client.py."""
from __future__ import annotations

import json
import logging
from typing import Any
import aiohttp

from .consts import API_BASE, ONE_BASE

LOG = logging.getLogger("pybragerone.api")

class ApiError(RuntimeError):
    """ApiError class.

    Attributes:
    TODO.
    """
    def __init__(self, status: int, data: Any):
        """Init  .
    
        Args:
        status: TODO.
        data: TODO.

        Returns:
        TODO.
        """
        super().__init__(f"HTTP {status}: {data}")
        self.status = status
        self.data = data

class BragerOneApiClient:
    """Minimalny async REST klient. Nie trzyma żadnego storage.
    """
    _connect_variant: dict | None = None

    def __init__(self, base_api: str = API_BASE, base_one: str = ONE_BASE,  session: aiohttp.ClientSession | None = None, access_token: str | None = None, timeout: int = 30):
        """Init  .
    
        Args:
        access_token: TODO.
        timeout: TODO.

        Returns:
        TODO.
        """
        self._token: str | None = access_token
        self._timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession = session if session else aiohttp.ClientSession(timeout=self._timeout)

        self.base_api: str = base_api.rstrip("/")
        self.base_one: str = base_one.rstrip("/")

    @property
    def token(self) -> str | None:
        """Token.
    
        Returns:
        TODO.
        """
        return self._token

    @property
    def session(self) -> aiohttp.ClientSession:
        """Session.
    
        Returns:
        TODO.
        """
        if self._session is None or self._session.closed:
            raise RuntimeError("no session (did you forget to use 'async with'?)")
        return self._session

    async def __aenter__(self):
        """Aenter  .
    
        Returns:
        TODO.
        """
        await self.ensure_session()
        return self

    async def __aexit__(self, *exc):
        """Aexit  .
    
        Args:
        exc: TODO.

        Returns:
        TODO.
        """
        await self.close()

    async def ensure_session(self):
        """Ensure session.
    
        Returns:
        TODO.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)

    async def close(self):
        """Close.
    
        Returns:
        TODO.
        """
        if self._session and not self._session.closed:
            await self._session.close()

    def _base_headers(self) -> dict[str, str]:
        """Base headers.
    
        Returns:
        TODO.
        """
        h = {
            "Accept": "application/json",
            "Origin": self.base_one,
            "Referer": self.base_one + '/'
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def _req(self, method: str, path: str, **kw) -> tuple[int, Any, dict[str, str]]:
        """Req.
    
        Args:
        method: TODO.
        path: TODO.
        kw: TODO.

        Returns:
        TODO.
        """
        await self.ensure_session()
        url = f"{self.base_one}{path}" if path.startswith("/") else f"{self.base_one}/{path}"
        headers = kw.pop("headers", {})
        headers = {**self._base_headers(), **headers}
        async with self._session.request(method, url, headers=headers, **kw) as r:
            ctype = r.headers.get("Content-Type", "")
            try:
                data = await r.json() if "application/json" in ctype or ctype == "" else await r.text()
            except Exception:
                data = await r.text()
            return r.status, data, dict(r.headers)

    # -------- AUTH --------
    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Login.
    
        Args:
        email: TODO.
        password: TODO.

        Returns:
        TODO.
        """
        status, data, _ = await self._req("POST", "/auth/user", json={"email": email, "password": password})
        if status != 200:
            raise ApiError(status, data)
        # utrwal token
        token = data.get("accessToken")
        if not token:
            raise ApiError(500, {"error": "missing accessToken"})
        self._token = token
        return data

    async def revoke(self) -> dict[str, Any]:
        """Revoke.
    
        Returns:
        TODO.
        """
        status, data, _ = await self._req("POST", "/auth/revoke")
        if status not in (200, 204):
            raise ApiError(status, data)
        return data if isinstance(data, dict) else {"status": "SUCCESS"}

    # -------- USER --------
    async def get_user(self) -> dict[str, Any]:
        """Get user.
    
        Returns:
        TODO.
        """
        status, data, _ = await self._req("GET", "/user")
        if status != 200:
            raise ApiError(status, data)
        return data

    async def get_user_permissions(self) -> list[str]:
        """Get user permissions.
    
        Returns:
        TODO.
        """
        status, data, _ = await self._req("GET", "/user/permissions")
        if status != 200:
            raise ApiError(status, data)
        return data if isinstance(data, list) else []

    # -------- OBJECTS --------
    async def list_objects(self) -> dict[str, Any]:
        """List objects.
    
        Returns:
        TODO.
        """
        status, data, _ = await self._req("GET", "/objects")
        if status != 200:
            raise ApiError(status, data)
        return data if isinstance(data, dict) else {"objects": []}

    async def get_object(self, object_id: int) -> dict[str, Any]:
        """Get object.
    
        Args:
        object_id: TODO.

        Returns:
        TODO.
        """
        status, data, _ = await self._req("GET", f"/objects/{object_id}")
        if status != 200:
            raise ApiError(status, data)
        return data

    async def get_object_permissions(self, object_id: int) -> list[str]:
        """Get object permissions.
    
        Args:
        object_id: TODO.

        Returns:
        TODO.
        """
        status, data, _ = await self._req("GET", f"/objects/{object_id}/permissions")
        if status != 200:
            raise ApiError(status, data)
        return data if isinstance(data, list) else []

    # -------- MODULES --------
    async def list_modules(self, group_id: int, page: int = 1, limit: int = 999) -> list[dict]:
        """List modules.
    
        Args:
        group_id: TODO.
        page: TODO.
        limit: TODO.

        Returns:
        TODO.
        """
        status, data, _ = await self._req("GET", f"/modules?page={page}&limit={limit}&group_id={group_id}")
        if status != 200:
            raise ApiError(status, data)

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                return data["data"]

        return []

    async def get_module_card(self, code: str) -> dict[str, Any]:
        """Get module card.
    
        Args:
        code: TODO.

        Returns:
        TODO.
        """
        status, data, _ = await self._req("GET", f"/modules/{code}/card")
        if status != 200:
            raise ApiError(status, data)
        return data

    async def modules_connect(
        self,
        wsid_ns: str,
        modules: list[str],
        group_id: int | None = None,
        engine_sid: str | None = None,
    ) -> bool:
        """Modules connect.
    
        Args:
        wsid_ns: TODO.
        modules: TODO.
        group_id: TODO.
        engine_sid: TODO.

        Returns:
        TODO.
        """
        if not modules:
            return True
        modules = sorted(set(modules))
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }

        def bodies(pref_sid: str):
            """Bodies.
    
            Args:
            pref_sid: TODO.

            Returns:
            TODO.
            """
            arr = [
                {"wsid": pref_sid, "modules": modules},
                {"sid":  pref_sid, "modules": modules},
            ]
            if group_id is not None:
                arr.append({"wsid": pref_sid, "group_id": group_id, "modules": modules})
            return arr

        candidates: list[dict] = []
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
        uniq: list[dict] = []
        for c in candidates:
            # hashuj "kształt" payloadu jako stabilny JSON
            key = json.dumps(c, sort_keys=True, separators=(",", ":"))
            if key not in seen:
                seen.add(key)
                uniq.append(c)

        for body in uniq:
            status, data, _ = await self._req("POST", "/modules/connect", json=body, headers=headers)
            LOG.debug("modules.connect try %s → %s %s", body, status, data if isinstance(data, dict) else "")
            if status in (200, 204):
                self._connect_variant = body
                return True
        return False

    async def modules_parameters_prime(self, modules: list[str], *, return_data: bool=False):
        """Modules parameters prime.
    
        Args:
        modules: TODO.
        return_data: TODO.

        Returns:
        TODO.
        """
        payload = {"modules": modules}
        status, data, _ = await self._req("POST", "/modules/parameters", json=payload)
        #log_json_payload(LOG, "prime.modules.parameters", summarize_top_level(data))
        return (status, data) if return_data else (status in (200, 204))


    async def modules_activity_quantity_prime(self, modules: list[str], *, return_data: bool=False):
        """Modules activity quantity prime.
    
        Args:
        modules: TODO.
        return_data: TODO.

        Returns:
        TODO.
        """
        payload = {"modules": modules}
        status, data, _ = await self._req("POST", "/modules/activity/quantity", json=payload)
        #log_json_payload(LOG, "prime.modules.activity.quantity", summarize_top_level(data))
        return (status, data) if return_data else (status in (200, 204))

    # -------- ASSETS --------

    async def fetch_text_one(self, path_or_url: str) -> tuple[int, str]:
        """GET z domeny one.* (assets), z Twoimi nagłówkami i logowaniem."""
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_one}{path_or_url}"
        async with self.session.get(url, headers=self._base_headers()) as r:
            txt = await r.text()
            return r.status, txt

    async def fetch_json_one(self, path_or_url: str) -> tuple[int, dict | list | None]:
        st, txt = await self.fetch_text_one(path_or_url)
        # UWAGA: assets są JS, więc JSON wyciągamy *po stronie katalogu*, nie tutaj
        # Ta metoda jest tu tylko dla symetrii; możesz jej nie używać.
        try:
            import json
            return st, json.loads(txt)
        except Exception:
            return st, None

