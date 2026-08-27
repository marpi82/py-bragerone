"""Module alarm / activity list DTOs for BragerOne REST responses."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue


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


class ModuleActivityUser(BaseModel):
    """Author of a module activity row when the API returns a user object."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int
    name: str


class ModuleActivity(BaseModel):
    """One module activity (parameter change / remote action) row.

    Live ``POST /v1/modules/activity`` rows typically include:

    - ``prevValue`` (camelCase): scalar previous value — mapped to ``prev_value``
    - ``prev_value`` (snake_case): nested param snapshot ``{P*: {n: {v, u}}}`` — kept in
      ``model_extra`` when both keys are present
    - ``user``: either a username string or :class:`ModuleActivityUser`
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int | None = None
    devid: str = ""
    module_id: int | None = None
    name: str = ""
    unit: int | None = None
    value: JsonValue = None
    prev_value: JsonValue = Field(default=None, validation_alias="prevValue")
    state: str = ""
    created_at: str | None = None
    user: ModuleActivityUser | str | None = None
    user_id: int | None = None
