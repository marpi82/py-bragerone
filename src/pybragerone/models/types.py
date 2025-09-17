from __future__ import annotations

# Recursive JSON type without typing.Any (PEP 604 style).
type JSON = None | bool | int | float | str | list[JSON] | dict[str, JSON]

# Domain aliases
type ObjectId = int
type ModuleId = str
type ParamId = int
type UnitId = str
type Pool = str
type ParamKey = tuple[Pool, ParamId]
