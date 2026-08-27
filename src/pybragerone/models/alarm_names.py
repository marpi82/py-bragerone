"""Parse SPA ``AlarmName`` enum maps and resolve ``errors.*`` alarm labels."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Bidirectional chunks emit either ``38:"ERROR_…"`` or ``ERROR_…:38`` (quotes optional).
_ALARM_NAME_PAIR_RE = re.compile(
    r"""(?x)
    (?:
        ['"]?(?P<name_a>ERROR_[A-Z0-9_]+)['"]?\s*:\s*(?P<code_a>\d+)
      | (?P<code_b>\d+)\s*:\s*['"]?(?P<name_b>ERROR_[A-Z0-9_]+)['"]?
    )
    """
)
# Obfuscated SPA enum chunks: ``obj['ERROR_FOO']=0x26`` (hex or decimal).
_ALARM_NAME_BRACKET_ASSIGN_RE = re.compile(
    r"""\[\s*['"](?P<name>ERROR_[A-Z0-9_]+)['"]\s*\]\s*=\s*(?P<code>0[xX][0-9a-fA-F]+|\d+)"""
)


def parse_alarm_name_enum(source: str | bytes | bytearray) -> dict[int, str]:
    """Extract ``{alarm_type_id: ERROR_*}`` from an Alarms chunk / enum blob.

    Args:
        source: JavaScript (or JSON-like) source that contains ``AlarmName`` pairs.

    Returns:
        Mapping of numeric alarm type id → ``ERROR_*`` symbol. Pair and bracket
        matches are applied in source order so a later declaration wins on
        duplicate ids regardless of syntax.
    """
    text = source.decode("utf-8", errors="replace") if isinstance(source, (bytes, bytearray)) else source
    events: list[tuple[int, str, re.Match[str]]] = []
    for match in _ALARM_NAME_PAIR_RE.finditer(text):
        events.append((match.start(), "pair", match))
    for match in _ALARM_NAME_BRACKET_ASSIGN_RE.finditer(text):
        events.append((match.start(), "bracket", match))
    events.sort(key=lambda item: item[0])

    out: dict[int, str] = {}
    for _start, kind, match in events:
        if kind == "pair":
            # Alternation always binds either name_a/code_a or name_b/code_b.
            name_a = match.group("name_a")
            if name_a is not None:
                out[int(match.group("code_a"))] = name_a
            else:
                out[int(match.group("code_b"))] = match.group("name_b")
        else:
            # Named groups are always present when the bracket pattern matches.
            # Prefer explicit bases: ``int(..., 0)`` rejects zero-padded decimals
            # such as ``=08`` that appear in public SPA bundles.
            code = match.group("code")
            base = 16 if code[:2].lower() == "0x" else 10
            out[int(code, base)] = match.group("name")
    return out


def resolve_alarm_error_key(alarm_id: int, alarm_names: Mapping[int, str]) -> str | None:
    """Return the ``ERROR_*`` key for *alarm_id*, or ``None`` if unknown."""
    name = alarm_names.get(alarm_id)
    return name if isinstance(name, str) and name.startswith("ERROR_") else None


def resolve_alarm_label(
    alarm_id: int,
    *,
    alarm_names: Mapping[int, str],
    errors_i18n: Mapping[str, Any],
) -> str | None:
    """Resolve a localized alarm title via ``errors.<ERROR_*>``.

    Args:
        alarm_id: SPA alarm type code from the REST list.
        alarm_names: Output of :func:`parse_alarm_name_enum`.
        errors_i18n: Namespace from ``LiveAssetsCatalog.get_i18n(lang, "errors")``.

    Returns:
        Localized label, or ``None`` when the key/id cannot be resolved (callers
        must not invent a hardcoded fallback language string).
    """
    key = resolve_alarm_error_key(alarm_id, alarm_names)
    if key is None:
        return None
    value = errors_i18n.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
