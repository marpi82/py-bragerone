import ast
import contextlib
import json
import re

from .types import JSON

# --- helper regexes for JSON-ish normalization ---
_SPECIALS_RE = re.compile(r"\b(?:undefined|NaN|Infinity|-Infinity)\b", re.I)
_NOT_ZERO_RE = re.compile(r"!\s*0")
_NOT_ONE_RE = re.compile(r"!\s*1")
_UNQUOTED_KEY_RE = re.compile(r"([{\s,])([A-Za-z_$][\w$]*)\s*:")
_UNQUOTED_NUM_KEY_RE = re.compile(
    r"([{\s,])([+-]?(?:\d+(?:\.\d+)?(?:[eE][+-]?\d+)?))\s*:",
)

# dodatkowo: klucze heksadecymalne typu 0x1a (JS je dopuszcza)
_UNQUOTED_HEX_KEY_RE = re.compile(
    r"([{\s,])(0x[0-9a-fA-F]+)\s*:",
)
_TRAILING_COMMA_OBJ_RE = re.compile(r",\s*}")
_TRAILING_COMMA_ARR_RE = re.compile(r",\s*]")

# quick finds
_EXPORT_DEFAULT_RE = re.compile(r"export\s+default\b")
_EXPORT_ALIAS_RE = re.compile(r"export\s*{\s*([A-Za-z_$][\w$]*)\s+as\s+default\s*}")
_VAR_DEF_RE_TMPL = r"(?:const|let|var)\s+{name}\s*=\s*"  # followed by object literal

# --- helper (PARAM_*.js) ------------------------------------------------------

_PARAM_OBJECT_RE = re.compile(
    r"""const\s+[A-Za-z_$][\w$]*\s*=\s*(\{.*?\})\s*;\s*export\s*\{\s*[A-Za-z_$][\w$]*\s+as\s+default\s*\}\s*;?""",
    re.S,
)

# [u.LOCKED]: ...  =>  "LOCKED": ...
_BRACKETED_KEY_RE = re.compile(
    r"""\[\s*[A-Za-z_$][\w$]*\s*\.\s*([A-Za-z_$][\w$]*)\s*\]\s*:""", re.M
)

# value side:  : e.TEXT_FIELD  =>  : "TEXT_FIELD"
_ENUM_VALUE_RE = re.compile(r""":\s*[A-Za-z_$][\w$]*\s*\.\s*([A-Za-z_$][\w$]*)\b""")

# key side (niebrakujący cudzysłów):  icon:r.INFO  =>  "icon":"INFO"
_ENUM_AFTER_KEY_RE = re.compile(
    r"""(?P<prefix>\b[A-Za-z_$][\w$]*\s*:\s*)[A-Za-z_$][\w$]*\s*\.\s*([A-Za-z_$][\w$]*)\b"""
)

# single quoted string -> double quoted, z zachowaniem escapingu
_SINGLE_QUOTED_RE = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'")


# -------------- low-level JS scanning helpers --------------


def _strip_comments(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = re.sub(r"//.*?$", "", s, flags=re.M)
    return s


def _find_braced_object(s: str, start_pos: int) -> tuple[int, int] | None:
    """
    Given position of '{' in s, return (obj_start, obj_end_inclusive) that covers balanced {...}.
    Handles strings and escapes.
    """
    n = len(s)
    i = start_pos
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
    """
    Extract object literal that is exported as default.
    Supports:
      - export default { ... };
      - const X = { ... }; export { X as default };
      - let/var also supported.
    """
    # 1) export default { ... }
    m = _EXPORT_DEFAULT_RE.search(js)
    if m:
        # find first '{' after 'export default'
        brace_pos = js.find("{", m.end())
        if brace_pos != -1:
            rng = _find_braced_object(js, brace_pos)
            if rng:
                return js[rng[0] : rng[1] + 1]

    # 2) export { X as default }; then find var/let/const X = { ... }
    ma = _EXPORT_ALIAS_RE.search(js)
    if ma:
        name = ma.group(1)
        var_def_re = re.compile(_VAR_DEF_RE_TMPL.format(name=re.escape(name)))
        md = var_def_re.search(js)
        if md:
            brace_pos = js.find("{", md.end())
            if brace_pos != -1:
                rng = _find_braced_object(js, brace_pos)
                if rng:
                    return js[rng[0] : rng[1] + 1]

    raise RuntimeError("export default object not found (neither direct nor alias form)")


# -------------- JSON-ish normalization (conservative) --------------


def _to_jsonish(s: str) -> str:
    # 1) comments
    s = _strip_comments(s)

    # 1a) 'void 0' i 'void(0)' -> null (robust)
    s = re.sub(r"(?<![A-Za-z0-9_$])void\s*0(?![A-Za-z0-9_$])", "null", s)
    s = re.sub(r"(?<![A-Za-z0-9_$])void\s*\(\s*0\s*\)(?![A-Za-z0-9_$])", "null", s)

    # 2) !0 / !1
    s = _NOT_ZERO_RE.sub("true", s)
    s = _NOT_ONE_RE.sub("false", s)

    # 3) single-quoted -> double-quoted (bez ruszania już podwójnych)
    def _single_to_double(m: re.Match) -> str:
        inner = m.group(1)
        inner = inner.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{inner}"'

    s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", _single_to_double, s)

    # 4) keys quoted
    s = _UNQUOTED_KEY_RE.sub(r'\1"\2":', s)
    s = _UNQUOTED_NUM_KEY_RE.sub(r'\1"\2":', s)
    s = _UNQUOTED_HEX_KEY_RE.sub(r'\1"\2":', s)

    # 5) trailing commas
    s = _TRAILING_COMMA_OBJ_RE.sub("}", s)
    s = _TRAILING_COMMA_ARR_RE.sub("]", s)

    # 6) specials -> null
    s = _SPECIALS_RE.sub("null", s)

    return s


# -------------- public parsers --------------


def parse_units_js(js_text: str) -> dict[str, JSON]:
    """
    Parse contents of a units-*.js file into a Python dict.
    Supports both 'export default {..}' and 'const a={..};export{a as default}'.
    """
    obj_literal = _extract_default_object_literal(js_text)
    obj_json = _to_jsonish(obj_literal)
    try:
        return json.loads(obj_json)
    except json.JSONDecodeError as e:
        dump_path = "/tmp/brager_units_jsonish.txt"
        try:
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(obj_json)
        except Exception:
            dump_path = "(dump failed)"
        prefix = obj_json[:1000]
        raise RuntimeError(
            f"units: JSON decode failed: {e}; dump={dump_path}; prefix={prefix!r}"
        ) from e


def parse_parameters_js(js_text: str) -> dict[str, str]:
    """
    Parse parameters-*.js into {"PARAM_6": "label", ...}.
    These files never contain `export default {}`, only alias mappings:
        PARAM_6 : Te
        ...
        Te = "Maksymalna wydajność dmuchawy"
    """
    aliases: dict[str, str] = {}
    labels: dict[str, str] = {}

    # 1) PARAM_<id> : Alias   (tolerant: comma, }, ;, newline, or EOF)
    alias_re = re.compile(
        r"\b(PARAM_\d+)\b\s*:\s*([A-Za-z_$][\w$]*)\s*(?=,|}|;|[\r\n]|$)",
        re.M,
    )
    for m in alias_re.finditer(js_text):
        aliases[m.group(1)] = m.group(2)

    # 2) Alias = "..." | '...'  (allow const/let/var and optional semicolon)
    sym_def_re = re.compile(
        r"\b(?:const|let|var\s+)?([A-Za-z_$][\w$]*)\s*=\s*"
        r'("([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\')\s*;?',
        re.M,
    )
    for m in sym_def_re.finditer(js_text):
        sym = m.group(1)
        s_quoted = m.group(2)  # zawiera cudzysłowy
        try:
            # Najbezpieczniej: zamień JS-owy literał na Pythona
            inner = ast.literal_eval(s_quoted)
        except Exception:
            # awaryjnie, gdyby coś było bardzo egzotyczne
            inner = s_quoted[1:-1]
        labels[sym] = inner

    # 3) Build final dict
    out: dict[str, str] = {}
    for param_key, sym in aliases.items():
        if sym in labels:
            out[param_key] = labels[sym]

    # Don't blow up if empty — allow units binding to proceed
    return out


def parse_labels_js(js_text: str) -> dict[str, JSON]:
    """
    Parse one PARAM_*.js file into a dict, prefer full JSON if possible.
    If JSON parse fails (complex conditional shapes), fall back to a
    minimal extractor (name + optional id) so bootstrap does not break.
    """
    m = _PARAM_OBJECT_RE.search(js_text)
    if not m:
        return {}

    obj_literal = m.group(1)

    # --- pre-normalizations on raw JS object literal ---
    # [u.LOCKED] : ...  ->  "LOCKED" :
    obj_literal = _BRACKETED_KEY_RE.sub(r'"\1":', obj_literal)
    # icon:r.INFO -> "icon":"INFO"  (generic enum-key.rightSide)
    obj_literal = _ENUM_AFTER_KEY_RE.sub(
        lambda mm: f'{mm.group("prefix")}"{mm.group(2)}"', obj_literal
    )
    # value side like  : e.TEXT_FIELD  ->  : "TEXT_FIELD"
    obj_literal = _ENUM_VALUE_RE.sub(r': "\1"', obj_literal)
    # convert: e  ->  convert: "e"
    obj_literal = re.sub(
        r"(?P<prefix>\bconvert\s*:\s*)([A-Za-z_$][\w$]*)\b", r'\g<prefix>"\2"', obj_literal
    )
    # void 0 / void(0) -> null (jeśli jeszcze nie było zrobione na poziomie _to_jsonish)
    obj_literal = re.sub(r"(?<![A-Za-z0-9_$])void\s*0(?![A-Za-z0-9_$])", "null", obj_literal)
    obj_literal = re.sub(
        r"(?<![A-Za-z0-9_$])void\s*\(\s*0\s*\)(?![A-Za-z0-9_$])", "null", obj_literal
    )

    # -> JSON-ish
    obj_jsonish = _to_jsonish(obj_literal)

    # Spróbuj pełnego parsowania
    try:
        data = json.loads(obj_jsonish)
        name = data.get("name")
        if not isinstance(name, str):
            return {}

        meta: dict[str, JSON] = {}
        for k in (
            "id",
            "name",
            "unit",
            "command",
            "minValue",
            "maxValue",
            "value",
            "status",
            "componentType",
            "icon",
            "any",
            "if",
            "then",
            "else",
        ):
            if k in data:
                meta[k] = data[k]
        return {name: meta}

    except Exception:
        # --- fallback: minimal extraction, żeby nie blokować bootstrapa ---
        # Wyciągnij "name":"parameters.PARAM_..." oraz numeric id jeśli jest.
        name_m = re.search(r'"name"\s*:\s*"([^"]+)"', obj_jsonish)
        if not name_m:
            # jeśli się nie da, zrzut diagnostyczny i pusta odpowiedź
            try:
                with open("/tmp/brager_param_fallback.txt", "w", encoding="utf-8") as f:
                    f.write(obj_jsonish)
            except Exception:
                pass
            return {}

        name = name_m.group(1)
        id_m = re.search(r'"id"\s*:\s*(\d+)', obj_jsonish)
        meta = {"name": name}
        if id_m:
            with contextlib.suppress(Exception):
                meta["id"] = int(id_m.group(1))

        # zostawiamy hook na przyszłość: jeżeli w prosty sposób da się wyłuskać `command`
        # jako string bezpiecznie - spróbuj
        cmd_m = re.search(r'"command"\s*:\s*"([^"]+)"', obj_jsonish)
        if cmd_m:
            meta["command"] = cmd_m.group(1)

        return {name: meta}
