from __future__ import annotations

import re

from ..models.labels import Labels
from ..models.param_meta import ParamMeta
from ..models.types import JSON
from ..models.units import Units


def parse_labels(d: dict[str, str]) -> Labels:
    """Create Labels model from raw dict."""
    return Labels(d)


def parse_units(d: dict[str, JSON]) -> Units:
    """Create Units model from raw dict."""
    return Units(d)


def parse_param_meta(d: dict[str, JSON]) -> ParamMeta:
    """Create ParamMeta model from raw dict."""
    return ParamMeta(d)


# --- robust object extraction ---

_VAR_DEF_RE_TMPL = r"\b(?:const|let|var)\s+{name}\s*=\s*"
_EXPORT_DEFAULT_RE = re.compile(r"export\s+default\b")
_EXPORT_ALIAS_RE = re.compile(r"export\s*{\s*([A-Za-z_$][\w$]*)\s+as\s+default\s*}")
_EXPORT_DEFAULT_NAME_RE = re.compile(r"export\s+default\s+([A-Za-z_$][\w$]*)\s*;?")


def _find_braced_object(s: str, brace_pos: int) -> tuple[int, int] | None:
    """
    Given position of '{' in s, return (obj_start, obj_end_inclusive) that covers balanced {...}.
    Handles strings and escapes.
    """
    n = len(s)
    i = brace_pos
    if i < 0 or i >= n or s[i] != "{":
        return None
    depth = 0
    in_str = False
    q = ""
    esc = False
    obj_start = i
    while i < n:
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == q:
                in_str = False
        else:
            if ch == '"' or ch == "'":
                in_str = True
                q = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return (obj_start, i)
        i += 1
    return None


def _extract_default_object_literal(js: str) -> str:
    """Supports:
    - export default { ... };
    - const X = { ... }; export { X as default };
    - export default X;  (a X zdefiniowane wyżej)
    """
    # 1) bezpośrednio: export default { ... }
    m = _EXPORT_DEFAULT_RE.search(js)
    if m:
        brace_pos = js.find("{", m.end())
        if brace_pos != -1:
            rng = _find_braced_object(js, brace_pos)
            if rng:
                return js[rng[0] : rng[1] + 1]

    # 2) alias: export { X as default }
    ma = _EXPORT_ALIAS_RE.search(js)
    if ma:
        name = ma.group(1)
        var_def_re = re.compile(_VAR_DEF_RE_TMPL.format(name=re.escape(name)), re.VERBOSE)
        md = var_def_re.search(js)
        if md:
            brace_pos = js.find("{", md.end())
            if brace_pos != -1:
                rng = _find_braced_object(js, brace_pos)
                if rng:
                    return js[rng[0] : rng[1] + 1]

    # 3) export default X;
    mdn = _EXPORT_DEFAULT_NAME_RE.search(js)
    if mdn:
        name = mdn.group(1)
        var_def_re = re.compile(_VAR_DEF_RE_TMPL.format(name=re.escape(name)), re.VERBOSE)
        md = var_def_re.search(js)
        if md:
            brace_pos = js.find("{", md.end())
            if brace_pos != -1:
                rng = _find_braced_object(js, brace_pos)
                if rng:
                    return js[rng[0] : rng[1] + 1]

    # fallback: first '{' to last '}'
    start = js.find("{")
    end = js.rfind("}")
    if start != -1 and end != -1 and end > start:
        return js[start : end + 1]
    raise RuntimeError("export default object not found (neither direct nor alias form)")


def parse_param_meta_chunk(js_or_dict: dict[str, JSON] | str) -> dict[str, JSON]:
    # ... (jak w poprzedniej wersji; próba json, zamiana cudzysłowów, do-cytowanie kluczy) ...
    ...
