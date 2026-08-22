"""Module alarm / activity list DTOs for BragerOne REST responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModuleAlarm(BaseModel):
    """One active or historical module alarm row.

    ``id`` is the SPA alarm *type* code (mapped via ``AlarmName`` → ``errors.*``),
    not a unique row primary key.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int
    devid: str = ""
    created_at: str | None = None
    finished_at: str | None = None


class ModuleActivity(BaseModel):
    """One module activity (parameter change / remote action) row."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int | None = None
    devid: str = ""
    module_id: int | None = None
    name: str = ""
    unit: int | None = None
    value: Any = None
    prev_value: Any = Field(default=None, validation_alias="prevValue")
    state: str = ""
    created_at: str | None = None
    user: str | None = None
    user_id: int | None = None
