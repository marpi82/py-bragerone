"""Protocols for the HTTP and Socket.IO clients used by BragerOneGateway."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from ..models.api.modules import Module


class ApiClient(Protocol):
    """Protocol for the HTTP client used by the gateway.

    This makes the gateway easy to test by allowing a lightweight fake.
    """

    @property
    def access_token(self) -> str:
        raise NotImplementedError

    async def modules_connect(
        self,
        wsid_ns: str,
        modules: list[str],
        group_id: int | None = None,
        engine_sid: str | None = None,
    ) -> bool:
        raise NotImplementedError

    async def modules_parameters_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        raise NotImplementedError

    async def modules_activity_quantity_prime(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        raise NotImplementedError

    async def modules_alarms_quantity(self, modules: list[str], *, return_data: bool = False) -> tuple[int, Any] | bool:
        raise NotImplementedError

    async def get_modules(self, object_id: int) -> list[Module]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class RealtimeManagerClient(Protocol):
    """Protocol for the WS client used by the gateway."""

    @property
    def group_id(self) -> int | None:
        raise NotImplementedError

    @group_id.setter
    def group_id(self, group_id: int | None) -> None:
        raise NotImplementedError

    def on_event(self, handler: Any) -> None:
        raise NotImplementedError

    async def connect(self) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError

    def add_on_connected(self, cb: Callable[[], Awaitable[None] | None]) -> None:
        raise NotImplementedError

    def add_on_disconnected(self, cb: Callable[[], Awaitable[None] | None]) -> None:
        raise NotImplementedError

    def sid(self) -> str | None:
        raise NotImplementedError

    def engine_sid(self) -> str | None:
        raise NotImplementedError

    async def subscribe(self, modules: list[str]) -> None:
        raise NotImplementedError

    async def force_reconnect(self) -> None:
        raise NotImplementedError

    async def hard_reset(self) -> None:
        raise NotImplementedError
