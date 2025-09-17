"""Utility helpers for pybragerone."""

from __future__ import annotations


def chunked(seq: list[object], size: int) -> list[list[object]]:
    """Return a list of chunks of `seq` with a given `size` (last chunk may be shorter)."""
    if size <= 0:
        raise ValueError("size must be > 0")
    return [seq[i : i + size] for i in range(0, len(seq), size)]
