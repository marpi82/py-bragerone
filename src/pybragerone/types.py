from __future__ import annotations

# Rekurencyjny typ JSON (PEP 604, bez 'typing')
type JSON = None | bool | int | float | str | list[JSON] | dict[str, JSON]
