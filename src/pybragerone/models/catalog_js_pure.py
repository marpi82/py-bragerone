"""Pure-Python JavaScript value extractor for catalog leaves (i18n / units / language).

This is the production parser for shapes that previously went through tree-sitter:
object/array/string/number literals, ``const`` bindings, and ``export default``.
Arrow/factory evaluation is deferred to later slices — arrows are kept as source text.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from .menu import js_public_member_name

LOG = logging.getLogger(__name__)

_JS_SIMPLE_ESCAPES = {
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
    "0": "\0",
}
_JS_LINE_CONTINUATIONS = frozenset("\n\r\u2028\u2029")
_IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")
_EXPORT_AS_DEFAULT_RE = re.compile(r"export\s*\{[^}]*?([A-Za-z0-9_$]+)\s+as\s+default")
_EXPORT_DEFAULT_RE = re.compile(r"export\s+default\b")
_TRAILING_PUBLIC_SUBSCRIPT_RE = re.compile(r"""\[['\"]([A-Z][A-Z0-9_]*)['\"]\]\s*$""")


def collapse_public_token(expr: Any) -> Any:
    """Collapse leftover member/IIFE text to a public TOKEN when possible."""
    if not isinstance(expr, str):
        return expr
    public = js_public_member_name(expr)
    if public is not None:
        return public
    match = _TRAILING_PUBLIC_SUBSCRIPT_RE.search(expr)
    if match is not None:
        return match.group(1)
    return expr


def _read_hex(text: str, start: int, length: int) -> int | None:
    """Read exactly *length* hex digits at *start*, or return None."""
    chunk = text[start : start + length]
    if len(chunk) != length:
        return None
    try:
        return int(chunk, 16)
    except ValueError:
        return None


def _safe_chr(code: int) -> str:
    """Convert a code point to a character, replacing lone surrogates."""
    if 0xD800 <= code <= 0xDFFF or code > 0x10FFFF:
        return "\ufffd"
    return chr(code)


def decode_js_escapes(text: str) -> str:
    """Decode JavaScript escape sequences in a string literal body."""
    if "\\" not in text:
        return text

    out: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        if ch != "\\" or i + 1 >= n:
            out.append(ch)
            i += 1
            continue

        esc = text[i + 1]
        i += 2

        if esc in _JS_LINE_CONTINUATIONS:
            if esc == "\r" and i < n and text[i] == "\n":
                i += 1
            continue

        if esc == "x":
            code = _read_hex(text, i, 2)
            if code is not None:
                out.append(_safe_chr(code))
                i += 2
                continue
            out.append(esc)
            continue

        if esc == "u":
            if i < n and text[i] == "{":
                close = text.find("}", i + 1)
                code = _read_hex(text, i + 1, close - i - 1) if close > i + 1 else None
                if code is not None:
                    out.append(_safe_chr(code))
                    i = close + 1
                    continue
                out.append(esc)
                continue

            code = _read_hex(text, i, 4)
            if code is None:
                out.append(esc)
                continue
            i += 4

            if 0xD800 <= code <= 0xDBFF and text[i : i + 2] == "\\u":
                low = _read_hex(text, i + 2, 4)
                if low is not None and 0xDC00 <= low <= 0xDFFF:
                    out.append(chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)))
                    i += 6
                    continue

            out.append(_safe_chr(code))
            continue

        if esc in _JS_SIMPLE_ESCAPES and not (esc == "0" and i < n and text[i].isdigit()):
            out.append(_JS_SIMPLE_ESCAPES[esc])
            continue

        out.append(esc)

    return "".join(out)


def parse_js_number(text: str) -> int | float | None:
    """Parse a JavaScript numeric literal (hex/octal/binary/decimal/float/BigInt)."""
    raw = text.strip().replace("_", "")
    if not raw:
        return None

    sign = 1
    if raw[0] in "+-":
        sign = -1 if raw[0] == "-" else 1
        raw = raw[1:]

    if raw.endswith(("n", "N")) and len(raw) > 1:
        raw = raw[:-1]

    prefix = raw[:2].lower()
    radix = {"0x": 16, "0o": 8, "0b": 2}.get(prefix)
    if radix is not None:
        try:
            return sign * int(raw[2:], radix)
        except ValueError:
            return None

    try:
        if any(c in raw for c in ".eE"):
            return sign * float(raw)
        return sign * int(raw)
    except ValueError:
        return None


def js_property_key(text: str) -> str:
    """Convert a non-string property key literal to the JS property name."""
    number = parse_js_number(text)
    if number is None:
        return text
    if isinstance(number, float) and number.is_integer():
        return str(int(number))
    return str(number)


def string_value(text: str) -> str:
    """Strip surrounding quotes and decode JS escapes."""
    if len(text) >= 2 and text[0] in "\"'`" and text[-1] == text[0]:
        return decode_js_escapes(text[1:-1])
    return decode_js_escapes(text)


class _Parser:
    """Recursive-descent parser over a single JS source string."""

    def __init__(self, source: str, *, bindings: dict[str, Any] | None = None) -> None:
        """Initialize parser state."""
        self.source = source
        self.i = 0
        self.n = len(source)
        self.bindings = dict(bindings or {})

    def _peek(self) -> str:
        return self.source[self.i] if self.i < self.n else ""

    def _advance(self, count: int = 1) -> str:
        start = self.i
        self.i = min(self.n, self.i + count)
        return self.source[start : self.i]

    def _skip_ws_and_comments(self) -> None:
        while self.i < self.n:
            ch = self.source[self.i]
            if ch.isspace():
                self.i += 1
                continue
            if ch == "/" and self.i + 1 < self.n:
                nxt = self.source[self.i + 1]
                if nxt == "/":
                    self.i += 2
                    while self.i < self.n and self.source[self.i] not in "\r\n":
                        self.i += 1
                    continue
                if nxt == "*":
                    end = self.source.find("*/", self.i + 2)
                    self.i = self.n if end < 0 else end + 2
                    continue
            break

    def _match(self, text: str) -> bool:
        self._skip_ws_and_comments()
        if self.source.startswith(text, self.i):
            self.i += len(text)
            return True
        return False

    def _match_keyword(self, word: str) -> bool:
        self._skip_ws_and_comments()
        if not self.source.startswith(word, self.i):
            return False
        end = self.i + len(word)
        if end < self.n and (_IDENT_RE.match(self.source[end]) or self.source[end] in "0123456789$"):
            return False
        self.i = end
        return True

    def parse_value(self) -> Any:
        """Parse one JS value expression (stops at top-level comma/semicolon/brace)."""
        self._skip_ws_and_comments()
        if self.i >= self.n:
            return None
        return self._parse_conditional()

    def _parse_conditional(self) -> Any:
        value = self._parse_logical_or()
        self._skip_ws_and_comments()
        if self._peek() != "?":
            return value
        self._advance()
        consequence = self._parse_conditional()
        if not self._match(":"):
            return value
        alternative = self._parse_conditional()
        return consequence if value else alternative

    def _parse_logical_or(self) -> Any:
        left = self._parse_logical_and()
        while True:
            self._skip_ws_and_comments()
            if not self._match("||"):
                return left
            # Unevaluable leftovers (member/call strings) keep full source elsewhere;
            # for catalog leaves prefer short-circuit like tree-sitter when left is concrete.
            if isinstance(left, str) and (left.startswith("_0x") or "[" in left or "(" in left or left in self.bindings):
                # Keep parity soft: evaluate right only when left is falsy-like.
                right = self._parse_logical_and()
                return left if left else right
            right = self._parse_logical_and()
            left = left if left else right

    def _parse_logical_and(self) -> Any:
        left = self._parse_equality()
        while True:
            self._skip_ws_and_comments()
            if not self._match("&&"):
                return left
            right = self._parse_equality()
            left = left if not left else right

    def _parse_equality(self) -> Any:
        left = self._parse_additive()
        while True:
            self._skip_ws_and_comments()
            if self._match("===") or self._match("!==") or self._match("==") or self._match("!="):
                _ = self._parse_additive()
                # Equality is rare in i18n/units leaves; keep left for structure.
                continue
            return left

    def _parse_additive(self) -> Any:
        left = self._parse_multiplicative()
        while True:
            self._skip_ws_and_comments()
            if self._match("+"):
                right = self._parse_multiplicative()
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    left = left + right
                elif isinstance(left, str) or isinstance(right, str):
                    left = f"{left}{right}"
                else:
                    left = f"{left}+{right}"
                continue
            if self._match("-"):
                right = self._parse_multiplicative()
                left = left - right if isinstance(left, (int, float)) and isinstance(right, (int, float)) else f"{left}-{right}"
                continue
            return left

    def _parse_multiplicative(self) -> Any:
        left = self._parse_unary()
        while True:
            self._skip_ws_and_comments()
            op = None
            for candidate in ("*", "/", "%"):
                if self.source.startswith(candidate, self.i):
                    op = candidate
                    break
            if op is None:
                return left
            self.i += len(op)
            right = self._parse_unary()
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                if op == "*":
                    left = left * right
                elif op == "/":
                    left = left / right
                else:
                    left = left % right
            else:
                left = f"{left}{op}{right}"

    def _parse_unary(self) -> Any:
        self._skip_ws_and_comments()
        start = self.i
        if self._match_keyword("void"):
            _ = self._parse_unary()
            return None
        if self._match("!"):
            # Match tree-sitter catalog semantics: unary leftovers stay as source text
            # (``!![]``, ``!0``), except we still parse the operand to advance the cursor.
            _ = self._parse_unary()
            return self.source[start : self.i].replace(" ", "")
        if self._match("-") or self._match("+"):
            sign = self.source[start]
            operand = self._parse_unary()
            if isinstance(operand, (int, float)):
                return -operand if sign == "-" else operand
            return f"{sign}{operand}"
        return self._parse_postfix()

    def _parse_postfix(self) -> Any:
        value = self._parse_primary()
        while True:
            self._skip_ws_and_comments()
            if self._peek() == "(":
                # Call expression — keep leftover source for later slices.
                call_start = self.i
                self._advance()
                depth = 1
                while self.i < self.n and depth:
                    ch = self._peek()
                    if ch in "\"'`":
                        self._read_string()
                        continue
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                    self._advance()
                leftover = (
                    self.source[call_start - len(str(value)) : self.i]
                    if isinstance(value, str)
                    else self.source[call_start : self.i]
                )
                # Prefer full text from identifier start when value was an identifier name.
                if isinstance(value, str) and value.isidentifier():
                    # Reconstruct poorly; store a compact call leftover.
                    value = f"{value}{self.source[call_start : self.i]}"
                else:
                    value = leftover or value
                continue
            if self._peek() == "[":
                self._advance()
                index = self.parse_value()
                self._match("]")
                if isinstance(value, Mapping) and isinstance(index, str) and index in value:
                    value = value[index]
                    continue
                # ``_0xabc['TOKEN']`` / ``ParameterCustomComponent['THREE_WAY_VALVE']``
                # collapse to the public token, matching tree-sitter catalog semantics.
                if (
                    isinstance(index, str)
                    and isinstance(value, str)
                    and (value.startswith("_0x") or _IDENT_RE.fullmatch(value) is not None)
                ):
                    value = index
                    continue
                leftover = f"{value}[{index!r}]"
                value = collapse_public_token(leftover)
                continue
            if self._peek() == ".":
                self._advance()
                name = self._read_identifier()
                leftover = f"{value}.{name}" if name else str(value)
                value = collapse_public_token(leftover)
                continue
            if self._match("=>"):
                # Arrow function: consume body as opaque source.
                body_start = self.i
                self._skip_ws_and_comments()
                if self._peek() == "{":
                    self._skip_balanced("{", "}")
                else:
                    _ = self._parse_conditional()
                params = value if isinstance(value, str) else "..."
                value = f"{params}=>{self.source[body_start : self.i].strip()}"
                continue
            return value

    def _parse_primary(self) -> Any:
        self._skip_ws_and_comments()
        ch = self._peek()
        if not ch:
            return None

        if ch in "\"'`":
            return string_value(self._read_string())

        if ch == "{":
            return self._parse_object()

        if ch == "[":
            return self._parse_array()

        if ch == "(":
            self._advance()
            # Possibly arrow params ``({...})=>`` or grouped expression.
            start = self.i
            if self._peek() == "{":
                # Could be destructuring params or object in parens.
                obj_or_block = self._parse_object()
                self._skip_ws_and_comments()
                if self._match(")"):
                    self._skip_ws_and_comments()
                    if self.source.startswith("=>", self.i):
                        return f"({self.source[start - 1 : self.i]})"
                    return obj_or_block
                # Unclosed — treat as leftover.
                return obj_or_block
            value = self.parse_value()
            self._match(")")
            return value

        if ch.isdigit() or (ch == "." and self.i + 1 < self.n and self.source[self.i + 1].isdigit()):
            return self._read_number()

        # Boolean / null keywords and identifiers.
        if self._match_keyword("true"):
            return True
        if self._match_keyword("false"):
            return False
        if self._match_keyword("null"):
            return None
        if self._match_keyword("undefined"):
            return None

        ident = self._read_identifier()
        if ident:
            if ident in self.bindings:
                return self.bindings[ident]
            return ident

        # Skip unknown character to avoid infinite loops.
        self._advance()
        return None

    def _parse_object(self) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        if not self._match("{"):
            return obj
        while True:
            self._skip_ws_and_comments()
            if self._peek() == "}" or not self._peek():
                self._match("}")
                return obj
            if self._match("..."):
                spread = self.parse_value()
                if isinstance(spread, Mapping):
                    obj.update(spread)
                self._match(",")
                continue

            key = self._parse_object_key()
            self._skip_ws_and_comments()
            if not self._match(":"):
                # Shorthand property.
                if isinstance(key, str) and key in self.bindings:
                    obj[key] = self.bindings[key]
                elif isinstance(key, str):
                    obj[key] = key
                self._match(",")
                if self._peek() == "}":
                    self._match("}")
                    return obj
                continue

            value = self.parse_value()
            obj[str(key)] = value
            self._match(",")
            if self._peek() == "}":
                self._match("}")
                return obj

    def _parse_object_key(self) -> str:
        self._skip_ws_and_comments()
        ch = self._peek()
        if ch in "\"'`":
            return string_value(self._read_string())
        if ch == "[":
            self._advance()
            # Computed keys may be IIFEs / arrows; take the bracket span as text and collapse.
            start = self.i
            depth = 1
            while self.i < self.n and depth:
                c = self._peek()
                if c in "\"'`":
                    self._read_string()
                    continue
                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                if depth:
                    self._advance()
            inner_src = self.source[start : self.i]
            self._match("]")
            try:
                inner_parser = _Parser(inner_src, bindings=self.bindings)
                inner = inner_parser.parse_value()
                collapsed = collapse_public_token(inner if isinstance(inner, str) else inner_src)
                return str(collapsed)
            except Exception:
                return str(collapse_public_token(inner_src))
        if ch.isdigit() or ch == ".":
            number = self._read_number()
            return js_property_key(str(number) if not isinstance(number, str) else number)
        start = self.i
        if self.source.startswith("0x", self.i) or self.source.startswith("0X", self.i):
            num = self._read_number()
            return js_property_key(str(int(num)) if isinstance(num, float) and num.is_integer() else str(num))
        ident = self._read_identifier()
        if ident:
            return ident
        self._advance()
        return self.source[start : self.i]

    def _parse_array(self) -> list[Any]:
        out: list[Any] = []
        if not self._match("["):
            return out
        while True:
            self._skip_ws_and_comments()
            if self._peek() == "]" or not self._peek():
                self._match("]")
                return out
            if self._match(","):
                continue
            out.append(self.parse_value())
            self._match(",")
            if self._peek() == "]":
                self._match("]")
                return out

    def _read_string(self) -> str:
        quote = self._advance()
        start = self.i
        while self.i < self.n:
            ch = self.source[self.i]
            if ch == "\\":
                self.i += 2
                continue
            if ch == quote:
                body = self.source[start : self.i]
                self.i += 1
                return quote + body + quote
            self.i += 1
        return quote + self.source[start:]

    def _read_number(self) -> int | float | str:
        start = self.i
        if self.source.startswith(("0x", "0X", "0o", "0O", "0b", "0B"), self.i):
            self.i += 2
            while self.i < self.n and self.source[self.i] in "0123456789abcdefABCDEF_":
                self.i += 1
        else:
            while self.i < self.n and (self.source[self.i].isdigit() or self.source[self.i] == "_"):
                self.i += 1
            if self.i < self.n and self.source[self.i] == ".":
                self.i += 1
                while self.i < self.n and (self.source[self.i].isdigit() or self.source[self.i] == "_"):
                    self.i += 1
            if self.i < self.n and self.source[self.i] in "eE":
                self.i += 1
                if self.i < self.n and self.source[self.i] in "+-":
                    self.i += 1
                while self.i < self.n and self.source[self.i].isdigit():
                    self.i += 1
        if self.i < self.n and self.source[self.i] in "nN":
            self.i += 1
        text = self.source[start : self.i]
        parsed = parse_js_number(text)
        return text if parsed is None else parsed

    def _read_identifier(self) -> str:
        self._skip_ws_and_comments()
        match = _IDENT_RE.match(self.source, self.i)
        if match is None:
            return ""
        self.i = match.end()
        return match.group(0)

    def _skip_balanced(self, open_ch: str, close_ch: str) -> None:
        if self._peek() != open_ch:
            return
        self._advance()
        depth = 1
        while self.i < self.n and depth:
            ch = self._peek()
            if ch in "\"'`":
                self._read_string()
                continue
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
            self._advance()


def _scan_top_level_declarations(source: str) -> list[tuple[str, int, int]]:
    """Return ``(kind, start, end)`` spans for top-level ``const``/``let``/``var`` decls."""
    out: list[tuple[str, int, int]] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in "\"'`":
            quote = ch
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            i += 2
            while i < n and source[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            end = source.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        # Prefer explicit search from i.
        kw = None
        for word in ("const", "let", "var"):
            if (
                source.startswith(word, i)
                and (i + len(word) >= n or not (source[i + len(word)].isalnum() or source[i + len(word)] in "_$"))
                and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in "_$"))
            ):
                kw = word
                break
        if kw is None:
            i += 1
            continue
        start = i
        i += len(kw)
        # Scan until top-level semicolon (not inside braces/parens/brackets/strings).
        depth_brace = depth_paren = depth_bracket = 0
        while i < n:
            c = source[i]
            if c in "\"'`":
                quote = c
                i += 1
                while i < n:
                    if source[i] == "\\":
                        i += 2
                        continue
                    if source[i] == quote:
                        i += 1
                        break
                    i += 1
                continue
            if c == "{":
                depth_brace += 1
            elif c == "}":
                depth_brace = max(0, depth_brace - 1)
            elif c == "(":
                depth_paren += 1
            elif c == ")":
                depth_paren = max(0, depth_paren - 1)
            elif c == "[":
                depth_bracket += 1
            elif c == "]":
                depth_bracket = max(0, depth_bracket - 1)
            elif c == ";" and depth_brace == depth_paren == depth_bracket == 0:
                i += 1
                break
            i += 1
        out.append((kw, start, i))
    return out


def _split_top_level_declarators(body: str) -> list[str]:
    """Split ``a=1, b={…}, c='x'`` on top-level commas."""
    parts: list[str] = []
    depth_brace = depth_paren = depth_bracket = 0
    start = 0
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch in "\"'`":
            quote = ch
            i += 1
            while i < n:
                if body[i] == "\\":
                    i += 2
                    continue
                if body[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace = max(0, depth_brace - 1)
        elif ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren = max(0, depth_paren - 1)
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket = max(0, depth_bracket - 1)
        elif ch == "," and depth_brace == depth_paren == depth_bracket == 0:
            parts.append(body[start:i].strip())
            start = i + 1
        i += 1
    tail = body[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def collect_bindings(source: str) -> dict[str, Any]:
    """Collect ``const``/``let``/``var`` bindings from a module, left-to-right."""
    bindings: dict[str, Any] = {}
    for _kind, start, end in _scan_top_level_declarations(source):
        decl = source[start:end]
        body = re.sub(r"^(?:const|let|var)\s+", "", decl.strip().rstrip(";"), count=1)
        for declarator in _split_top_level_declarators(body):
            match = re.match(r"^([A-Za-z_$][\w$]*)\s*=\s*", declarator)
            if match is None:
                continue
            name = match.group(1)
            value_src = declarator[match.end() :]
            parser = _Parser(value_src, bindings=bindings)
            try:
                value = parser.parse_value()
            except Exception:
                LOG.debug("Pure binding parse failed for %s", name, exc_info=True)
                continue
            bindings[name] = value
    return bindings


def _largest_object_literal(source: str, bindings: dict[str, Any]) -> Any | None:
    """Return the largest successfully parsed object literal in *source*."""
    best: Any | None = None
    best_size = -1
    i = 0
    n = len(source)
    while i < n:
        if source[i] != "{":
            i += 1
            continue
        parser = _Parser(source[i:], bindings=bindings)
        try:
            value = parser._parse_object()
        except Exception:
            i += 1
            continue
        consumed = parser.i
        if isinstance(value, dict) and consumed > best_size:
            best = value
            best_size = consumed
        i += 1
    return best


def parse_i18n_module(code: bytes) -> dict[str, Any]:
    """Parse an i18n JS module into a translation dict.

    Supports ``export default {…}``, ``export { X as default }``, string default
    exports (wrapped as a one-key object), and a largest-object fallback.
    """
    try:
        source = code.decode("utf-8", errors="replace")
        bindings = collect_bindings(source)
        translations: Any | None = None
        default_export_name: str | None = None
        saw_export_default = False

        # ``export default <expr>``
        for match in _EXPORT_DEFAULT_RE.finditer(source):
            saw_export_default = True
            parser = _Parser(source[match.end() :], bindings=bindings)
            translations = parser.parse_value()
            # Identify ``export default IDENT``.
            tail = source[match.end() : match.end() + 64].lstrip()
            ident_match = _IDENT_RE.match(tail)
            if ident_match and translations == bindings.get(ident_match.group(0), translations):
                default_export_name = ident_match.group(0)
            break

        if translations is None:
            as_default = _EXPORT_AS_DEFAULT_RE.search(source)
            if as_default is not None:
                saw_export_default = True
                default_export_name = as_default.group(1)
                translations = bindings.get(default_export_name)

        if translations is None and not saw_export_default:
            translations = _largest_object_literal(source, bindings)

        if isinstance(translations, dict):
            # Reject garbage from malformed ``export default {[};`` style parses.
            if saw_export_default and any("}" in str(k) or "{" in str(k) for k in translations):
                return {}
            return translations

        if isinstance(translations, str):
            cleaned = translations.strip()
            if not cleaned:
                return {}
            key = default_export_name if default_export_name else "__default__"
            return {key: cleaned}

        if translations is not None:
            LOG.warning("i18n export is not an object: %s", type(translations))
        return {}
    except Exception as exc:
        LOG.warning("Failed to parse i18n bundle: %s", exc)
        return {}


def iter_top_level_object_assignments(code: bytes) -> list[dict[str, Any]]:
    """Parse object literals assigned in top-level variable declarations."""
    source = code.decode("utf-8", errors="replace")
    bindings = collect_bindings(source)
    objects: list[dict[str, Any]] = []
    for value in bindings.values():
        if isinstance(value, dict):
            objects.append(value)
    # Also scan assignment-like ``name={…}`` without keyword (obfuscated defines).
    for match in re.finditer(r"=\s*\{", source):
        parser = _Parser(source[match.start() + 1 :], bindings=bindings)
        try:
            value = parser.parse_value()
        except Exception:
            LOG.debug("Pure object-assignment scan failed", exc_info=True)
            continue
        if isinstance(value, dict):
            objects.append(value)
    return objects


def find_language_config_object(code: bytes) -> dict[str, Any] | None:
    """Find ``{translations: [...], defaultTranslation: '...'}`` in index JS."""
    source = code.decode("utf-8", errors="replace")
    bindings = collect_bindings(source)

    def _is_translations_array(value: Any) -> bool:
        if not isinstance(value, list) or not value:
            return False
        objects = [item for item in value if isinstance(item, dict)]
        if not objects:
            return False
        valid = sum(1 for item in objects if "id" in item and "flag" in item)
        return valid >= len(objects) * 0.7

    def _is_language_config(obj: Mapping[str, Any]) -> bool:
        translations = obj.get("translations")
        default = obj.get("defaultTranslation")
        return _is_translations_array(translations) and isinstance(default, str)

    # Prefer objects from bindings / assignments.
    candidates = iter_top_level_object_assignments(code)
    # Deep scan: walk nested dicts in candidates.
    stack: list[Any] = list(candidates)
    seen: set[int] = set()
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, dict):
            if _is_language_config(cur):
                return dict(cur)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)

    # Brute-force scan object literals (quoted live shape often not in const).
    best: dict[str, Any] | None = None
    i = 0
    n = len(source)
    while i < n:
        if source[i] != "{":
            i += 1
            continue
        parser = _Parser(source[i:], bindings=bindings)
        try:
            value = parser._parse_object()
        except Exception:
            i += 1
            continue
        if isinstance(value, dict) and _is_language_config(value):
            best = value
            # Keep searching for no reason to prefer first; first structural hit matches TS DFS.
            return best
        i += 1
    return best
