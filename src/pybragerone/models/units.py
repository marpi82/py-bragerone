from __future__ import annotations

from dataclasses import dataclass, field

from .types import JSON, UnitId


@dataclass(slots=True, frozen=True)
class Units:
    """Units dictionary: unit id -> symbol or enum mapping."""

    items: dict[UnitId, JSON] = field(default_factory=dict)

    def symbol(self, uid: UnitId) -> str | None:
        u = self.items.get(uid)
        if isinstance(u, str):
            return u or None
        if isinstance(u, dict):
            sym = u.get("sym") or u.get("unit")
            return sym or None
        return None

    def enum_label(self, uid: UnitId, value: object) -> str | None:
        u = self.items.get(uid)
        if isinstance(u, dict) and "0" in u:
            return u.get(str(value))
        return None
