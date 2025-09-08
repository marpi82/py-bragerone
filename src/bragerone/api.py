from __future__ import annotations
import json
import aiohttp
from typing import Any, Optional

from .const import API_BASE, AUTH_URL, ORIGIN, REFERER

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=25)

class Api:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.http = session
        self._own = False
        self.jwt: Optional[str] = None

    async def ensure(self):
        if self.http is None:
            self.http = aiohttp.ClientSession()
            self._own = True

    async def close(self):
        if self._own and self.http:
            await self.http.close()

    async def _req(self, method: str, url: str, *, headers: dict | None = None, **kw) -> Any:
        await self.ensure()
        headers = headers or {}
        headers.setdefault("Accept", "application/json, text/plain, */*")
        headers.setdefault("Origin", ORIGIN)
        headers.setdefault("Referer", REFERER)
        if self.jwt:
            headers["Authorization"] = f"Bearer {self.jwt}"
        kw.setdefault("timeout", DEFAULT_TIMEOUT)
        async with self.http.request(method, url, headers=headers, **kw) as r:
            txt = await r.text()
            ct = r.headers.get("content-type", "")
            if r.status >= 400:
                raise RuntimeError(f"{method} {url} -> {r.status}: {txt[:400]}")
            if "application/json" in ct or txt.startswith(("{","[")):
                try:
                    return json.loads(txt)
                except json.JSONDecodeError:
                    return txt
            return txt

    # ---------- high-level ----------
    async def login(self, email: str, password: str) -> dict:
        data = await self._req("POST", AUTH_URL, json={"email": email, "password": password})
        tok = data.get("accessToken") if isinstance(data, dict) else None
        if not tok:
            raise RuntimeError("Brak accessToken w odpowiedzi logowania")
        self.jwt = tok
        return data

    async def list_objects(self) -> list[dict]:
        objs: list[dict] = []
        try:
            d = await self._req("GET", f"{API_BASE}/objects")
            items = d.get("data") or d.get("items") or d.get("objects") or d
            if isinstance(items, list):
                for it in items:
                    oid = it.get("id") or it.get("group_id") or it.get("object_id")
                    name = it.get("name") or it.get("title") or it.get("label") or f"Object {oid}"
                    if oid is not None:
                        objs.append({"id": int(oid), "name": name})
        except Exception:
            pass
        if not objs:
            try:
                u = await self._req("GET", f"{API_BASE}/user")
                cand = u.get("objects") or u.get("groups") or u.get("data", {}).get("groups") or []
                for it in cand:
                    oid = it.get("id") or it.get("group_id")
                    name = it.get("name") or it.get("title") or it.get("label") or f"Object {oid}"
                    if oid is not None:
                        objs.append({"id": int(oid), "name": name})
            except Exception:
                pass
        return list({o["id"]: o for o in objs}.values())

    async def list_modules(self, object_id: int) -> list[dict]:
        d = await self._req("GET", f"{API_BASE}/modules?page=1&limit=999&group_id={object_id}")
        items = d.get("data") or d.get("items") or d.get("modules") or d
        return items if isinstance(items, list) else []

    async def snapshot_parameters(self, devs: list[str]) -> dict:
        res = await self._req("POST", f"{API_BASE}/modules/parameters", json={"modules": devs})
        return res if isinstance(res, dict) else {}

    async def activity_quantity(self, devs: list[str]) -> dict:
        res = await self._req("POST", f"{API_BASE}/modules/activity/quantity", json={"modules": devs})
        return res if isinstance(res, dict) else {}

    async def modules_connect(self, wsid: str, devs: list[str], object_id: int | None = None) -> bool:
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json;charset=UTF-8",
        }
        payloads = [
            {"wsid": wsid, "modules": devs},
            {"sid": wsid, "modules": devs},
            {"wsid": wsid, "group_id": object_id, "modules": devs} if object_id else None,
        ]
        for pl in payloads:
            if not pl: continue
            try:
                res = await self._req("POST", f"{API_BASE}/modules/connect", json=pl, headers=headers)
                if isinstance(res, dict):
                    return True
            except Exception:
                continue
        return False

