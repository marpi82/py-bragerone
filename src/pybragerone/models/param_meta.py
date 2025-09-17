from __future__ import annotations

from dataclasses import dataclass, field

from .types import JSON, ParamId


@dataclass(slots=True, frozen=True)
class ParamMeta:
    """Parameter metadata as parsed from PARAM_*.js bundles."""

    items: dict[str, JSON] = field(default_factory=dict)

    def for_param(self, pid: ParamId) -> dict[str, JSON] | None:
        return self.items.get(f"parameters.PARAM_{pid}")
