from __future__ import annotations

from logging import Logger, getLogger

from ..api import Api
from ..ws import WsClient
from .types import JSON


class ApiModel:
    """Backend aggregator: REST (Api) + WebSocket (WsClient)."""

    def __init__(self, logger: Logger | None = None) -> None:
        self.log = logger or getLogger("pybragerone")
        self.api = Api()
        self.ws = WsClient(lambda: self.api.jwt, logger=self.log)

    # REST
    async def login(self, email: str, password: str) -> dict[str, JSON]:
        return await self.api.login(email, password)

    async def list_objects(self) -> list[dict[str, JSON]]:
        return await self.api.list_objects()

    async def list_modules(self, object_id: int) -> list[dict[str, JSON]]:
        return await self.api.list_modules(object_id)

    async def snapshot_parameters(self, devs: list[str]) -> dict[str, JSON]:
        return await self.api.snapshot_parameters(devs)

    async def activity_quantity(self, devs: list[str]) -> dict[str, JSON]:
        return await self.api.activity_quantity(devs)

    # WS
    async def ws_connect(self) -> str:
        return await self.ws.connect()

    async def ws_subscribe(self, devs: list[str]) -> None:
        if not devs:
            return
        await self.ws.subscribe(devs)

    async def ws_close(self) -> None:
        await self.ws.close()
