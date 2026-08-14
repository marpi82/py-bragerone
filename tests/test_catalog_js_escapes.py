"""Tests for JavaScript string-literal escape decoding in the assets catalog."""

from __future__ import annotations

import pytest

from pybragerone.models.catalog import LiveAssetsCatalog, _decode_js_escapes, _string_value
from pybragerone.models.i18n import I18nResolver


class _DummyApi:
    """Minimal stand-in; escape decoding never touches the network."""

    one_base = "https://example.invalid"


def _catalog() -> LiveAssetsCatalog:
    return LiveAssetsCatalog(_DummyApi())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("plain text", "plain text"),
        (r"\x20", " "),
        (r"Ilo\u015b\u0107\x20rozpale\u0144", "Ilość rozpaleń"),
        (r"Moc\x20palnika", "Moc palnika"),
        (r"WPA\x20120/06,\x20DM80", "WPA 120/06, DM80"),
        (r"\n\r\t", "\n\r\t"),
        (r"\b\f\v", "\b\f\v"),
        (r"quote\'s", "quote's"),
        (r"say\"hi\"", 'say"hi"'),
        (r"back\\slash", "back\\slash"),
        (r"solidus\/path", "solidus/path"),
        (r"\u00b0C", "°C"),
        (r"\u{1F600}", "\U0001f600"),
        (r"\ud83d\ude00", "\U0001f600"),
        (r"nbsp\xa0here", "nbsp\xa0here"),
    ],
)
def test_decode_js_escapes_handles_known_sequences(raw: str, expected: str) -> None:
    """Every escape form JavaScript accepts resolves to the character it denotes."""
    assert _decode_js_escapes(raw) == expected


def test_decode_js_escapes_preserves_non_ascii_payloads() -> None:
    """A latin-1 round trip (unicode_escape) would corrupt these; a manual scan must not."""
    assert _decode_js_escapes("Wymiennik ciepła") == "Wymiennik ciepła"
    assert _decode_js_escapes(r"Wymiennik\x20ciepła") == "Wymiennik ciepła"
    assert _decode_js_escapes("温度") == "温度"


def test_decode_js_escapes_degrades_on_malformed_input() -> None:
    """Vendor bundles change without notice; malformed escapes must not raise."""
    assert _decode_js_escapes("\\") == "\\"
    assert _decode_js_escapes(r"\xZZ") == "xZZ"
    assert _decode_js_escapes(r"\x2") == "x2"
    assert _decode_js_escapes(r"\uZZZZ") == "uZZZZ"
    assert _decode_js_escapes(r"\u{}") == "u{}"
    assert _decode_js_escapes(r"\u{110000}") == "\ufffd"
    assert _decode_js_escapes(r"\q") == "q"


def test_decode_js_escapes_replaces_lone_surrogates() -> None:
    """Lone surrogates cannot be encoded to UTF-8 and would fail far from here."""
    assert _decode_js_escapes(r"\ud83d") == "\ufffd"
    assert _decode_js_escapes(r"\ud83dtail") == "\ufffdtail"


def test_decode_js_escapes_drops_line_continuations() -> None:
    """A backslash before a newline continues the literal and contributes nothing."""
    assert _decode_js_escapes("one\\\ntwo") == "onetwo"
    assert _decode_js_escapes("one\\\r\ntwo") == "onetwo"


def test_decode_js_escapes_handles_nul_and_legacy_octal() -> None:
    """A digit after a zero escape means legacy octal, which must not become NUL."""
    assert _decode_js_escapes(r"a\0b") == "a\0b"
    assert _decode_js_escapes(r"a\01b") == "a01b"


def test_string_value_unquotes_and_decodes() -> None:
    """Quote stripping and escape decoding happen together for every quote style."""
    assert _string_value(r'"Moc\x20palnika"') == "Moc palnika"
    assert _string_value(r"'Moc\x20palnika'") == "Moc palnika"
    assert _string_value(r"`Moc\x20palnika`") == "Moc palnika"
    assert _string_value("unquoted") == "unquoted"


def test_parse_i18n_decodes_obfuscated_units_namespace() -> None:
    """Regression for the obfuscated bundle shape: `units['0']` is a hex-escaped space."""
    js = rb"""
const units={'0':'\x20','1':'\u00b0C','5':'%','31':'kW','6':{'0':'Ochrona\x20powrotu'}};
export{units as default};
"""
    parsed = _catalog()._parse_i18n_from_js(js)

    assert parsed["0"] == " "
    assert parsed["1"] == "°C"
    assert parsed["5"] == "%"
    assert parsed["31"] == "kW"
    assert parsed["6"]["0"] == "Ochrona powrotu"


def test_blank_unit_is_dropped_after_decoding() -> None:
    r"""The decoded `\x20` unit must normalize away instead of reaching consumers as text."""
    js = rb"""
const units={'0':'\x20'};
export{units as default};
"""
    parsed = _catalog()._parse_i18n_from_js(js)

    assert I18nResolver.normalize_unit_value(parsed["0"]) is None


def test_parse_i18n_decodes_obfuscated_parameter_labels() -> None:
    """Labels ship as consts that a trailing object re-exports by explicit key."""
    js = rb"""
const PARAM_P4_43='Ilo\u015b\u0107\x20rozpale\u0144',PARAM_P4_14='Moc\x20palnika',
parameters={'PARAM_P4_43':PARAM_P4_43,'PARAM_P4_14':PARAM_P4_14};
export{parameters as default};
"""
    parsed = _catalog()._parse_i18n_from_js(js)

    assert parsed["PARAM_P4_43"] == "Ilość rozpaleń"
    assert parsed["PARAM_P4_14"] == "Moc palnika"
