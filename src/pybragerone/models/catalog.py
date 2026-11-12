"""Implementation of live asset catalog parsing from BragerOne web app.

This module provides classes and utilities for parsing and managing live assets
from the BragerOne web application, including:

- LiveAssetsCatalog: Main entry point for fetching and parsing assets
- AssetRef, AssetIndex: Data structures for tracking asset references
- ParamMap: Data structures for menu routes and parameter mappings
- TranslationConfig: Configuration for available translations
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .api.modules import DeviceMenuRef
from .menu import MenuResult, js_public_member_name
from .menu_manager import MenuManager, RawMenuData

if TYPE_CHECKING:
    from ..api import BragerOneApiClient

INDEX_ASSET_RE = re.compile(r"/assets/(index-[A-Za-z0-9_-]+\.js)")
_HELPER_ACTIONS = frozenset({"READ", "WRITE", "STATUS"})
# Only ``PARAM_*`` / ``STATUS_*`` are addressable tokens. Any other quoted upper-case
# literal in leftover source (``'WRITE'``, ``'DISPLAY_*'``) would be a bogus parameter.
_PUBLIC_PARAM_PATTERN = r"(?:PARAM|STATUS)_[A-Z0-9_]+"
# Catalog-like menu keys wrapped by single-arg obfuscated helpers
# (``_0x4d74a8('PARAM_1')``, ``_0x4d74a8('COMMAND_MODULE_RESTART')``).
_CATALOG_LIKE_TOKEN_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
# JS identifier boundaries (``[A-Za-z0-9_$]``) so ``DEFAULT_PARAM_177``,
# ``default_PARAM_177``, and ``$PARAM_177`` do not yield ``PARAM_177``.
_HELPER_TOKEN_RE = re.compile(rf"(?<![A-Za-z0-9_$]){_PUBLIC_PARAM_PATTERN}(?![A-Za-z0-9_$])")
_LEFTOVER_QUOTED_TOKEN_RE = re.compile(rf"""['"]({_PUBLIC_PARAM_PATTERN})['"]""")
_OBFUSCATED_IDENTIFIER_RE = re.compile(r"_0x[0-9a-fA-F]*")
# Leftover single-arg helper text: ``_0xabc('TOKEN')`` → TOKEN (defense when AST
# collapse misses and the call string becomes MenuParameter.token).
_OBFUSCATED_SINGLE_ARG_CALL_RE = re.compile(r"""(?<![A-Za-z0-9_$])_0x[0-9a-fA-F]*\(\s*(['"])(?P<tok>[A-Z][A-Z0-9_]*)\1\s*\)""")
# Home-tile chunks also call the public helper by name (unobfuscated in some builds).
_LOAD_PARAMETER_CALL_RE = re.compile(r"""(?<![A-Za-z0-9_$])loadParameter\(\s*(['"])(?P<tok>[A-Z][A-Z0-9_]*)\1\s*\)""")
# Tile chunks call many obfuscated helpers; only keep catalog parameter families so
# enum/component literals (``AUTO``, ``TILE_SWITCH``, …) are not candidate symbols.
_TILE_PARAMETER_TOKEN_RE = re.compile(r"^(?:PARAM_|STATUS_|COMMAND_|URUCHOMIENIE_|ZADANA_)[A-Z0-9_]+$")
# Minified bundles spell booleans as unary expressions: ``!0``/``!![]`` are true,
# ``!1``/``![]`` are false. Bare ``true``/``false`` are deliberately absent — at this
# layer they are indistinguishable from the quoted strings ``'true'``/``'false'``.
_JS_BOOL_LITERALS = {"!0": True, "!1": False, "![]": False, "!![]": True}
# ``void 0`` is spelled ``void 0x0`` once the bundle rewrites numeric literals as hex.
_JS_UNDEFINED_LITERALS = frozenset({"void 0", "void 0x0", "undefined"})

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
_HELPER_PARAM_TOKEN_RE = re.compile(r"^(?:PARAM|STATUS)_[A-Z0-9_]+$")
_TEMPLATE_INTERPOLATION_RE = re.compile(r"\$\{([A-Za-z_$][\w$]*)\}")


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


def _body_builds_object_factory(body_src: str) -> bool:
    """Return True when an arrow body looks like a ParamMap object factory."""
    stripped = body_src.strip()
    if stripped.startswith("(") and "{" in stripped:
        return True
    if stripped.startswith("{") and ("return" in stripped or stripped.startswith("{{") is False):
        # Statement block with object assignment/return, or direct object.
        if "return" in stripped or re.search(r"\bconst\b.*=\s*\{", stripped):
            return True
        # Direct object expression ``({...})`` already handled; bare ``{...}`` block.
        return "return" in stripped
    return False


def _parse_destructure_params(params_src: str) -> list[tuple[str, str, Any]]:
    """Parse ``({id: a, number: b = 1})`` into ``(src_key, local_name, default)`` specs."""
    text = params_src.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]
    specs: list[tuple[str, str, Any]] = []
    for item in re.split(r",(?![^\{\[\(]*[\]\}\)])", text):
        part = item.strip()
        if not part:
            continue
        default: Any = None
        if "=" in part:
            part, default_src = part.split("=", 1)
            part = part.strip()
            default_src = default_src.strip()
            try:
                default = _Parser(default_src).parse_value()
            except Exception:
                default = default_src
        if ":" in part:
            src_key, local = part.split(":", 1)
            specs.append((src_key.strip(), local.strip(), default))
        else:
            specs.append((part, part, default))
    return specs


def _eval_factory_body(body_src: str, local_bindings: dict[str, Any]) -> Any:
    """Evaluate a factory arrow body to an object using the pure parser."""
    stripped = body_src.strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        stripped = stripped[1:-1].strip()
    if stripped.startswith("{") and "return" not in stripped and "const" not in stripped:
        return _Parser(stripped, bindings=local_bindings).parse_value()

    # Statement block: ``{ const x = {...}; return x; }``
    inner = stripped[1:-1] if stripped.startswith("{") and stripped.endswith("}") else stripped
    block_bindings = dict(local_bindings)
    for _kind, start, end in _scan_top_level_declarations(inner):
        decl = inner[start:end]
        body = re.sub(r"^(?:const|let|var)\s+", "", decl.strip().rstrip(";"), count=1)
        for declarator in _split_top_level_declarators(body):
            match = re.match(r"^([A-Za-z_$][\w$]*)\s*=\s*", declarator)
            if match is None:
                continue
            name = match.group(1)
            value_src = declarator[match.end() :]
            try:
                block_bindings[name] = _Parser(value_src, bindings=block_bindings).parse_value()
            except Exception:
                LOG.debug("Pure factory body binding failed for %s", name, exc_info=True)
                continue
    ret = re.search(r"\breturn\b", inner)
    if ret is not None:
        return _Parser(inner[ret.end() :], bindings=block_bindings).parse_value()
    return None


def make_object_factory(params_src: str, body_src: str, bindings: dict[str, Any] | None) -> Any:
    """Build a Python callable for ``({…}) => { const o={…}; return o; }`` factories."""
    if not _body_builds_object_factory(body_src):
        return f"{params_src}=>{body_src.strip()}"
    specs = _parse_destructure_params(params_src)
    base = dict(bindings or {})
    # Bare identifier params (``x=>…`` / ``(_0x…)=>…``) bind the whole call argument.
    # Object-destructure params (``({id:e, number:n})=>…``) bind from a mapping argument.
    destructured = "{" in params_src

    def _factory(arg: Any) -> Any:
        local = dict(base)
        if not destructured and len(specs) == 1:
            _src_key, local_name, default = specs[0]
            local[local_name] = default if arg is None and default is not None else arg
            return _eval_factory_body(body_src, local)
        arg_map = arg if isinstance(arg, Mapping) else {}
        for src_key, local_name, default in specs:
            if src_key in arg_map:
                local[local_name] = arg_map[src_key]
            elif default is not None:
                local[local_name] = default
            else:
                local[local_name] = None
        return _eval_factory_body(body_src, local)

    return _factory


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


def string_value(text: str, *, bindings: Mapping[str, Any] | None = None) -> str:
    """Strip surrounding quotes and decode JS escapes.

    Template literals (backticks) optionally interpolate simple ``${ident}``
    bindings the same way the catalog path does.
    """
    quote = text[0] if text else ""
    body = decode_js_escapes(text[1:-1]) if len(text) >= 2 and quote in "\"'`" and text[-1] == quote else decode_js_escapes(text)
    if quote == "`" and bindings:

        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in bindings:
                return str(bindings[name])
            return match.group(0)

        body = _TEMPLATE_INTERPOLATION_RE.sub(_replace, body)
    return body


def _public_token_from_helper_args(callee: str, args: list[Any]) -> str | None:
    """Collapse obfuscated helper calls to a catalog token when args allow it."""
    if _OBFUSCATED_IDENTIFIER_RE.fullmatch(callee) is None:
        return None
    if len(args) == 1:
        token = args[0]
        if isinstance(token, str) and _CATALOG_LIKE_TOKEN_RE.fullmatch(token) is not None:
            return token
        return None
    if len(args) < 2:
        return None
    action = args[0]
    token = args[-1]
    if not isinstance(action, str) or action not in _HELPER_ACTIONS:
        return None
    # Match: two-arg helpers only collapse PARAM_*/STATUS_* (not DISPLAY_*).
    if not isinstance(token, str) or _HELPER_PARAM_TOKEN_RE.fullmatch(token) is None:
        return None
    return token


def _array_map_method(receiver: list[Any]) -> Any:
    """Return a callable implementing ``array['map'](callback)`` for menu write-lists."""

    def _map(callback: Any) -> list[Any]:
        if callable(callback) and not isinstance(callback, type):
            try:
                return [callback(item) for item in receiver]
            except Exception:
                LOG.debug("Pure array map callback failed; keeping receiver tokens", exc_info=True)
        # Fall back to the literal token list so MenuResult still sees PARAM_* entries.
        return list(receiver)

    return _map


_MAX_PARSE_DEPTH = 250


class _Parser:
    """Recursive-descent parser over a single JS source string."""

    def __init__(self, source: str, *, bindings: dict[str, Any] | None = None) -> None:
        """Initialize parser state."""
        self.source = source
        self.i = 0
        self.n = len(source)
        self.bindings = dict(bindings or {})
        self._depth = 0

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

    def _skip_one_value_span(self) -> None:
        """Advance past one value-shaped span without building a Python object."""
        self._skip_ws_and_comments()
        ch = self._peek()
        # ``ch and`` guards against ``"" in "{[("`` (empty substring is True in Python).
        if ch and ch in "{[(":
            closer = {"{": "}", "[": "]", "(": ")"}[ch]
            self._skip_balanced(ch, closer)
            return
        if ch and ch in "\"'`":
            self._read_string()
            return
        if ch in "+-":
            self._advance()
            ch = self._peek()
        if ch and (ch.isdigit() or ch == "." or self.source.startswith(("0x", "0X", "0o", "0O", "0b", "0B"), self.i)):
            self._read_number()
            return
        if ch and (_IDENT_RE.match(ch) is not None or ch in "_$"):
            self._read_identifier()
            return
        if ch:
            self._advance()

    def parse_value(self) -> Any:
        """Parse one JS value expression (stops at top-level comma/semicolon/brace)."""
        self._skip_ws_and_comments()
        if self.i >= self.n:
            return None
        if self._depth >= _MAX_PARSE_DEPTH:
            # Degrade pathologically nested payloads (see TestDeepNestingResilience).
            LOG.warning("Pure JS value exceeded parse depth %d; degrading to None", _MAX_PARSE_DEPTH)
            self._skip_one_value_span()
            return None
        self._depth += 1
        try:
            try:
                return self._parse_conditional()
            except RecursionError:
                # Match catalog semantics: degrade nested subtrees instead of crashing.
                LOG.warning("Pure JS value too deeply nested; degrading to None")
                self._skip_one_value_span()
                return None
        finally:
            self._depth -= 1

    def _parse_conditional(self) -> Any:
        value = self._parse_logical_or()
        self._skip_ws_and_comments()
        # ``?.`` is optional chaining (handled in postfix), not a ternary.
        if self._peek() != "?" or self.source.startswith("?.", self.i):
            return value
        self._advance()
        consequence = self._parse_conditional()
        if not self._match(":"):
            return value
        alternative = self._parse_conditional()
        return consequence if self._js_truthy(value) else alternative

    def _is_nullish(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and value.strip() in {"undefined", "void 0", "void 0x0"}:
            return True
        return bool(isinstance(value, str) and value.startswith("_0x"))

    def _js_truthy(self, value: Any) -> bool:
        """Approximate JavaScript truthiness (nullish ``_0x…`` leftovers are falsy)."""
        if self._is_nullish(value) or value is False:
            return False
        return bool(value != 0 and value != "")

    def _is_unevaluable_leftover(self, value: Any) -> bool:
        """Return whether *value* is unevaluated source text for ``||`` / ``&&``.

        Unary bang leftovers (``![]``, ``!1``) and similar
        must not short-circuit as truthy strings (``![] && [path]`` must not invent
        a value path).
        """
        if not isinstance(value, str):
            return False
        stripped = value.strip()
        if not stripped:
            return False
        return stripped.startswith("!")

    def _eval_optional_subscript(self, value: Any, index: Any) -> Any:
        """Evaluate ``receiver?.['index']`` like the catalog path (#329)."""
        if isinstance(value, Mapping) and isinstance(index, str):
            return value.get(index)
        # Unbound / nullish obfuscated receivers are undefined (SPA ``||`` fallback).
        if self._is_nullish(value):
            return None
        if isinstance(value, str) and (_IDENT_RE.fullmatch(value) is not None or value.startswith("_0x")):
            return None
        return None

    def _eval_optional_member(self, value: Any, name: str) -> Any:
        """Evaluate ``receiver?.name`` optional member access."""
        if not name:
            return None
        if isinstance(value, Mapping):
            return value.get(name)
        if self._is_nullish(value):
            return None
        if isinstance(value, str) and (_IDENT_RE.fullmatch(value) is not None or value.startswith("_0x")):
            return None
        return None

    def _parse_logical_or(self) -> Any:
        left = self._parse_nullish()
        while True:
            self._skip_ws_and_comments()
            if not self._match("||"):
                return left
            right = self._parse_nullish()
            if self._is_unevaluable_leftover(left):  # noqa: SIM108
                left = f"{left}||{right}"
            else:
                left = left if self._js_truthy(left) else right

    def _parse_nullish(self) -> Any:
        left = self._parse_logical_and()
        while True:
            self._skip_ws_and_comments()
            if not self._match("??"):
                return left
            right = self._parse_logical_and()
            left = right if self._is_nullish(left) else left

    def _parse_logical_and(self) -> Any:
        left = self._parse_bitwise_or()
        while True:
            self._skip_ws_and_comments()
            if not self._match("&&"):
                return left
            right = self._parse_bitwise_or()
            if self._is_unevaluable_leftover(left):  # noqa: SIM108
                left = f"{left}&&{right}"
            else:
                left = right if self._js_truthy(left) else left

    def _parse_equality(self) -> Any:
        left = self._parse_shift()
        while True:
            self._skip_ws_and_comments()
            op = None
            for candidate in ("===", "!==", "==", "!="):
                if self.source.startswith(candidate, self.i):
                    op = candidate
                    break
            if op is None:
                return left
            self.i += len(op)
            right = self._parse_shift()
            equal = left == right or (self._is_nullish(left) and self._is_nullish(right))
            left = equal if op in {"===", "=="} else (not equal)

    def _js_to_int32(self, value: Any) -> int | None:
        """Coerce a value the way JS bitwise ops do (``ToInt32``-ish).

        Booleans become ``0``/``1`` so equality results combine with ``&``/``|``/``^``
        (``1===1&0`` → ``0``). Non-integral floats and non-numerics return ``None``.
        """
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return None

    def _js_typeof(self, operand: Any) -> str:
        """Return a JavaScript-like ``typeof`` string for an already-parsed operand."""
        if operand is None or self._is_nullish(operand):
            return "undefined"
        if isinstance(operand, bool):
            return "boolean"
        if isinstance(operand, (int, float)) and not isinstance(operand, bool):
            return "number"
        if isinstance(operand, str):
            return "string"
        if isinstance(operand, (list, dict)):
            return "object"
        if callable(operand):
            return "function"
        return "undefined"

    def _parse_bitwise_or(self) -> Any:
        """Parse ``|`` (not ``||``) so SPA bitmasks inside arrows consume fully (#495)."""
        left = self._parse_bitwise_xor()
        while True:
            self._skip_ws_and_comments()
            if self.source.startswith("||", self.i):
                return left
            if not self._match("|"):
                return left
            right = self._parse_bitwise_xor()
            left_i, right_i = self._js_to_int32(left), self._js_to_int32(right)
            left = left_i | right_i if left_i is not None and right_i is not None else f"{left}|{right}"

    def _parse_bitwise_xor(self) -> Any:
        left = self._parse_bitwise_and()
        while True:
            self._skip_ws_and_comments()
            if not self._match("^"):
                return left
            right = self._parse_bitwise_and()
            left_i, right_i = self._js_to_int32(left), self._js_to_int32(right)
            left = left_i ^ right_i if left_i is not None and right_i is not None else f"{left}^{right}"

    def _parse_bitwise_and(self) -> Any:
        """Parse ``&`` (not ``&&``) for SPA ``x>>bit&0x1`` filters inside arrows (#495)."""
        left = self._parse_equality()
        while True:
            self._skip_ws_and_comments()
            if self.source.startswith("&&", self.i):
                return left
            if not self._match("&"):
                return left
            right = self._parse_equality()
            left_i, right_i = self._js_to_int32(left), self._js_to_int32(right)
            left = left_i & right_i if left_i is not None and right_i is not None else f"{left}&{right}"

    def _parse_shift(self) -> Any:
        left = self._parse_additive()
        while True:
            self._skip_ws_and_comments()
            op = None
            for candidate in (">>>", "<<", ">>"):
                if self.source.startswith(candidate, self.i):
                    op = candidate
                    break
            if op is None:
                return left
            self.i += len(op)
            right = self._parse_additive()
            left_i, right_i = self._js_to_int32(left), self._js_to_int32(right)
            if left_i is not None and right_i is not None:
                if op == "<<":
                    left = left_i << right_i
                elif op == ">>":
                    left = left_i >> right_i
                else:
                    left = (left_i % 0x100000000) >> right_i
            else:
                left = f"{left}{op}{right}"

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
                    # Keep source text on divide-by-zero (oracle returns ``"1/0"``).
                    left = f"{left}/{right}" if right == 0 else left / right
                else:
                    left = f"{left}%{right}" if right == 0 else left % right
            else:
                left = f"{left}{op}{right}"

    def _parse_unary(self) -> Any:
        self._skip_ws_and_comments()
        start = self.i
        if self._match_keyword("void"):
            _ = self._parse_unary()
            return None
        if self._match_keyword("typeof"):
            # SPA ``valueCallback`` arrows use ``typeof x==='number'?…`` (#495). Without
            # this unary the arrow body stops at ``typeof`` and the rest of the object
            # literal is misread as keys (overwriting ``number: 0x1`` with ``"number"``).
            return self._js_typeof(self._parse_unary())
        if self._match("!"):
            # Match catalog semantics: unary leftovers stay as source text
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
                call_start = self.i
                self._advance()
                args: list[Any] = []
                self._skip_ws_and_comments()
                if self._peek() != ")":
                    while True:
                        args.append(self.parse_value())
                        self._skip_ws_and_comments()
                        if self._match(","):
                            continue
                        break
                self._match(")")
                if callable(value) and not isinstance(value, type):
                    try:
                        value = value(args[0]) if len(args) == 1 else value(args)
                    except Exception:
                        LOG.debug("Pure factory call failed", exc_info=True)
                        value = f"<call:{call_start}>"
                    continue
                # Obfuscated helpers: ``_0x2d2290('WRITE', 'PARAM_45')`` → ``PARAM_45``.
                if isinstance(value, str):
                    helper_token = _public_token_from_helper_args(value, args)
                    if helper_token is not None:
                        value = helper_token
                        continue
                # Leftover call text for unresolved callees.
                if isinstance(value, str) and (_IDENT_RE.fullmatch(value) or value.startswith("_0x")):
                    value = f"{value}{self.source[call_start : self.i]}"
                else:
                    value = self.source[call_start : self.i]
                continue
            # Optional chaining: ``_0x?.['minValue']`` / ``obj?.prop`` (issue #329).
            if self.source.startswith("?.", self.i):
                self.i += 2
                self._skip_ws_and_comments()
                if self._peek() == "[":
                    self._advance()
                    index = self.parse_value()
                    self._match("]")
                    value = self._eval_optional_subscript(value, index)
                    continue
                name = self._read_identifier()
                value = self._eval_optional_member(value, name)
                continue
            if self._peek() == "[":
                self._advance()
                index = self.parse_value()
                self._match("]")
                if isinstance(value, Mapping) and isinstance(index, str) and index in value:
                    value = value[index]
                    continue
                # Live menus: ``['PARAM_45',…]['map'](x => ({…}))`` — keep a map method so
                # the following call evaluates (or falls back to the literal token list).
                if isinstance(value, list) and index == "map":
                    value = _array_map_method(value)
                    continue
                # ``_0xabc['TOKEN']`` / ``ParameterCustomComponent['THREE_WAY_VALVE']``
                # collapse to the public token, matching catalog semantics.
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
                body_start = self.i
                self._skip_ws_and_comments()
                if self._peek() == "{":
                    self._skip_balanced("{", "}")
                else:
                    _ = self._parse_conditional()
                params = value if isinstance(value, str) else "..."
                body_src = self.source[body_start : self.i]
                value = make_object_factory(params, body_src, self.bindings)
                continue
            return value

    def _parse_primary(self) -> Any:
        self._skip_ws_and_comments()
        ch = self._peek()
        if not ch:
            return None

        if ch in "\"'`":
            return string_value(self._read_string(), bindings=self.bindings)

        if ch == "{":
            return self._parse_object()

        if ch == "[":
            return self._parse_array()

        if ch == "(":
            paren_start = self.i
            self._advance()
            self._skip_ws_and_comments()
            if self._peek() == "{":
                # Destructuring arrow params ``({id: x = def, ...})=>`` must not be
                # parsed as a plain object (defaults use ``=`` which breaks pairs).
                brace_start = self.i
                self._skip_balanced("{", "}")
                self._skip_ws_and_comments()
                if self._match(")"):
                    self._skip_ws_and_comments()
                    if self.source.startswith("=>", self.i):
                        return self.source[paren_start : self.i]
                    # Grouped object literal ``({...})``.
                    return _Parser(self.source[brace_start:], bindings=self.bindings)._parse_object()
                # Fall through: reset and parse as grouped expression.
                self.i = paren_start + 1
            # Comma operator: ``(0, _0xabc)`` → last expression (SPA helper IIFEs).
            value = self.parse_value()
            while True:
                self._skip_ws_and_comments()
                if not self._match(","):
                    break
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


def extract_root_export(code: bytes) -> Any | None:
    """Extract the root ``export default`` value (object or array) from a JS module."""
    try:
        source = code.decode("utf-8", errors="replace")
        bindings = collect_bindings(source)
        value: Any | None = None

        for match in _EXPORT_DEFAULT_RE.finditer(source):
            parser = _Parser(source[match.end() :], bindings=bindings)
            value = parser.parse_value()
            break

        if value is None:
            as_default = _EXPORT_AS_DEFAULT_RE.search(source)
            if as_default is not None:
                value = bindings.get(as_default.group(1))

        if value is None:
            value = _largest_object_literal(source, bindings)

        return value
    except RecursionError:
        LOG.warning("Pure JS export too deeply nested; degrading to None")
        return None


def extract_root_object(code: bytes) -> dict[str, Any] | None:
    """Extract the root exported object from a JS module (ParamMap / generic export)."""
    try:
        value = extract_root_export(code)
        return value if isinstance(value, dict) else None
    except RecursionError:
        LOG.warning("Pure JS root object too deeply nested; degrading to None")
        return None


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


def is_translations_array_value(value: Any) -> bool:
    """Return whether *value* looks like the SPA ``translations`` array in index JS."""
    if not isinstance(value, list) or not value:
        return False
    objects = [item for item in value if isinstance(item, dict)]
    if not objects:
        return False
    valid = sum(1 for item in objects if "id" in item and "flag" in item)
    return valid >= len(objects) * 0.7


def find_language_config_object(code: bytes) -> dict[str, Any] | None:
    """Find ``{translations: [...], defaultTranslation: '...'}`` in index JS."""
    source = code.decode("utf-8", errors="replace")
    bindings = collect_bindings(source)

    def _is_language_config(obj: Mapping[str, Any]) -> bool:
        translations = obj.get("translations")
        default = obj.get("defaultTranslation")
        return is_translations_array_value(translations) and isinstance(default, str)

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


def _string_value(text: str) -> str:
    """Extract string literal value (quotes stripped, escapes decoded)."""
    return string_value(text)


def _decode_js_escapes(text: str) -> str:
    """Backward-compatible alias for :func:`decode_js_escapes`."""
    return decode_js_escapes(text)


_parse_js_number = parse_js_number
_js_property_key = js_property_key


def parse_js_declaration(code: bytes, *, bindings: Mapping[str, Any] | None = None) -> Any:
    """Parse the RHS of a ``const <name> = <expr>`` declaration (tests)."""
    source = code.decode("utf-8", errors="replace")
    match = re.search(r"const\s+\w+\s*=\s*(.*)", source, flags=re.DOTALL)
    if match is None:
        raise ValueError("expected const declaration")
    expr = match.group(1).strip().rstrip(";")
    local = dict(collect_bindings(source))
    if bindings:
        local.update(bindings)
    return _Parser(expr, bindings=local).parse_value()


def _find_inline_param_object_spans(code: bytes, *, max_objects: int = 10) -> list[tuple[int, int]]:
    """Find large object-literal byte spans that resemble inline param maps."""
    key_needles = (b"group", b"pool", b"use", b"value", b"unit", b"status", b"componentType")
    limit = min(len(code), 1_000_000)
    blob = code[:limit]
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(blob)
    while i < n and len(spans) < max_objects:
        if blob[i : i + 1] != b"{":
            i += 1
            continue
        start = i
        depth = 0
        in_str: bytes | None = None
        escape = False
        j = i
        closed = False
        while j < n:
            ch = blob[j : j + 1]
            if in_str is not None:
                if escape:
                    escape = False
                elif ch == b"\\":
                    escape = True
                elif ch == in_str:
                    in_str = None
                j += 1
                continue
            if ch in (b'"', b"'", b"`"):
                in_str = ch
                j += 1
                continue
            if ch == b"{":
                depth += 1
            elif ch == b"}":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    if end - start > 200 and any(k in blob[start:end] for k in key_needles):
                        spans.append((start, end))
                    i = end
                    closed = True
                    break
            j += 1
        if not closed:
            i += 1
    return spans


def _token_from_obfuscated_call_text(text: str) -> str | None:
    """Extract a catalog-like token from leftover ``_0x…('TOKEN')`` call text."""
    match = _OBFUSCATED_SINGLE_ARG_CALL_RE.fullmatch(text.strip())
    if match is None:
        match = _OBFUSCATED_SINGLE_ARG_CALL_RE.search(text)
    if match is None:
        return None
    return match.group("tok")


_JS_ESCAPE_LEAK_RE = re.compile(r"\\(?:x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4})")


def _count_js_escape_leaks(value: Any) -> int:
    r"""Count strings that still contain JS ``\x`` / ``\u`` / ``\u{...}`` escape sequences.

    After a successful parse those sequences should already have been decoded. A
    leftover leak means a new escape form slipped past ``_decode_js_escapes``.
    Incomplete fragments such as ``\\x2`` or ``\\u00`` are not JS escapes.
    """
    if isinstance(value, str):
        return 1 if _JS_ESCAPE_LEAK_RE.search(value) else 0
    if isinstance(value, Mapping):
        return sum(_count_js_escape_leaks(item) for item in value.values())
    if isinstance(value, list):
        return sum(_count_js_escape_leaks(item) for item in value)
    return 0


def _i18n_import_base_and_hash(namespace: str, stem: str) -> tuple[str, str]:
    """Split an i18n import stem into ``(base, hash)`` using the JSON namespace.

    Vite hashes may contain hyphens (``info-Bpu026-3``) or end with one
    (``tariff-Db9Vj8s-``). ``str.rpartition("-")`` would treat those as extra
    base segments. The JSON path already names the namespace, so everything after
    ``<namespace>-`` is the hash.

    Args:
        namespace: Namespace captured from the language JSON path (e.g. ``info``).
        stem: Import filename without ``.js`` (e.g. ``info-Bpu026-3``).

    Returns:
        ``(base, hash)``. Hash is empty when the import has no ``-hash`` suffix.
        When *stem* does not start with *namespace*, the whole stem is the base.
    """
    prefix = f"{namespace}-"
    stem_l = stem.lower()
    if stem_l.startswith(prefix.lower()):
        return namespace, stem[len(namespace) + 1 :]
    if stem_l == namespace.lower():
        return namespace, ""
    return stem, ""


# ----------------------------- Data types -----------------------------


_EXTENDS_REF_RE = re.compile(r"^(\d+)[:/]([A-Za-z0-9_.-]+)$")


def _parse_extends_ref(ref: str) -> tuple[int, str] | None:
    """Parse SPA ``extends`` tokens such as ``153:1211`` or ``153/1211``."""
    match = _EXTENDS_REF_RE.match(str(ref).strip())
    if match is None:
        return None
    return int(match.group(1)), str(match.group(2))


@dataclass(slots=True)
class AssetRef:
    """Reference to a versioned asset from the BragerOne catalog.

    Attributes:
        url: The full URL to the asset file.
        base: The base name without hash (e.g., 'module.menu' from 'module.menu-BNvCCsxi').
        hash: The hash identifier for this version (e.g., 'BNvCCsxi').
        etag: Optional ETag from HTTP headers for cache validation.
        last_modified: Optional last modified timestamp from HTTP headers.
    """

    url: str
    base: str  # BASENAME (np. 'module.menu-BNvCCsxi' → base='module.menu')
    hash: str  # 'BNvCCsxi'
    etag: str | None = None
    last_modified: str | None = None


@dataclass(slots=True)
class AssetIndex:
    """Index of assets parsed from ``index-*.js`` file.

    Attributes:
        assets_by_basename: Full list of assets declared in ``index-*.js`` (exact basenames, no normalization).
            Maps basename strings to lists of AssetRef objects.
        menu_map: Mapping from deviceMenu integers to preferred BASENAME stems
            (variant ``0`` when present, else first candidate).
        menu_variant_map: Mapping from ``(deviceMenu, variant)`` to hashed stems for SPA
            ``extends`` refs such as ``153:1211`` (#438).
        tile_map: Mapping from ``(manuf_code, dev_code)`` to hashed ``deviceTile`` stems
            (SPA home dashboard tiles; default chunk is ``(0, 0)``).
        inline_param_candidates: List of (start_byte, end_byte) tuples indicating potential
            inline parameter maps detected within ``index-*.js``.
        index_bytes: Raw bytes of the index file for potential inline parsing.
    """

    # full list of assets declared in index-*.js (exact basenames, no normalization)
    assets_by_basename: dict[str, list[AssetRef]] = field(default_factory=dict)
    # mapping from deviceMenu:int -> BASENAME('module.menu-<hash>.js')
    menu_map: dict[int, str] = field(default_factory=dict)
    # deviceMenu/N/variant.ts -> hashed stem (every candidate; used by extends)
    menu_variant_map: dict[tuple[int, str], str] = field(default_factory=dict)
    # static side-menu route chunks: path basename -> asset basename (e.g. timezones -> timezones)
    static_route_map: dict[str, str] = field(default_factory=dict)
    # deviceTile/manuf/dev.ts -> hashed stem (home dashboard tiles)
    tile_map: dict[tuple[int, int], str] = field(default_factory=dict)
    # inline parameter maps detected within index-*.js
    inline_param_candidates: list[tuple[int, int]] = field(default_factory=list)  # (start_byte, end_byte)
    # raw index for potential inline parsing
    index_bytes: bytes = b""

    def find_asset_for_basename(self, basename: str) -> AssetRef | None:
        """Find an asset reference by its basename.

        Args:
            basename: The basename of the asset to search for.

        Returns:
            The last asset reference found for the given basename, or None if no
            asset is found. When multiple assets share the same basename, returns
            the last one (typically the newest hash).

        Note:
            Uses an alpha heuristic that assumes the last asset in the list is
            the most recent version when multiple assets share the same basename.
        """
        lst = self.assets_by_basename.get(basename)
        if not lst:
            return None
        # Alpha heuristic: take the last found (usually the newest hash)
        return lst[-1]

    def find_asset_for_full_name(self, full_name: str) -> AssetRef | None:
        """Find an asset reference by its full name with hash (e.g., 'module.menu-Dbo_n32n').

        Args:
            full_name: Stem (``base-hash``) or filename (``base-hash.js``).

        Returns:
            The asset reference if found, or None if not found.
        """
        stem = full_name[:-3] if full_name.lower().endswith(".js") else full_name
        filename = stem + ".js"
        for basename_assets in self.assets_by_basename.values():
            for asset in basename_assets:
                if f"{asset.base}-{asset.hash}" == stem:
                    return asset
                if asset.url.rsplit("/", 1)[-1] == filename:
                    return asset
        return None


@dataclass(slots=True)
class ParamMap:
    """Represents a parameter mapping in the BragerOne system.

    This class encapsulates the mapping between parameter identifiers and their
    metadata, including paths, units, limits, and status flags. It serves as a
    structured representation of parameter configurations retrieved from the router.

    Attributes:
        key: The unique parameter identifier token from the router.
            Examples: "URUCHOMIENIE_KOTLA", "PARAM_66".
        group: Optional parameter group identifier. Example: "P6".
        paths: Dictionary mapping path types to their respective path lists.
            Entries are normalized lists of dictionaries describing pool/index/use
            metadata for value/unit/status/command/min/max channels.
        component_type: Optional type of the UI component associated with this parameter.
        units: Optional measurement unit identifier. May be a localized string, numeric
            code, or mapping used for enumerations; resolution happens via the units
            i18n catalog where possible.
        limits: Optional dictionary containing parameter limit definitions and constraints.
        status_flags: List of dictionaries defining various status flags and their meanings.
        origin: Source of the parameter map definition.
            Format: "asset:<url>" for external sources or "inline:index" for inline definitions.
        raw: The raw, unprocessed parameter map dictionary. Preserved for future use
            in internationalization (i18n) and logging purposes.

    Example:
        >>> param_map = ParamMap()
        >>> param_map.key = "PARAM_66"
        >>> param_map.group = "P6"
        >>> param_map.paths = {"v": ["status", "value"], "u": ["status", "unit"]}
    """

    key: str  # token from router: np. "URUCHOMIENIE_KOTLA" lub "PARAM_66"
    group: str | None  # np. "P6"
    paths: dict[str, list[dict[str, Any]]]  # value/unit/status/command/min/max channel descriptors
    component_type: str | None
    units: str | int | float | dict[str, Any] | list[Any] | None
    limits: dict[str, Any] | None
    status_flags: list[dict[str, Any]]
    status_conditions: dict[str, list[dict[str, Any]]] | None
    command_rules: list[dict[str, Any]]
    origin: str  # "asset:<url>" or "inline:index"
    raw: dict[str, Any]  # raw map (will be useful later for i18n/logging)


# ----------------------------- TranslationConfig -----------------------------


@dataclass
class TranslationConfig:
    """Configuration of available translations."""

    translations: list[dict[str, Any]]
    default_translation: str


# ----------------------------- LiveAssetsCatalog -----------------------------


class LiveAssetsCatalog:
    """Main entry point: fetches index-<hash>.js, parses router (module.menu-<hash>.js).

    Only loads necessary parameter map files (based on router tokens).
    """

    def __init__(
        self,
        api: BragerOneApiClient,
        logger: logging.Logger | None = None,
        visibility_strategy: str = "independent",  # "independent" | "parent_gates_children" (for future use)
        schemas_enabled: bool = False,  # hook (OFF)
        request_timeout: float = 8.0,
        concurrency: int = 8,
    ) -> None:
        """Initialize the LiveAssetsCatalog.

        Args:
            api: BragerOneApiClient used to fetch assets and index files.
            logger: Optional logger to use for informational and debug output.
            visibility_strategy: Strategy for gating menu visibility (default 'independent').
            schemas_enabled: Whether schema validation is enabled (currently unused).
            request_timeout: Timeout for network requests in seconds.
            concurrency: Maximum concurrent ParamMap asset fetches.
        """
        self._api = api
        self._timeout = request_timeout
        self._asset_sema = asyncio.Semaphore(max(1, concurrency))
        self._idx = AssetIndex()
        self._log = logger or logging.getLogger(__name__)
        self._last_index_url: str | None = None

        # Cache for language-scoped i18n namespaces (from index-driven mapping)
        self._cache_i18n: dict[tuple[str, str], dict[str, Any]] = {}
        self._i18n_lock = asyncio.Lock()
        self._units_descriptor_table: dict[str, dict[str, Any]] | None = None
        self._units_descriptor_lock = asyncio.Lock()
        self._custom_unit_codes: dict[str, str] | None = None
        self._index_token_raw_maps: dict[str, dict[str, Any]] | None = None
        self._index_token_raw_maps_sig: tuple[int, bytes, bytes] | None = None
        self._index_token_raw_maps_lock = asyncio.Lock()

        # New menu management system
        self._menu_manager = MenuManager(self._log)
        # device_menu -> devices fingerprint used when the raw menu was cached (#438)
        self._menu_devices_fp: dict[int, str] = {}
        self._static_route_tokens_cache: dict[str, set[str]] = {}
        self._index_generation = 0

        # Track auto-discovery attempts to help guard repeated network fetches
        self._index_autoload_attempts = 0

    def _smart_urljoin(self, base_url: str, relative_url: str) -> str:
        """Smart urljoin that handles assets prefix correctly to avoid double /assets/ paths.

        Args:
            base_url: Base URL (usually an index file like /assets/index-hash.js)
            relative_url: Relative URL, may start with assets/

        Returns:
            Properly joined URL without duplicate /assets/ segments
        """
        from urllib.parse import urljoin

        # If relative_url starts with assets/ and base_url contains /assets/,
        # remove the assets/ prefix from relative_url to avoid duplication
        if relative_url.startswith("assets/") and "/assets/" in base_url:
            # Remove assets/ prefix
            relative_url = relative_url[7:]  # len('assets/') = 7

        return urljoin(base_url, relative_url)

    # ---------- lifecycle ----------

    async def __aenter__(self) -> LiveAssetsCatalog:
        """Enter the async context manager and return self."""
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Exit the async context manager."""
        pass

    # ---------- INDEX ----------

    async def refresh_index(self, index_url: str, *, allow_recover: bool = True) -> None:
        """Fetches index-<hash>.js and builds full asset index.

        - assets_by_basename (exact BASENAME → [AssetRef])
        - menu_map: int -> BASENAME(module.menu-<hash>.js), if present in index
        - inline_param_candidates: list of (start,end) large objects in index that look like param-maps
        """
        try:
            code = await self._api.get_bytes(index_url)
        except Exception as exc:
            if allow_recover and "index-" in index_url:
                self._log.warning("Index fetch failed for %s, attempting rediscovery: %s", index_url, exc)
                await self._auto_discover_and_load_index()
                if self._idx.index_bytes:
                    return
            raise
        self._last_index_url = index_url  # Store for i18n URL construction
        self._idx = self._build_asset_index_from_index_js(index_url, code)
        self._index_generation += 1
        self._static_route_tokens_cache.clear()
        self._units_descriptor_table = None
        self._custom_unit_codes = None
        self._index_token_raw_maps = None
        self._index_token_raw_maps_sig = None
        self._log.info(
            "INDEX: assets=%d basenames=%d menus=%d tiles=%d inline_param_candidates=%d",
            sum(len(v) for v in self._idx.assets_by_basename.values()),
            len(self._idx.assets_by_basename),
            len(self._idx.menu_map),
            len(self._idx.tile_map),
            len(self._idx.inline_param_candidates),
        )

    async def _auto_discover_and_load_index(self) -> None:
        """Auto-discover and load the index file."""
        self._log.info("Auto-discovering index file...")

        try:
            base = self._api.one_base.rstrip("/")
            candidate_urls: list[str] = []

            for page_url in (f"{base}/", f"{base}/assets/"):
                try:
                    html = (await self._api.get_bytes(page_url)).decode("utf-8", errors="replace")
                except Exception as page_exc:
                    self._log.debug("Index discovery page fetch failed (%s): %s", page_url, page_exc)
                    continue
                for match in INDEX_ASSET_RE.finditer(html):
                    candidate_urls.append(f"{base}/assets/{match.group(1)}")

            for discovered_url in list(dict.fromkeys(candidate_urls)):
                try:
                    self._log.info("Discovered index candidate: %s", discovered_url)
                    await self.refresh_index(discovered_url, allow_recover=False)
                    return
                except Exception as discover_exc:
                    self._log.debug("Discovered index failed (%s): %s", discovered_url, discover_exc)

            # Try alternative URLs if discovery failed
            alt_urls = [f"{base}/assets/index-main.js", f"{base}/assets/index.js"]

            for alt_url in alt_urls:
                try:
                    self._log.debug("Trying alternative: %s", alt_url)
                    await self.refresh_index(alt_url, allow_recover=False)
                    self._log.info("Success with alternative: %s", alt_url)
                    return
                except Exception as e:
                    self._log.debug("Alternative failed: %s - %s", alt_url, e)

            # If all fails, log warning
            self._log.warning("Failed to auto-discover index file")

        except Exception as e:
            self._log.warning("Error auto-discovering index: %s", e)

    async def _ensure_index_loaded(self) -> None:
        """Best-effort ensure that the asset index is available."""
        if self._idx.index_bytes or self._idx.assets_by_basename:
            return

        attempt = self._index_autoload_attempts + 1
        self._index_autoload_attempts = attempt
        self._log.debug("Index not loaded yet. Auto-discovery attempt %d", attempt)

        try:
            await self._auto_discover_and_load_index()
        except Exception as e:  # pragma: no cover - should not happen but guard just in case
            self._log.warning("Auto-discovery attempt %d failed: %s", attempt, e)

    def _build_asset_index_from_index_js(self, index_url: str, code: bytes) -> AssetIndex:
        text = code.decode("utf-8", errors="replace")

        # Performance optimization: limit regex search to first part of file for most assets
        # Most index files have assets declared early, but we keep a fallback for full file
        search_text = text[:50000] if len(text) > 50000 else text

        # 1) Collect all '*-<hash>.js' paths from literals - SIMPLIFIED FOR PERFORMANCE
        # Much simpler regex that should be faster
        assets_by_basename: dict[str, list[AssetRef]] = {}

        # Parameters and i18n assets frequently live deeper in the bundle, so we scan both the
        # leading slice and the remaining part. We also normalise basenames to strip path prefixes.
        simple_pattern = re.compile(r"([A-Za-z0-9._/-]+?)-([A-Za-z0-9_-]+)\.js")

        def _register(matches: Iterable[re.Match[str]]) -> None:
            for m in matches:
                raw_base = m.group(1)
                h = m.group(2)
                # Normalise '../parameters/write/FOO' → 'FOO'
                norm_base = raw_base.rsplit("/", 1)[-1]
                full_url = self._smart_urljoin(index_url, f"{raw_base}-{h}.js")
                bucket = assets_by_basename.setdefault(norm_base, [])
                if all(existing.hash != h or existing.url != full_url for existing in bucket):
                    bucket.append(AssetRef(url=full_url, base=norm_base, hash=h))

        _register(simple_pattern.finditer(search_text))

        if len(text) > len(search_text):
            self._log.debug("Scanning remaining index fragment for additional assets...")
            _register(simple_pattern.finditer(text[len(search_text) :]))

        # 2) Try to find mapping from deviceMenu:int -> menu asset in index (Regex fallback)
        # Use regex pattern matching since AST parsing can fail on complex minified Object.assign payloads.
        menu_map: dict[int, str] = {}
        menu_variant_map: dict[tuple[int, str], str] = {}

        try:
            # Pattern examples (legacy + current):
            #   "../config/router/deviceMenu/N/module.menu.ts":()=>...import("./module.menu-HASH.js")
            #   "/src/config/router/deviceMenu/N/0.ts":()=>...import("./0-HASH.js")
            #   "../../config/router/deviceMenu/N/101.ts":()=>...import("./101-HASH.js")
            device_menu_pattern = re.compile(
                r"['\"](?:(?:\.\./)+config/router|/src/config/router)/deviceMenu/(\d+)/([A-Za-z0-9_.-]+)\.ts['\"]"
                r"\s*:\s*\(\)\s*=>\s*[A-Za-z_$][\w$]*\s*\(\s*\(\)\s*=>\s*import\s*\(\s*"
                r"['\"]\./([A-Za-z0-9_.-]+-[A-Za-z0-9_-]+)\.js['\"]\s*\)"
            )
            menu_candidates: dict[int, list[tuple[str, str]]] = {}

            # Reuse resiliently decoded text prepared at function start.
            code_str = text

            for match in device_menu_pattern.finditer(code_str):
                device_menu_num = int(match.group(1))
                variant_name = str(match.group(2))
                menu_file_name = str(match.group(3))
                menu_candidates.setdefault(device_menu_num, []).append((variant_name, menu_file_name))
                self._log.debug(
                    "Found deviceMenu mapping candidate: %d/%s -> %s",
                    device_menu_num,
                    variant_name,
                    menu_file_name,
                )

            for device_menu_num, candidates in menu_candidates.items():
                for variant_name, menu_file_name in candidates:
                    menu_variant_map.setdefault((device_menu_num, variant_name), menu_file_name)
                preferred = next((asset for variant, asset in candidates if variant == "0"), None)
                if preferred is None:
                    preferred = candidates[0][1]
                menu_map[device_menu_num] = preferred
                self._log.debug("Selected deviceMenu mapping: %d -> %s", device_menu_num, preferred)

        except Exception as regex_e:
            self._log.debug("Regex deviceMenu parsing failed: %s", regex_e)
            menu_variant_map = {}

        static_route_map: dict[str, str] = {}
        try:
            # Bound the gap between the static route key and its import so a
            # malformed entry without ``import(...)`` cannot steal the next
            # entry's chunk (DOTALL ``.*?`` previously crossed manifest keys).
            static_route_pattern = re.compile(
                r"deviceMenu/static/([A-Za-z0-9_-]+)\.ts['\"]"
                r"(?:(?!deviceMenu/static/)[\s\S]){0,160}?"
                r"import\s*\(\s*['\"]\./([A-Za-z0-9_.-]+)-([A-Za-z0-9_-]+)\.js['\"]",
            )
            for match in static_route_pattern.finditer(text):
                route_path = str(match.group(1))
                asset_base = str(match.group(2))
                static_route_map.setdefault(route_path, asset_base)
        except Exception as static_exc:
            self._log.debug("Static deviceMenu route parsing failed: %s", static_exc)

        tile_map: dict[tuple[int, int], str] = {}
        try:
            # Mirror deviceMenu import shape for home dashboard tiles:
            #   "../../config/router/deviceTile/0/0.ts":()=>...import("./0-C-o8CJ8v.js")
            #   "../../config/router/deviceTile/153/1211.ts":()=>...import("./1211-CrKFnoNa.js")
            device_tile_pattern = re.compile(
                r"['\"](?:(?:\.\./)+config/router|/src/config/router)/deviceTile/(\d+)/(\d+)\.ts['\"]"
                r"\s*:\s*\(\)\s*=>\s*[A-Za-z_$][\w$]*\s*\(\s*\(\)\s*=>\s*import\s*\(\s*"
                r"['\"]\./([A-Za-z0-9_.-]+-[A-Za-z0-9_-]+)\.js['\"]\s*\)"
            )
            for match in device_tile_pattern.finditer(text):
                manuf_code = int(match.group(1))
                dev_code = int(match.group(2))
                tile_stem = str(match.group(3))
                tile_map.setdefault((manuf_code, dev_code), tile_stem)
                self._log.debug(
                    "Found deviceTile mapping: %d/%d -> %s",
                    manuf_code,
                    dev_code,
                    tile_stem,
                )
        except Exception as tile_exc:
            self._log.debug("Regex deviceTile parsing failed: %s", tile_exc)
            tile_map = {}

        # Prepare limited code for AST parsing (needed for inline param candidates)
        ast_limit = min(1000000, len(code))
        limited_code = code[:ast_limit]

        # 3) Inline param-map candidates (brace-span scan; token maps used at resolve time)
        inline_candidates: list[tuple[int, int]] = []

        if limited_code:
            try:
                inline_candidates = _find_inline_param_object_spans(limited_code)
            except Exception as param_e:
                self._log.debug("Param candidates scan failed: %s", param_e)

        return AssetIndex(
            assets_by_basename=assets_by_basename,
            menu_map=menu_map,
            menu_variant_map=menu_variant_map,
            static_route_map=static_route_map,
            tile_map=tile_map,
            inline_param_candidates=inline_candidates,
            index_bytes=code,
        )

    @staticmethod
    def _extract_public_tokens_from_js(code: bytes) -> set[str]:
        """Return PARAM/STATUS tokens referenced in a minified JS chunk."""
        text = code.decode("utf-8", errors="replace")
        tokens: set[str] = set()
        tokens.update(_HELPER_TOKEN_RE.findall(text))
        tokens.update(_LEFTOVER_QUOTED_TOKEN_RE.findall(text))
        return tokens

    @staticmethod
    def _extract_tile_parameter_tokens_from_js(code: bytes) -> set[str]:
        """Return catalog parameter tokens bound by a ``deviceTile`` chunk.

        Home tiles call ``loadParameter('TOKEN')`` / obfuscated single-arg helpers
        with tokens beyond ``PARAM_*`` / ``STATUS_*`` (e.g. ``URUCHOMIENIE_*``,
        ``ZADANA_*_WRITE``). Menu leftover extraction intentionally excludes those
        to avoid permission/enum noise, so tiles need a dedicated extractor that
        still rejects unrelated ALL-CAPS literals (``AUTO``, ``TILE_SWITCH``, …).
        """
        text = code.decode("utf-8", errors="replace")
        tokens: set[str] = set()
        for match in _OBFUSCATED_SINGLE_ARG_CALL_RE.finditer(text):
            tokens.add(match.group("tok"))
        for match in _LOAD_PARAMETER_CALL_RE.finditer(text):
            tokens.add(match.group("tok"))
        return {token for token in tokens if _TILE_PARAMETER_TOKEN_RE.fullmatch(token) is not None}

    async def discover_status_bar_parameter_tokens(self) -> set[str]:
        """Return SPA footer status-bar parameter tokens from the vite asset map.

        The web app registers footer diodes as dedicated chunks under
        ``/src/constants/parameters/STATUS_BAR_*.ts`` (and matching hashed
        ``STATUS_BAR_*-*.js`` assets). Those tokens are not attached to menu
        panel groups, so HA bootstrap must discover them from the index.
        """
        await self._ensure_index_loaded()
        tokens: set[str] = set()
        if self._idx.index_bytes:
            text = self._idx.index_bytes.decode("utf-8", errors="replace")
            tokens.update(match.group(1) for match in re.finditer(r"/src/constants/parameters/(STATUS_BAR_[A-Z0-9_]+)\.ts", text))
        for basename in self._idx.assets_by_basename:
            if basename.startswith("STATUS_BAR_") and basename.isupper():
                tokens.add(basename)
        return tokens

    async def discover_device_tile_parameter_tokens(
        self,
        devices: Sequence[DeviceMenuRef] | None = None,
    ) -> set[str]:
        """Return SPA home-tile parameter tokens for the given module devices.

        Mirrors SPA ``getTilesConstruction``: when any device-specific
        ``deviceTile/{manuf}/{dev}`` chunk is present (and SPA would treat the
        module as standalone), those chunks **replace** the default ``0/0``
        group — they are not merged with it. Otherwise fall back to
        ``deviceTile/0/0``. Tile bindings have no ``permissionModule``, so
        LEVEL_MAX menu symbols can still appear on the dashboard for LEVEL_1
        accounts (#478).
        """
        await self._ensure_index_loaded()
        # Match ``discover_static_route_tokens``: only proceed when an index load
        # left bytes or basename assets (``tile_map`` alone can be stale).
        if not (self._idx.index_bytes or self._idx.assets_by_basename):
            return set()

        stems: list[str] = []
        if devices:
            for ref in devices:
                stem = self._idx.tile_map.get((ref.manuf_code, ref.dev_code))
                if stem is not None:
                    stems.append(stem)
        if not stems:
            default_stem = self._idx.tile_map.get((0, 0))
            if default_stem is not None:
                stems.append(default_stem)
        if not stems:
            return set()

        generation = self._index_generation
        tokens: set[str] = set()
        seen_stems: set[str] = set()
        for stem in stems:
            if stem in seen_stems:
                continue
            seen_stems.add(stem)
            asset_ref = self._idx.find_asset_for_full_name(stem)
            if asset_ref is None:
                # Stem may already be registered as a basename key (tests / odd hashes).
                asset_ref = self._idx.find_asset_for_basename(stem)
            if asset_ref is None:
                self._log.debug("No asset found for deviceTile stem %s", stem)
                continue
            try:
                code = await self._api.get_bytes(asset_ref.url)
            except Exception as exc:
                self._log.debug("deviceTile asset fetch failed for %s: %s", stem, exc)
                continue
            if generation != self._index_generation:
                return set()
            tokens.update(self._extract_tile_parameter_tokens_from_js(code))
            if generation != self._index_generation:
                return set()
        return tokens

    async def discover_static_route_tokens(self, route_path: str) -> set[str]:
        """Return parameter tokens declared in a static ``deviceMenu/static/<path>.ts`` chunk.

        Live menus sometimes expose a side-menu route (e.g. ``MAINMENU_STREFY_CZASOWE`` /
        path ``timezones``) with no ``read``/``write`` parameters in ``module.menu-*.js``.
        The SPA loads symbols from a separate static route bundle referenced in ``index-*.js``.
        """
        path_key = route_path.strip().strip("/")
        if not path_key or path_key in {".", ".."}:
            return set()
        if path_key in self._static_route_tokens_cache:
            return set(self._static_route_tokens_cache[path_key])

        await self._ensure_index_loaded()
        # Mirror ``_ensure_index_loaded`` success predicate: an unloaded index must not
        # poison the cache (auto-discovery may recover on a later call).
        if not (self._idx.index_bytes or self._idx.assets_by_basename):
            return set()

        generation = self._index_generation
        asset_base = self._idx.static_route_map.get(path_key)
        if asset_base is None and path_key in self._idx.assets_by_basename:
            asset_base = path_key

        tokens: set[str] = set()
        if asset_base is not None:
            asset_ref = self._idx.find_asset_for_basename(asset_base)
            if asset_ref is not None:
                try:
                    code = await self._api.get_bytes(asset_ref.url)
                    if generation != self._index_generation:
                        return set()
                    tokens = self._extract_public_tokens_from_js(code)
                    if generation != self._index_generation:
                        return set()
                except Exception as exc:
                    self._log.debug("Static route asset fetch failed for %s: %s", path_key, exc)
                    # Transient fetch failures must not poison the cache.
                    return set()

        # Generation mismatches return above; reaching here means this index is still current.
        self._static_route_tokens_cache[path_key] = tokens
        return set(tokens)

    async def fetch_alarm_name_source(self) -> str | bytes | None:
        """Return SPA Alarms chunk bytes/text for ``AlarmName`` enum parsing, or ``None``.

        Post-1.04 indexes often register **two** ``Alarms-<hash>.js`` assets: a shared
        module that owns the ``AlarmName`` enum, and a Vue page chunk that only imports
        it. ``find_asset_for_basename`` returns the last hash (usually the page), which
        parses to an empty map — so this method fetches every ``Alarms`` / ``alarms``
        candidate and returns the payload with the richest ``parse_alarm_name_enum`` hit.
        """
        await self._ensure_index_loaded()
        if not (self._idx.index_bytes or self._idx.assets_by_basename):
            return None

        candidates: list[AssetRef] = []
        seen_urls: set[str] = set()

        def _add_refs(refs: list[AssetRef] | None) -> None:
            if not refs:
                return
            for ref in refs:
                if ref.url in seen_urls:
                    continue
                seen_urls.add(ref.url)
                candidates.append(ref)

        for basename in ("Alarms", "alarms"):
            _add_refs(self._idx.assets_by_basename.get(basename))
        if not candidates:
            for basename, refs in self._idx.assets_by_basename.items():
                if not isinstance(basename, str) or not basename.casefold().startswith("alarms"):
                    continue
                _add_refs(refs)
        if not candidates:
            return None

        # Local import: catalog is the heavy module; keep alarm_names out of import cycles.
        from .alarm_names import parse_alarm_name_enum

        best: str | bytes | None = None
        best_score = 0
        for asset in candidates:
            try:
                payload: Any = await self._api.get_bytes(asset.url)
            except Exception as exc:
                self._log.debug("Failed to fetch Alarms chunk from %s: %s", asset.url, exc)
                continue
            if isinstance(payload, bytearray):
                payload = bytes(payload)
            if not isinstance(payload, (bytes, str)):
                continue
            score = len(parse_alarm_name_enum(payload))
            if score > best_score:
                best = payload
                best_score = score
        return best

    # ---------- MENU ----------

    @staticmethod
    def devices_fingerprint(devices: Sequence[DeviceMenuRef] | None) -> str:
        """Stable fingerprint for menu cache keys (#438)."""
        if not devices:
            return ""
        return "|".join(ref.fingerprint() for ref in devices)

    async def get_module_menu(
        self,
        device_menu: int,
        permissions: Iterable[str] | None = None,
        *,
        debug_mode: bool = False,
        devices: Sequence[DeviceMenuRef] | None = None,
    ) -> MenuResult:
        """Get processed menu using the unified MenuManager pipeline.

        When *devices* is supplied, prefers device-specific REST menus (then the
        SPA default ``0/0/0.0.0`` and ``extends`` chunks) before legacy JS
        ``deviceMenu`` assets (#438). Without *devices*, keeps the historical
        JS-then-REST fallback.
        """
        fp = self.devices_fingerprint(devices)
        needs_load = device_menu not in self._menu_manager.list_cached_menus() or self._menu_devices_fp.get(device_menu) != fp
        if needs_load:
            await self._load_and_cache_menu(device_menu, devices=devices)
            self._menu_devices_fp[device_menu] = fp

        perm_set = None if permissions is None else set(permissions)
        return self._menu_manager.get_menu(device_menu=device_menu, permissions=perm_set, debug_mode=debug_mode)

    def _generic_menu_asset(self) -> AssetRef | None:
        """Return a legacy generic menu chunk when ``menu_map`` has no entry.

        Pre-1.04 indexes shipped ``module.menu-<hash>.js`` (preferred) or
        ``0-<hash>.js``. Post-1.04 ``menu-0-*.js`` chunks are i18n, not routes —
        do not select them here; callers fall through to the REST default menu.
        """
        for basename in ("module.menu", "0"):
            asset = self._idx.find_asset_for_basename(basename)
            if asset is not None:
                return asset
        return None

    def resolve_extended_menu_asset(self, ref: str) -> AssetRef | None:
        """Resolve an SPA ``extends`` ref (``N:variant`` / ``N/variant``) to a Vite chunk."""
        parsed = _parse_extends_ref(ref)
        if parsed is None:
            return None
        menu_id, variant = parsed
        stem = self._idx.menu_variant_map.get((menu_id, variant))
        if stem is None:
            return None
        return self._idx.find_asset_for_full_name(stem)

    async def _fetch_devices_menu_payload(
        self,
        manuf_code: int,
        dev_code: int,
        fw: str = "0.0.0",
    ) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
        """Fetch one SPA devices menu; return ``(routes, meta, url_hint)``.

        ``meta`` carries ``priority``, ``standalone``, and ``extends`` when present.
        """
        get_menu = getattr(self._api, "get_devices_menu", None)
        if not callable(get_menu):
            return [], {}, None
        url_hint = f"manufacturers/{manuf_code}/devices/{dev_code}/menu/{fw}"
        try:
            payload = await get_menu(manuf_code, dev_code, fw)
        except Exception as exc:
            self._log.warning("Devices menu fetch failed (%s): %s", url_hint, exc)
            return [], {}, None
        if not isinstance(payload, Mapping):
            self._log.warning("Devices menu returned non-object payload (%s): %s", url_hint, type(payload).__name__)
            return [], {}, None
        raw = payload.get("deviceMenu")
        if not isinstance(raw, list):
            self._log.warning("Devices menu missing deviceMenu list (%s)", url_hint)
            return [], {}, None
        routes = [self._attach_parameters_tokens(item) for item in raw if isinstance(item, dict)]
        priority_raw = payload.get("priority", 0)
        try:
            priority = int(priority_raw) if priority_raw is not None else 0
        except (TypeError, ValueError):
            priority = 0
        extends_raw = payload.get("extends")
        extends = [str(item) for item in extends_raw] if isinstance(extends_raw, list) else []
        meta = {
            "priority": priority,
            "standalone": bool(payload.get("standalone")),
            "extends": extends,
        }
        return routes, meta, url_hint

    async def _fetch_server_default_menu_routes(self) -> tuple[list[dict[str, Any]], str | None]:
        """Load the SPA default menu from ``manufacturers/0/devices/0/menu/0.0.0``.

        BragerOne 1.04.05+ dropped ``deviceMenu/0`` and ``module.menu`` assets. The
        web app falls back to this REST endpoint for non-standalone modules when a
        device-specific menu is missing (typical ``deviceMenu=0`` internet modules).
        """
        routes, _meta, url_hint = await self._fetch_devices_menu_payload(0, 0, "0.0.0")
        return routes, url_hint

    @staticmethod
    def _param_entry_key(entry: Any) -> str | None:
        """Stable identity for a parameter list entry (token / parameter field)."""
        if isinstance(entry, Mapping):
            for key in ("token", "parameter", "param"):
                value = entry.get(key)
                if isinstance(value, str) and value:
                    return value
            return None
        if isinstance(entry, str) and entry:
            return entry
        return None

    @classmethod
    def _merge_parameter_section_lists(cls, preferred: Any, fallback: Any) -> list[Any]:
        """Union parameter lists; *preferred* wins on duplicate tokens."""
        preferred_list = list(preferred) if isinstance(preferred, list) else []
        fallback_list = list(fallback) if isinstance(fallback, list) else []
        out: list[Any] = []
        seen: set[str] = set()
        for entry in preferred_list:
            key = cls._param_entry_key(entry)
            if key is not None:
                seen.add(key)
            out.append(entry)
        for entry in fallback_list:
            key = cls._param_entry_key(entry)
            if key is not None and key in seen:
                continue
            if key is not None:
                seen.add(key)
            out.append(entry)
        return out

    @classmethod
    def _merge_parameters_maps(cls, preferred: Any, fallback: Any) -> dict[str, Any] | Any:
        """Merge read/write/status/special maps; keep non-section keys from *preferred*."""
        if not isinstance(preferred, Mapping) and not isinstance(fallback, Mapping):
            return preferred if preferred is not None else fallback
        pref = dict(preferred) if isinstance(preferred, Mapping) else {}
        fall = dict(fallback) if isinstance(fallback, Mapping) else {}
        out = dict(fall)
        out.update(pref)
        for section in ("read", "write", "status", "special"):
            if section in pref or section in fall:
                out[section] = cls._merge_parameter_section_lists(pref.get(section), fall.get(section))
        return out

    @classmethod
    def _merge_route_dicts(cls, preferred: Mapping[str, Any], fallback: Mapping[str, Any]) -> dict[str, Any]:
        """Deep-merge two routes: *preferred* wins scalars; parameters/children union by path (#438)."""
        out = dict(fallback)
        out.update(preferred)

        pref_meta = preferred.get("meta")
        fall_meta = fallback.get("meta")
        if isinstance(pref_meta, Mapping) or isinstance(fall_meta, Mapping):
            meta_out = dict(fall_meta) if isinstance(fall_meta, Mapping) else {}
            if isinstance(pref_meta, Mapping):
                meta_out.update(pref_meta)
            pref_params = pref_meta.get("parameters") if isinstance(pref_meta, Mapping) else None
            fall_params = fall_meta.get("parameters") if isinstance(fall_meta, Mapping) else None
            if pref_params is not None or fall_params is not None:
                meta_out["parameters"] = cls._merge_parameters_maps(pref_params, fall_params)
            out["meta"] = meta_out

        if "parameters" in preferred or "parameters" in fallback:
            out["parameters"] = cls._merge_parameters_maps(preferred.get("parameters"), fallback.get("parameters"))

        pref_children = preferred.get("children")
        fall_children = fallback.get("children")
        if isinstance(pref_children, list) or isinstance(fall_children, list):
            child_layers: list[tuple[list[dict[str, Any]], int]] = []
            if isinstance(fall_children, list):
                child_layers.append(([c for c in fall_children if isinstance(c, dict)], 0))
            if isinstance(pref_children, list):
                child_layers.append(([c for c in pref_children if isinstance(c, dict)], 1))
            out["children"] = cls._merge_menu_route_layers(child_layers)
        return out

    @classmethod
    def _merge_menu_route_layers(
        cls,
        layers: Sequence[tuple[list[dict[str, Any]], int]],
    ) -> list[dict[str, Any]]:
        """Merge route lists by ``path``; higher *priority* wins scalars, parameters union (#438).

        Layers are applied in ascending priority so a mid-priority extension can
        override tokens inherited from a lower-priority default even when a
        high-priority device route was fetched earlier. Equal priorities keep
        the earlier original layer (device before default) via a stable
        ``-index`` secondary key.
        """
        by_path: dict[str, tuple[int, dict[str, Any]]] = {}
        order: list[str] = []
        # Ascending priority; among ties, earlier fetch index is applied last.
        ordered = sorted(enumerate(layers), key=lambda item: (item[1][1], -item[0]))
        for _index, (routes, priority) in ordered:
            for route in routes:
                path = route.get("path")
                if not isinstance(path, str) or not path:
                    continue
                existing = by_path.get(path)
                if existing is None:
                    by_path[path] = (priority, dict(route))
                    order.append(path)
                    continue
                prev_priority, prev_route = existing
                # Incoming layer is preferred after ascending sort.
                by_path[path] = (max(priority, prev_priority), cls._merge_route_dicts(route, prev_route))
        return [by_path[path][1] for path in order if path in by_path]

    async def _load_extended_menu_routes(self, extends: Sequence[str]) -> list[tuple[list[dict[str, Any]], int]]:
        """SPA ``loadExtendedMenu``: fetch Vite chunks listed in REST ``extends``."""
        layers: list[tuple[list[dict[str, Any]], int]] = []
        seen: set[str] = set()
        for raw_ref in extends:
            ref = str(raw_ref).strip()
            if not ref or ref in seen:
                continue
            seen.add(ref)
            asset = self.resolve_extended_menu_asset(ref)
            if asset is None:
                self._log.warning("Extended menu ref %r not found in index; skipping", ref)
                continue
            try:
                code = await self._api.get_bytes(asset.url)
            except Exception as exc:
                self._log.warning("Extended menu fetch failed (%s): %s", asset.url, exc)
                continue
            routes, priority = await asyncio.to_thread(self._parse_menu_export, code)
            if routes:
                layers.append((routes, priority))
                self._log.info(
                    "Loaded extended menu %s (priority=%d, %d routes) from %s",
                    ref,
                    priority,
                    len(routes),
                    asset.url,
                )
        return layers

    async def _load_rest_menu_layers(
        self,
        device_menu: int,
        devices: Sequence[DeviceMenuRef] | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Device-specific REST menus, then default, then extends (#438)."""
        layers: list[tuple[list[dict[str, Any]], int]] = []
        extend_refs: list[str] = []
        asset_url: str | None = None
        standalone_won = False

        if devices:
            for ref in devices:
                routes, meta, url_hint = await self._fetch_devices_menu_payload(ref.manuf_code, ref.dev_code, ref.fw)
                if not routes and not meta:
                    continue
                priority = int(meta.get("priority", 0) or 0)
                if routes:
                    layers.append((routes, priority))
                    asset_url = url_hint or asset_url
                extend_refs.extend(str(item) for item in meta.get("extends", []) if item)
                if meta.get("standalone"):
                    # Suppress only the generic default — keep loading remaining devices (#438).
                    standalone_won = True
                    self._log.info(
                        "Standalone devices menu won for device_menu=%d (%s)",
                        device_menu,
                        url_hint,
                    )

        if not standalone_won:
            self._log.info(
                "Fetching SPA default REST menu for device_menu=%d (devices=%s)",
                device_menu,
                self.devices_fingerprint(devices) or "none",
            )
            routes, meta, url_hint = await self._fetch_devices_menu_payload(0, 0, "0.0.0")
            if routes:
                layers.append((routes, int(meta.get("priority", 0) or 0)))
                asset_url = url_hint or asset_url
            extend_refs.extend(str(item) for item in meta.get("extends", []) if item)

        if extend_refs:
            layers.extend(await self._load_extended_menu_routes(extend_refs))

        return self._merge_menu_route_layers(layers), asset_url

    async def _load_and_cache_menu(
        self,
        device_menu: int,
        *,
        devices: Sequence[DeviceMenuRef] | None = None,
    ) -> None:
        """Load raw menu data and cache it in MenuManager."""
        # Auto-load index if not loaded yet
        if not self._idx.menu_map and not self._idx.assets_by_basename and not self._idx.menu_variant_map:
            await self._auto_discover_and_load_index()

        raw_routes: list[dict[str, Any]] = []
        asset_url: str | None = None

        # When Module.devices refs are supplied, prefer SPA REST construction first (#438).
        if devices:
            raw_routes, rest_url = await self._load_rest_menu_layers(device_menu, devices)
            asset_url = rest_url

        if not raw_routes:
            # Legacy JS deviceMenu chunk / generic module.menu (pre-1.04 or no devices=).
            menu_name = self._idx.menu_map.get(device_menu)
            asset: AssetRef | None = None
            if menu_name:
                asset = self._idx.find_asset_for_full_name(menu_name)
            if asset is None:
                self._log.debug(
                    "No menu mapping found for device_menu=%d; trying legacy generic menu assets (module.menu, then basename 0)",
                    device_menu,
                )
                asset = self._generic_menu_asset()

            if asset is not None:
                self._log.info("Loading menu asset: %s", asset.url)
                code = await self._api.get_bytes(asset.url)
                raw_routes = await asyncio.to_thread(self._parse_menu_routes, code)
                asset_url = asset.url

        if not raw_routes and not devices:
            raw_routes, rest_url = await self._load_rest_menu_layers(device_menu, devices)
            asset_url = rest_url or asset_url

        if not raw_routes:
            self._log.warning("No menu routes found for device_menu=%d", device_menu)

        self._menu_manager.store_raw_menu(device_menu=device_menu, routes=raw_routes, asset_url=asset_url)
        self._log.info("Cached raw menu for device_menu=%d: %d routes", device_menu, len(raw_routes))

    def get_raw_menu(self, device_menu: int) -> RawMenuData:
        """Get raw unprocessed menu data for debugging."""
        return self._menu_manager.get_raw_menu(device_menu)

    def get_menu_debug_info(self, device_menu: int) -> dict[str, Any]:
        """Get debug information about cached menu."""
        return self._menu_manager.get_debug_info(device_menu)

    def _parse_menu_export(self, code: bytes) -> tuple[list[dict[str, Any]], int]:
        """Parse a menu Vite/REST export into ``(routes, priority)`` (pure-Python path).

        Extended chunks often wrap routes as ``{priority, deviceMenu: [...]}``;
        priority defaults to ``0`` when absent or non-int (#438).
        """
        export_obj = extract_root_export(code)
        if export_obj is None:
            return [], 0

        priority = 0
        if isinstance(export_obj, Mapping):
            priority_raw = export_obj.get("priority", 0)
            try:
                priority = int(priority_raw) if priority_raw is not None else 0
            except (TypeError, ValueError):
                priority = 0

        def extract_routes(value: Any, depth: int = 0) -> list[dict[str, Any]]:
            if depth > 5:
                return []

            if isinstance(value, list):
                candidates = [item for item in value if isinstance(item, dict)]
                meaningful = [item for item in candidates if any(key in item for key in ("path", "name", "children", "meta"))]
                return meaningful or []

            if isinstance(value, dict):
                for key in ("routes", "deviceMenu", "menu", "items"):
                    if key in value:
                        extracted = extract_routes(value[key], depth + 1)
                        if extracted:
                            return extracted
                for nested in value.values():
                    extracted = extract_routes(nested, depth + 1)
                    if extracted:
                        return extracted
            return []

        raw_routes = extract_routes(export_obj)
        return [self._attach_parameters_tokens(route) for route in raw_routes], priority

    def _parse_menu_routes(self, code: bytes) -> list[dict[str, Any]]:
        """Returning list of root-routes (1:1 with export in module.menu-*.js)."""
        routes, _priority = self._parse_menu_export(code)
        return routes

    # Build output may rename helper functions; do not rely on single-letter identifiers.
    # Two-arg ``foo(…, 'TOKEN')`` plus single-arg obfuscated ``_0xabc('TOKEN')``.
    PARAM_CALL_RE = re.compile(
        r"""(?:"""
        r"""\b[A-Za-z_$][\w$]*\([^,]*?,\s*(['"])(?P<tok>[^'"]+)\1\)"""
        r"""|"""
        r"""(?<![A-Za-z0-9_$])_0x[0-9a-fA-F]*\(\s*(['"])(?P<tok_single>[A-Z][A-Z0-9_]*)\3\s*\)"""
        r""")"""
    )

    @classmethod
    def _token_from_param_call(cls, text: str) -> str | None:
        """Extract a token from two-arg helper text or ``_0x…('TOKEN')`` leftovers."""
        match = cls.PARAM_CALL_RE.search(text)
        if match is None:
            return None
        return match.group("tok") or match.group("tok_single")

    def _attach_parameters_tokens(self, node: dict[str, Any]) -> dict[str, Any]:
        """Attach parameter tokens to a node by processing its parameters section.

        After AST to dict conversion, items in parameters.* sections can be:
        - Literal strings (already valid tokens)
        - Call expressions as raw strings, e.g., "E(A.WRITE,'URUCHOMIENIE_KOTLA')"
            from which we extract the token using regex

        This method processes all parameter sections (read, write, status, special),
        extracts tokens from various formats, and normalizes them into a consistent
        dict structure with a "token" key. It recursively processes child nodes.

        Args:
                node: A dictionary representing a catalog node that may contain a
                        "parameters" section with read/write/status/special subsections,
                        and optionally a "children" list.

        Returns:
                A new dictionary with the same structure as the input node, but with
                parameters normalized to dicts containing "token" keys, and children
                recursively processed.
        """
        out = dict(node)
        params = out.get("parameters")
        if isinstance(params, dict):
            out["parameters"] = self._normalize_parameter_sections(params)
        meta = out.get("meta")
        if isinstance(meta, dict):
            meta_out = dict(meta)
            meta_params = meta_out.get("parameters")
            if isinstance(meta_params, dict):
                meta_out["parameters"] = self._normalize_parameter_sections(meta_params)
            out["meta"] = meta_out
        # recursion for children
        ch = out.get("children")
        if isinstance(ch, list):
            out["children"] = [self._attach_parameters_tokens(c) if isinstance(c, dict) else c for c in ch]
        elif ch is not None:
            # Fix: If children exists but is not a list (e.g., string reference like 'wA'),
            # convert to empty list to prevent MenuManager errors
            self._log.debug(f"Converting non-list children to empty list: {type(ch)} {ch}")
            out["children"] = []
        return out

    def _parameter_section_items(self, items: Any) -> list[Any]:
        """Coerce a parameters.read/write/status/special value to a list of entries.

        Leftover ``array['map'](…)`` source text must not be iterated as characters.
        """
        if isinstance(items, list):
            return items
        if isinstance(items, str):
            if "['map']" in items or '["map"]' in items:
                head = items.split("['map']", 1)[0].split('["map"]', 1)[0]
                return [{"parameter": token} for token in _LEFTOVER_QUOTED_TOKEN_RE.findall(head)]
            return []
        return []

    def _normalize_parameter_sections(self, params: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """Normalize read/write/status/special entries to ``{token, parameter}`` dicts."""
        newp: dict[str, list[dict[str, Any]]] = {}
        for sec in ("read", "write", "status", "special"):
            items = self._parameter_section_items(params.get(sec, []) or [])
            norm: list[dict[str, Any]] = []
            for it in items:
                if isinstance(it, str):
                    original = it.strip()
                    tok = self._token_from_param_call(original)
                    if tok:
                        norm.append({"token": tok, "parameter": original})
                    else:
                        scrubbed = _token_from_obfuscated_call_text(original)
                        norm.append({"token": scrubbed or original, "parameter": original})
                elif isinstance(it, dict):
                    entry = dict(it)
                    param_value = entry.get("parameter")
                    existing_token = entry.get("token")
                    if isinstance(existing_token, str) and existing_token:
                        scrubbed_existing = _token_from_obfuscated_call_text(existing_token)
                        if scrubbed_existing is not None:
                            entry["token"] = scrubbed_existing
                    if isinstance(param_value, str):
                        tok = self._token_from_param_call(param_value)
                        if tok and "token" not in entry:
                            entry["token"] = tok
                        elif "token" not in entry:
                            scrubbed = _token_from_obfuscated_call_text(param_value)
                            entry["token"] = scrubbed or param_value.strip()
                    elif "token" in entry:
                        token_val = str(entry["token"])
                        entry.setdefault("parameter", token_val)
                    else:
                        fallback_text = str(it)
                        tok = self._token_from_param_call(fallback_text)
                        if tok:
                            entry["token"] = tok
                            entry.setdefault("parameter", fallback_text)
                    if "token" in entry:
                        entry.setdefault("parameter", str(entry["token"]) or "")
                    norm.append(entry)
                else:
                    s = str(it)
                    tok = self._token_from_param_call(s)
                    if tok:
                        norm.append({"token": tok, "parameter": s})
                    elif s:
                        scrubbed = _token_from_obfuscated_call_text(s)
                        norm.append({"token": scrubbed or s, "parameter": s})
            newp[sec] = norm
        return newp

    # ---------- PARAM MAPS ----------

    async def get_param_mapping(self, tokens: Iterable[str]) -> dict[str, ParamMap]:
        """Retrieve parameter mappings for the given tokens.

        This method attempts to resolve parameter mappings for each provided token through
        a two-stage resolution process:

        1. First, it searches for a dedicated asset file named ``BASENAME-<hash>.js`` where
           BASENAME exactly matches the token.
        2. If no asset is found, and there is exactly one unresolved token with exactly
           one inline parameter candidate in the index, it attempts to use the inline
           parameter map from the ``index-*.js`` file as a fallback.
        3. Any tokens that cannot be resolved through either method are omitted from
           the results.

        Args:
             tokens: An iterable of token strings to resolve into parameter mappings.

        Returns:
             A dictionary mapping successfully resolved token strings to their
             corresponding ParamMap objects. Only tokens that were successfully
             resolved are included in the returned dictionary.

        Note:
             The method performs asset fetching concurrently using asyncio.gather for
             improved performance. Failed fetches are logged but do not raise exceptions.
        """
        t0_total = time.perf_counter()
        uniq_tokens = list(dict.fromkeys(str(t) for t in tokens if t))

        if not self._idx.assets_by_basename:
            await self._ensure_index_loaded()

        # 1) file assets
        file_jobs: list[tuple[str, AssetRef]] = []
        unresolved: list[str] = []
        for tok in uniq_tokens:
            a = self._idx.find_asset_for_basename(tok)
            if a:
                file_jobs.append((tok, a))
            else:
                unresolved.append(tok)

        results: dict[str, ParamMap] = {}
        source_by_token: dict[str, str] = {}
        telemetry = {
            "token_count": len(uniq_tokens),
            "assets_queued": len(file_jobs),
            "assets_ok": 0,
            "assets_missing_parse": 0,
            "assets_failed": 0,
            "index_token_map_hits": 0,
            "index_chunk_hits": 0,
            "index_full_hits": 0,
            "index_ast_token_hits": 0,
            "unresolved": 0,
            "ms_assets": 0.0,
            "ms_index_fallback": 0.0,
        }

        async def fetch_and_parse(tok: str, a: AssetRef) -> tuple[str, ParamMap | None, str | None]:
            try:
                async with self._asset_sema:
                    code = await self._api.get_bytes(a.url)
                pm = await asyncio.to_thread(self._parse_param_map_from_js, code, tok, f"asset:{a.url}")
                if pm:
                    return tok, pm, None
                self._log.debug("PARAM MAP not found in asset (export not object?): %s", a.url)
                return tok, None, None
            except Exception as e:
                self._log.warning("Param asset fetch failed %s: %s", a.url, e)
                return tok, None, str(e)

        t_assets = time.perf_counter()
        asset_rows = await asyncio.gather(*(fetch_and_parse(tok, a) for tok, a in file_jobs), return_exceptions=False)
        telemetry["ms_assets"] = (time.perf_counter() - t_assets) * 1000.0

        for tok, pm, err in asset_rows:
            if pm is not None:
                results[tok] = pm
                source_by_token[tok] = "asset"
                telemetry["assets_ok"] += 1
            elif err is not None:
                telemetry["assets_failed"] += 1
                unresolved.append(tok)
            else:
                telemetry["assets_missing_parse"] += 1
                # Dedicated asset existed but did not yield a ParamMap — still try index.
                unresolved.append(tok)

        # 2) inline/index fallback for unresolved tokens (no asset *or* failed asset parse)
        def _looks_like_param_map(pm: ParamMap | None, token: str) -> bool:
            if pm is None:
                return False
            if pm.group is not None:
                return True
            if pm.units is not None:
                return True
            if any(pm.paths.get(name) for name in ("value", "unit", "status", "command", "min", "max")):
                return True
            raw = pm.raw
            if isinstance(raw, Mapping):
                if any(name in raw for name in ("name", "group", "pool", "use", "value", "unit", "units", "componentType")):
                    return True
                nested = raw.get(token)
                if isinstance(nested, Mapping):
                    return True
            return False

        unresolved_now = [tok for tok in dict.fromkeys(unresolved) if tok not in results]
        if unresolved_now and self._idx.index_bytes:
            t_fallback = time.perf_counter()
            token_raw_maps = await self._get_index_token_raw_maps(self._idx.index_bytes)
            chunk_token_maps: list[tuple[int, dict[str, dict[str, Any]]]] = []
            chunk_root_objects: list[tuple[int, dict[str, Any]]] = []
            full_root_obj = await asyncio.to_thread(self._extract_root_object_from_js, self._idx.index_bytes)
            standard_token_name_re = re.compile(r"^[A-Z][A-Z0-9_]+$")

            for idx, (start, end) in enumerate(self._idx.inline_param_candidates):
                if start < 0 or end <= start:
                    continue
                chunk = self._idx.index_bytes[start:end]
                try:
                    parsed_chunk = await asyncio.to_thread(self._parse_index_token_raw_maps, chunk)
                except Exception:
                    parsed_chunk = {}
                if parsed_chunk:
                    chunk_token_maps.append((idx, parsed_chunk))

                root_obj = await asyncio.to_thread(self._extract_root_object_from_js, chunk)
                if isinstance(root_obj, dict):
                    chunk_root_objects.append((idx, root_obj))

            for tok in unresolved_now:
                resolved_pm: ParamMap | None = None

                raw_map = token_raw_maps.get(tok)
                if isinstance(raw_map, Mapping):
                    pm_cached = self._build_param_map_from_obj(dict(raw_map), tok, origin="inline:index-token")
                    if _looks_like_param_map(pm_cached, tok):
                        resolved_pm = pm_cached
                        source_by_token[tok] = "index-token-map"
                        telemetry["index_token_map_hits"] += 1

                if resolved_pm is None:
                    for idx, token_map in chunk_token_maps:
                        raw_map_chunk = token_map.get(tok)
                        if not isinstance(raw_map_chunk, Mapping):
                            continue
                        origin = "inline:index" if idx == 0 else f"inline:index[{idx}]"
                        pm_chunk = self._build_param_map_from_obj(dict(raw_map_chunk), tok, origin=origin)
                        if _looks_like_param_map(pm_chunk, tok):
                            resolved_pm = pm_chunk
                            source_by_token[tok] = "index-inline-chunk"
                            telemetry["index_chunk_hits"] += 1
                            break

                if resolved_pm is None:
                    for idx, root_obj in chunk_root_objects:
                        origin = "inline:index" if idx == 0 else f"inline:index[{idx}]"
                        pm_chunk_obj = self._build_param_map_from_obj(dict(root_obj), tok, origin=origin)
                        if _looks_like_param_map(pm_chunk_obj, tok):
                            resolved_pm = pm_chunk_obj
                            source_by_token[tok] = "index-inline-chunk"
                            telemetry["index_chunk_hits"] += 1
                            break

                if resolved_pm is None:
                    pm_full = None
                    if isinstance(full_root_obj, dict):
                        pm_full = self._build_param_map_from_obj(dict(full_root_obj), tok, origin="inline:index-full")
                    if _looks_like_param_map(pm_full, tok):
                        resolved_pm = pm_full
                        source_by_token[tok] = "index-full"
                        telemetry["index_full_hits"] += 1

                # token_raw_maps already covers the common token namespace; keep this expensive
                # fallback only for non-standard keys to preserve compatibility.
                if resolved_pm is None and not standard_token_name_re.match(tok):
                    pm_token = self._parse_param_map_from_index_token(
                        self._idx.index_bytes,
                        tok,
                        origin="inline:index-token",
                    )
                    if _looks_like_param_map(pm_token, tok):
                        resolved_pm = pm_token
                        source_by_token[tok] = "index-token-ast"
                        telemetry["index_ast_token_hits"] += 1

                if resolved_pm is not None:
                    results[tok] = resolved_pm
                else:
                    self._log.debug("Index fallback didn't parse expected param map for %s", tok)
                    source_by_token[tok] = "unresolved"
                    telemetry["unresolved"] += 1

            telemetry["ms_index_fallback"] = (time.perf_counter() - t_fallback) * 1000.0

        for tok in uniq_tokens:
            source_by_token.setdefault(tok, "unresolved")
        telemetry["unresolved"] = sum(1 for src in source_by_token.values() if src == "unresolved")

        total_ms = (time.perf_counter() - t0_total) * 1000.0

        self._log.info(
            "PARAM MAPS: tokens=%d resolved=%d unresolved=%d total_ms=%.2f assets_ms=%.2f index_ms=%.2f "
            "src(asset=%d idx-map=%d idx-chunk=%d idx-full=%d idx-ast=%d)",
            len(uniq_tokens),
            len(results),
            telemetry["unresolved"],
            total_ms,
            telemetry["ms_assets"],
            telemetry["ms_index_fallback"],
            telemetry["assets_ok"],
            telemetry["index_token_map_hits"],
            telemetry["index_chunk_hits"],
            telemetry["index_full_hits"],
            telemetry["index_ast_token_hits"],
        )

        self._log.debug(
            "PARAM MAPS detail: assets_queued=%d assets_failed=%d assets_missing_parse=%d",
            telemetry["assets_queued"],
            telemetry["assets_failed"],
            telemetry["assets_missing_parse"],
        )

        unresolved_preview = [tok for tok, src in source_by_token.items() if src == "unresolved"][:20]
        if unresolved_preview:
            self._log.debug("PARAM MAPS unresolved preview(%d): %s", len(unresolved_preview), unresolved_preview)

        return results

    @staticmethod
    def _index_signature(code: bytes) -> tuple[int, bytes, bytes]:
        head = code[:64]
        tail = code[-64:] if len(code) > 64 else code
        return (len(code), head, tail)

    async def _get_index_token_raw_maps(self, code: bytes) -> dict[str, dict[str, Any]]:
        sig = self._index_signature(code)

        cached = self._index_token_raw_maps
        cached_sig = self._index_token_raw_maps_sig
        if isinstance(cached, dict) and cached_sig == sig:
            return cached

        async with self._index_token_raw_maps_lock:
            cached2 = self._index_token_raw_maps
            cached_sig2 = self._index_token_raw_maps_sig
            if isinstance(cached2, dict) and cached_sig2 == sig:
                return cached2

            parsed = await asyncio.to_thread(self._parse_index_token_raw_maps, code)
            self._index_token_raw_maps = parsed
            self._index_token_raw_maps_sig = sig
            return parsed

    def _parse_index_token_raw_maps(self, code: bytes) -> dict[str, dict[str, Any]]:
        """Collect PARAM_*/STATUS_* object maps embedded in index JS (pure path)."""
        out: dict[str, dict[str, Any]] = {}
        token_name_re = re.compile(r"^[A-Z][A-Z0-9_]+$")

        def _ingest(candidate: Mapping[str, Any]) -> None:
            for key_text, value in candidate.items():
                if not isinstance(key_text, str) or not token_name_re.match(key_text):
                    continue
                if isinstance(value, Mapping):
                    out[key_text] = dict(value)

        try:
            for candidate in iter_top_level_object_assignments(code):
                _ingest(candidate)
            root = extract_root_object(code)
            if isinstance(root, Mapping):
                _ingest(root)
        except Exception:
            return out
        return out

    def _parse_param_map_from_index_token(self, code: bytes, key: str, origin: str) -> ParamMap | None:
        """Parse a single token mapping from index JS by key lookup (pure path)."""
        try:
            maps = self._parse_index_token_raw_maps(code)
        except Exception:
            return None
        resolved_value = maps.get(key)
        if isinstance(resolved_value, Mapping):
            return self._build_param_map_from_obj(dict(resolved_value), key, origin=origin)
        return None

    def _build_param_map_from_obj(self, obj: dict[str, Any], key: str, origin: str) -> ParamMap | None:
        candidate_for_key = obj.get(key)
        if isinstance(candidate_for_key, Mapping):
            obj = dict(candidate_for_key)

        group = obj.get("group") or obj.get("pool")

        def _ensure_mapping_list(value: Any) -> list[dict[str, Any]]:
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, Mapping)]
            if isinstance(value, Mapping):
                return [dict(value)]
            return []

        def _normalize_status(value: Any) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
            conditions: dict[str, list[dict[str, Any]]] = {}
            flat: list[dict[str, Any]] = []
            if isinstance(value, Mapping):
                for raw_key, entries in value.items():
                    # Resolve ``ParameterStatus['INVISIBLE']`` / ``_0x…['ENABLED']`` to the
                    # public flag name the SPA stores on ``parameter.status.<flag>``.
                    key_str = _normalize_identifier(raw_key) or str(raw_key)
                    normalized_entries = _ensure_mapping_list(entries)
                    if not normalized_entries:
                        continue
                    bucket = conditions.setdefault(key_str, [])
                    bucket.extend(normalized_entries)
                    for entry in normalized_entries:
                        enriched = dict(entry)
                        enriched.setdefault("condition", key_str)
                        flat.append(enriched)
            elif isinstance(value, list):
                normalized_entries = _ensure_mapping_list(value)
                if normalized_entries:
                    conditions["default"] = normalized_entries
                    flat.extend(normalized_entries)
            return conditions, flat

        def _normalize_literal(value: Any) -> Any:
            if isinstance(value, str):
                trimmed = value.strip()
                if trimmed in _JS_UNDEFINED_LITERALS:
                    return None
                if trimmed in _JS_BOOL_LITERALS:
                    return _JS_BOOL_LITERALS[trimmed]
            return value

        def _normalize_identifier(value: Any) -> str | None:
            if not isinstance(value, str):
                return None
            cleaned = value.strip()
            if not cleaned:
                return None
            public = js_public_member_name(cleaned)
            if public is not None:
                return public
            if cleaned.startswith("[") and cleaned.endswith("]") and len(cleaned) > 2:
                cleaned = cleaned[1:-1]
            parts = cleaned.split(".", 1)
            # Keep in sync with ParamResolver._clean_symbolic_tag short prefixes.
            if len(parts) == 2 and parts[0].lower() in {"a", "e", "n", "o", "t", "u", "s", "r", "p", "m"}:
                cleaned = parts[1]
            return cleaned

        def _normalize_condition_entries(entries: Any) -> list[dict[str, Any]]:
            conditions_list: list[dict[str, Any]] = []
            if not isinstance(entries, list):
                return conditions_list
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                condition = {
                    "operation": _normalize_identifier(entry.get("operation")),
                    "expected": _normalize_literal(entry.get("expected")),
                    "targets": _ensure_mapping_list(entry.get("value")),
                }
                conditions_list.append(condition)
            return conditions_list

        def _normalize_command_action(raw_action: Any) -> dict[str, Any] | None:
            if not isinstance(raw_action, Mapping):
                return None
            command = _normalize_identifier(raw_action.get("command"))
            value = _normalize_literal(raw_action.get("value"))
            action: dict[str, Any] = {}
            if command:
                action["command"] = command
            if value is not None:
                action["value"] = value
            return action if action else None

        def _normalize_command_branches(blocks: Any, logic_key: str) -> list[dict[str, Any]]:
            normalized: list[dict[str, Any]] = []
            if not isinstance(blocks, list):
                return normalized
            for entry in blocks:
                if not isinstance(entry, Mapping):
                    continue
                branch_key = None
                for candidate in ("if", "elseif", "else"):
                    if candidate in entry:
                        branch_key = candidate
                        break
                if branch_key is None:
                    branch_key = "if"
                conditions = _normalize_condition_entries(entry.get(branch_key)) if branch_key != "else" else []
                action_source = entry.get("then") if branch_key != "else" else entry.get("else")
                action = _normalize_command_action(action_source)
                if action is None:
                    continue
                normalized_entry: dict[str, Any] = {
                    "logic": logic_key,
                    "kind": branch_key,
                    "conditions": conditions,
                }
                normalized_entry.update(action)
                normalized.append(normalized_entry)
            return normalized

        value_paths = _ensure_mapping_list(obj.get("value"))
        unit_field = obj.get("unit")
        unit_paths = _ensure_mapping_list(unit_field)
        command_paths = _ensure_mapping_list(obj.get("command"))
        min_paths = _ensure_mapping_list(obj.get("minValue") or obj.get("min"))
        max_paths = _ensure_mapping_list(obj.get("maxValue") or obj.get("max"))
        status_conditions, status_flat = _normalize_status(obj.get("status"))

        command_rules: list[dict[str, Any]] = []
        for logic_key in ("any", "all", "when"):
            command_rules.extend(_normalize_command_branches(obj.get(logic_key), logic_key))

        use = obj.get("use")
        if isinstance(use, Mapping):
            value_paths = value_paths or _ensure_mapping_list(use.get("v"))
            unit_paths = unit_paths or _ensure_mapping_list(use.get("u"))
            if not status_flat:
                _, status_flat = _normalize_status(use.get("s"))
            min_paths = min_paths or _ensure_mapping_list(use.get("n"))
            max_paths = max_paths or _ensure_mapping_list(use.get("x"))

        paths = {
            "value": value_paths,
            "unit": unit_paths,
            "status": status_flat,
            "command": command_paths,
            "min": min_paths,
            "max": max_paths,
        }
        component = _normalize_identifier(obj.get("componentType"))
        if component is None:
            component = _normalize_identifier(obj.get("useComponent"))
        units_raw: Any = obj.get("units")
        if units_raw is None:
            units_raw = obj.get("unit_name")
        if units_raw is None and isinstance(unit_field, (str, int, float)):
            units_raw = unit_field
        if isinstance(units_raw, str):
            trimmed_units = units_raw.strip()
            public_unit = js_public_member_name(trimmed_units)
            if public_unit is not None:
                units_raw = public_unit
            elif _CATALOG_LIKE_TOKEN_RE.fullmatch(trimmed_units) is not None:
                units_raw = trimmed_units
        limits = None
        for cand in ("limits", "range", "minmax"):
            if cand in obj and isinstance(obj[cand], dict):
                limits = obj[cand]
                break
        status_flags = obj.get("statusFlags") or obj.get("status_bits") or []

        return ParamMap(
            key=key,
            group=group if isinstance(group, str) else None,
            paths=paths,
            component_type=component if isinstance(component, str) else None,
            units=units_raw if isinstance(units_raw, (str, int, float)) else None,
            limits=limits,
            status_flags=status_flags if isinstance(status_flags, list) else [],
            status_conditions=status_conditions or None,
            command_rules=command_rules,
            origin=origin,
            raw=obj,
        )

    def _parse_param_map_from_js(self, code: bytes, key: str, origin: str) -> ParamMap | None:
        """Parse a JavaScript file (or index fragment) and extract a parameter map object.

        This method analyzes JavaScript code to find and parse an exported object that
        appears to be a parameter map. It extracts various fields like group, paths,
        component type, units, limits, and status flags, performing minimal normalization
        on the data structure.

        Args:
            code: The JavaScript source code as bytes to parse.
            key: A string identifier for this parameter map.
            origin: A string indicating the source/origin of this parameter map.

        Returns:
            A ParamMap object containing the parsed and normalized parameter data,
            or None if no valid parameter map could be extracted from the code.

        Note:
            The method performs minimal normalization by checking for alternative field
            names (e.g., 'group' or 'pool', 'use' fields or direct 'value'/'unit'/'status').
            The raw parsed object is preserved in the ParamMap's 'raw' attribute.
        """
        obj = self._extract_root_object_from_js(code)
        if not isinstance(obj, dict):
            return None

        return self._build_param_map_from_obj(obj, key, origin)

    def _extract_root_object_from_js(self, code: bytes) -> dict[str, Any] | None:
        """Extract root exported object from JavaScript bytes (pure-Python path).

        Returns a plain Python dictionary when extraction succeeds, otherwise ``None``.
        """
        return extract_root_object(code)

    # ---------- Permissions helper ----------

    async def list_symbols_for_permissions(
        self,
        device_menu: int,
        permissions: Iterable[str],
        *,
        devices: Sequence[DeviceMenuRef] | None = None,
    ) -> set[str]:
        """List symbols visible for given permissions.

        This is a convenient shortcut that fetches the menu for device_menu and returns
        tokens visible for the provided permissions. The schemas hook remains OFF.

        Args:
            device_menu: The device menu identifier.
            permissions: An iterable of permission strings to check visibility against.
            devices: Optional ``Module.devices`` refs for REST menu construction (#438).

        Returns:
            A set of token strings that are visible for the given permissions.
        """
        menu = await self.get_module_menu(device_menu=device_menu, permissions=permissions, devices=devices)
        return menu.all_tokens()

    # ---------- i18n support ----------

    async def list_language_config(self) -> TranslationConfig | None:
        """Get translation configuration from assets.

        Parses the ``index-*.js`` file to extract language configuration by structural patterns.
        The configuration object contains translations array and defaultTranslation field.
        """
        if not self._idx.index_bytes:
            await self._ensure_index_loaded()
        if not self._idx.index_bytes:
            self._log.warning("No index data available. Call refresh_index() or refresh_index_minimal() first.")
            return None

        try:
            return await asyncio.to_thread(self._parse_language_config_from_js, self._idx.index_bytes)
        except Exception as e:
            self._log.warning("Failed to parse language config from index: %s", e)
            return None

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        """Get i18n mapping for a given language and namespace.

        Parses the index file for dynamic language imports in the format:
        "../../resources/languages/{lang}/{namespace}.json":()=>d(()=>import("./file-hash.js"),[]).then(e=>e.default)

        Then fetches and parses the corresponding asset file.

        Args:
            lang: Language code (e.g., 'en', 'pl').
            namespace: Namespace (e.g., 'parameters', 'units').

        Returns:
            Dictionary with translation mappings, or empty dict if not found.
        """
        lang_norm = str(lang).strip().lower()
        namespace_norm = str(namespace).strip().lower()
        if not lang_norm or not namespace_norm:
            return {}

        cache_key = (lang_norm, namespace_norm)
        cached = self._cache_i18n.get(cache_key)
        if cached is not None:
            return cached

        async with self._i18n_lock:
            cached2 = self._cache_i18n.get(cache_key)
            if cached2 is not None:
                return cached2

            if not self._idx.index_bytes:
                await self._ensure_index_loaded()
            if not self._idx.index_bytes:
                self._log.warning("No index data available for i18n lookup")
                self._cache_i18n[cache_key] = {}
                return {}

            try:
                asset_ref = self._find_i18n_asset(lang_norm, namespace_norm)
                if not asset_ref:
                    self._log.debug("No i18n asset found for %s/%s", lang_norm, namespace_norm)
                    self._cache_i18n[cache_key] = {}
                    return {}

                code = await self._api.get_bytes(asset_ref.url)
                translations = await asyncio.to_thread(self._parse_i18n_from_js, code)
                result = translations if isinstance(translations, dict) else {}
                self._cache_i18n[cache_key] = result

                leaks = _count_js_escape_leaks(result)
                if not result:
                    self._log.warning(
                        "i18n %s/%s parsed to 0 keys from a %d-byte asset (%s)",
                        lang_norm,
                        namespace_norm,
                        len(code),
                        asset_ref.url,
                    )
                elif leaks:
                    self._log.warning(
                        "i18n %s/%s has %d values that still contain JS escape sequences",
                        lang_norm,
                        namespace_norm,
                        leaks,
                    )
                else:
                    self._log.debug("Loaded i18n %s/%s: %d keys", lang_norm, namespace_norm, len(result))
                return result
            except Exception as e:
                self._log.warning("Failed to load i18n %s/%s: %s", lang_norm, namespace_norm, e)
                self._cache_i18n[cache_key] = {}
                return {}

    @staticmethod
    def _normalize_unit_key(raw_key: Any) -> str | None:
        if isinstance(raw_key, int):
            return str(raw_key)
        if isinstance(raw_key, float):
            if raw_key.is_integer():
                return str(int(raw_key))
            return None
        if isinstance(raw_key, str):
            key = raw_key.strip()
            if not key:
                return None
            if key.isdigit():
                return key
            try:
                as_float = float(key)
            except ValueError:
                # Named units (``DEVICE_STATE``) and ``CustomUnit['…']`` leftovers.
                public = js_public_member_name(key)
                if public is not None:
                    return public
                if _CATALOG_LIKE_TOKEN_RE.fullmatch(key) is not None:
                    return key
                return None
            return str(int(as_float)) if as_float.is_integer() else None
        return None

    @staticmethod
    def _is_unit_descriptor_entry(value: Any) -> bool:
        if not isinstance(value, Mapping):
            return False
        # SPA ``DATE_TIME`` (CustomUnit 0x270f) ships as ``{parse: e => fromFormat(...)}`` only.
        return any(k in value for k in ("text", "options", "value", "valuePrepare", "parse"))

    @staticmethod
    def _units_descriptor_table_score(parsed: Mapping[str, Mapping[str, Any]]) -> tuple[int, int, int]:
        """Rank candidate objects so PARAM_* catalogs lose to numeric CustomUnit tables.

        Post-1.04 indexes also ship a large PARAM_* object whose entries look like unit
        descriptors (``text``/``options``). Prefer tables keyed by numeric unit codes.
        """
        if not parsed:
            return (0, 0, 0)
        digit_keys = 0
        param_keys = 0
        units_option_hits = 0
        for key, entry in parsed.items():
            if key.isdigit():
                digit_keys += 1
            if key.startswith("PARAM"):
                param_keys += 1
            options = entry.get("options") if isinstance(entry, Mapping) else None
            if isinstance(options, Mapping):
                for raw in options.values():
                    if isinstance(raw, str) and raw.startswith("units."):
                        units_option_hits += 1
                        break
        return (digit_keys, units_option_hits, len(parsed) - param_keys)

    _CUSTOM_UNIT_ENUM_RE = re.compile(r"\['([A-Z][A-Z0-9_]*)'\]=(0x[0-9a-fA-F]+|\d+)\]='\1'")

    def _parse_custom_unit_codes_from_index(self, code: bytes) -> dict[str, str]:
        """Parse ``CustomUnit`` bidirectional enum members (``BOILER_STATE`` ↔ ``9998``)."""
        text = code.decode("utf-8", errors="replace")
        out: dict[str, str] = {}
        for match in self._CUSTOM_UNIT_ENUM_RE.finditer(text):
            name = match.group(1)
            raw = match.group(2)
            # Pattern only matches hex/decimal literals.
            value = int(raw, 16) if raw.lower().startswith("0x") else int(raw)
            # CustomUnit codes live in the high 99xx band; skip unrelated enums.
            if value < 9000 or value > 9999:
                continue
            out[name] = str(value)
        return out

    def _parse_units_descriptor_table_from_index(self, code: bytes) -> dict[str, dict[str, Any]]:
        """Parse the units descriptor table using the pure-Python JS value extractor."""
        try:
            candidates = iter_top_level_object_assignments(code)
        except Exception as exc:
            self._log.debug("Failed to parse units descriptor table from index: %s", exc)
            return {}

        aliases = self._parse_custom_unit_codes_from_index(code)
        best: dict[str, dict[str, Any]] = {}
        best_score = self._units_descriptor_table_score(best)
        largest_candidate = 0

        for candidate in candidates:
            parsed: dict[str, dict[str, Any]] = {}
            descriptor_keys = 0
            for key_raw, value_raw in candidate.items():
                if not self._is_unit_descriptor_entry(value_raw):
                    continue
                descriptor_keys += 1
                coerced: Any = key_raw
                if isinstance(key_raw, str):
                    hex_num = parse_js_number(key_raw) if key_raw.lower().startswith("0x") else None
                    if hex_num is not None:
                        coerced = hex_num
                key = self._normalize_unit_key(coerced)
                if key is None:
                    continue
                if not key.isdigit() and key in aliases:
                    key = aliases[key]
                parsed[key] = dict(value_raw) if isinstance(value_raw, Mapping) else {"value": value_raw}

            largest_candidate = max(largest_candidate, descriptor_keys)
            score = self._units_descriptor_table_score(parsed)
            if score > best_score:
                best = parsed
                best_score = score

        if not best:
            if largest_candidate:
                self._log.warning(
                    "Units descriptor table kept 0 of %d keys from the largest candidate object",
                    largest_candidate,
                )
            elif len(code) >= 50_000:
                self._log.warning("Units descriptor table parsed to 0 entries from a %d-byte index", len(code))

        return best

    def _ensure_units_tables_loaded(self) -> dict[str, dict[str, Any]]:
        """Load (and cache) the units descriptor table and CustomUnit aliases from index."""
        cached = self._units_descriptor_table
        if isinstance(cached, dict):
            return cached
        if not self._idx.index_bytes:
            self._units_descriptor_table = {}
            self._custom_unit_codes = {}
            return self._units_descriptor_table
        self._units_descriptor_table = self._parse_units_descriptor_table_from_index(self._idx.index_bytes)
        self._custom_unit_codes = self._parse_custom_unit_codes_from_index(self._idx.index_bytes)
        return self._units_descriptor_table

    def canonical_unit_code(self, unit_code: Any) -> str | None:
        """Return numeric unit-code string for ``unit_code`` when known.

        Accepts legacy numeric codes and post-1.04 ``CustomUnit`` names
        (``BOILER_STATE`` → ``9998``).
        """
        key = self._normalize_unit_key(unit_code)
        if key is None:
            return None
        if key.isdigit():
            return key
        aliases = self._custom_unit_codes
        if not isinstance(aliases, dict):
            if not self._idx.index_bytes:
                return None
            aliases = self._parse_custom_unit_codes_from_index(self._idx.index_bytes)
            self._custom_unit_codes = aliases
        return aliases.get(key)

    def _lookup_unit_descriptor_entry(self, table: Mapping[str, Mapping[str, Any]], key: str) -> dict[str, Any] | None:
        """Return a copied descriptor for ``key``, falling back to CustomUnit aliases."""
        entry: Any = table.get(key)
        if entry is None:
            alias = self.canonical_unit_code(key)
            if alias is not None and alias != key:
                entry = table.get(alias)
        return dict(entry) if isinstance(entry, Mapping) else None

    async def get_unit_descriptor(self, unit_code: Any) -> dict[str, Any] | None:
        """Return unit descriptor for raw unit code from index-defined transform table.

        The BragerOne frontend keeps canonical unit behavior in an index-scoped table
        (text/options/value/valuePrepare). This helper exposes that table entry by raw
        unit code so runtime consumers can apply the same mappings/transforms.

        Named ``CustomUnit`` tokens (``BOILER_STATE``) resolve via the numeric alias when
        the table is still keyed by codes like ``9998``.
        """
        key = self._normalize_unit_key(unit_code)
        if key is None:
            return None

        cached = self._units_descriptor_table
        if isinstance(cached, dict):
            return self._lookup_unit_descriptor_entry(cached, key)

        async with self._units_descriptor_lock:
            cached_inner = self._units_descriptor_table
            if not isinstance(cached_inner, dict):
                if not self._idx.index_bytes:
                    await self._ensure_index_loaded()
                cached_inner = await asyncio.to_thread(self._ensure_units_tables_loaded)

        return self._lookup_unit_descriptor_entry(cached_inner, key)

    def _find_i18n_asset(self, lang: str, namespace: str) -> AssetRef | None:
        """Find i18n asset for given language and namespace.

        Looks for patterns in index like:
        "../../resources/languages/{lang}/{namespace}.json":()=>d(()=>import("./file-hash.js"),[])

        Args:
            lang: Language code.
            namespace: Namespace (e.g., 'parameters', 'units').

        Returns:
            AssetRef for the i18n file or None if not found.
        """
        if not self._idx.index_bytes:
            return None

        index_text = self._idx.index_bytes.decode("utf-8", errors="replace")

        # Upstream namespaces are not consistently cased (e.g. `app.json` vs `diodeState.json`).
        # Match case-insensitively by scanning all language imports and selecting the requested namespace.
        want = str(namespace).strip().lower()
        if not want:
            return None

        # Capture the full ``import("./<file>.js")`` filename. Hashes may contain hyphens
        # (``info-Bpu026-3.js``) or even end with one (``tariff-Db9Vj8s-.js``); splitting the
        # basename ourselves is how those chunks used to go missing.
        import_pattern = re.compile(
            rf'["\']\.\.\/\.\.\/resources\/languages\/{re.escape(lang)}\/([^"\']+)\.json["\']'
            r':\s*\(\)\s*=>\s*\w+\s*\(\s*\(\)\s*=>\s*import\s*\(\s*["\']\.\/([^"\']+\.js)["\']'
        )

        match: re.Match[str] | None = None
        for m in import_pattern.finditer(index_text):
            ns_in_index = m.group(1)
            if str(ns_in_index).strip().lower() == want:
                match = m
                break

        if not match:
            self._log.debug("No i18n asset match for %s/%s (case-insensitive)", lang, namespace)
            return None

        asset_filename = match.group(2)
        stem = asset_filename[:-3]  # the import regex already requires a ``.js`` suffix
        file_base, file_hash = _i18n_import_base_and_hash(match.group(1), stem)

        asset_ref = self._idx.find_asset_for_full_name(stem)
        if asset_ref is not None:
            return asset_ref

        asset_ref = self._idx.find_asset_for_basename(file_base)
        if asset_ref is not None and (not file_hash or asset_ref.hash == file_hash):
            return asset_ref

        if self._last_index_url:
            asset_url = self._smart_urljoin(self._last_index_url, asset_filename)
            return AssetRef(url=asset_url, base=file_base, hash=file_hash)

        return None

    def _parse_i18n_from_js(self, code: bytes) -> dict[str, Any]:
        """Parse i18n translations from a JavaScript module (pure-Python path).

        Expected format:
        export default { "key1": "value1", "key2": "value2", ... }
        """
        return parse_i18n_module(code)

    def _parse_language_config_from_js(self, js_bytes: bytes) -> TranslationConfig:
        """Parse TranslationConfig from index JS bytes (pure-Python path)."""
        parsed = find_language_config_object(js_bytes)
        if parsed is None:
            raise ValueError("Language config object not found")
        if not isinstance(parsed, dict):
            raise ValueError("Language config object missing required fields")
        translations = parsed.get("translations")
        default_translation = parsed.get("defaultTranslation")
        if not isinstance(translations, list) or not isinstance(default_translation, str) or not default_translation:
            raise ValueError("Language config object missing required fields")
        cleaned = [item for item in translations if isinstance(item, dict)]
        if not cleaned:
            raise ValueError("Language config object missing required fields")
        return TranslationConfig(translations=cleaned, default_translation=default_translation)
