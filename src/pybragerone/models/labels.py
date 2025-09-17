from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class Labels:
    """Dictionary of parameter labels: "PARAM_6" -> "Human label"."""

    items: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        return self.items.get(key)

    def for_param(self, pid: int) -> str | None:
        return self.items.get(f"PARAM_{pid}")
