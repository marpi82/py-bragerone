"""Tests for JavaScript numeric literal parsing in the assets catalog."""

from __future__ import annotations

import pytest

from pybragerone.models.catalog import (
    _TS,
    LiveAssetsCatalog,
    _js_property_key,
    _node_to_python,
    _parse_js_number,
)


class _DummyApi:
    """Minimal stand-in; literal parsing never touches the network."""

    one_base = "https://example.invalid"


def _catalog() -> LiveAssetsCatalog:
    return LiveAssetsCatalog(_DummyApi())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", 0),
        ("42", 42),
        ("-7", -7),
        ("+7", 7),
        ("0x9", 9),
        ("0xa", 10),
        ("0X1F", 31),
        ("0x7f", 127),
        ("0b1010", 10),
        ("0o17", 15),
        ("1_000", 1000),
        ("10n", 10),
        ("1.5", 1.5),
        (".5", 0.5),
        ("1e3", 1000.0),
        ("-0.25", -0.25),
    ],
)
def test_parse_js_number_covers_every_literal_form(raw: str, expected: int | float) -> None:
    """Radix prefixes, separators and BigInt markers all resolve to their numeric value."""
    assert _parse_js_number(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "abc", "0xZZ", "0b12", "0o99", "units.31"])
def test_parse_js_number_rejects_non_numeric_text(raw: str) -> None:
    """Anything that is not a numeric literal must be reported as such, not guessed."""
    assert _parse_js_number(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0x9", "9"),
        ("0xa", "10"),
        ("10", "10"),
        ("1.5", "1.5"),
        ("2.0", "2"),
        ("text", "text"),
        ("valuePrepare", "valuePrepare"),
    ],
)
def test_js_property_key_matches_javascript_tostring(raw: str, expected: str) -> None:
    """JavaScript coerces numeric keys via ToString, so `{0xa: 1}` is the property `"10"`."""
    assert _js_property_key(raw) == expected


def test_node_to_python_resolves_hex_object_keys_and_values() -> None:
    """Obfuscated bundles index objects by hex literal; keys must land in decimal form."""
    js = b"const t={0x9:{'options':{0x0:'units.17.0'}},0xa:{'text':'units.10'},0x1f:0x2a};"
    tree = _TS().parse(js)
    value_node = tree.root_node.named_children[0].named_children[0].child_by_field_name("value")
    assert value_node is not None

    parsed = _node_to_python(js, value_node)

    assert set(parsed) == {"9", "10", "31"}
    assert parsed["9"] == {"options": {"0": "units.17.0"}}
    assert parsed["10"] == {"text": "units.10"}
    assert parsed["31"] == 42


def test_node_to_python_keeps_unparseable_number_text() -> None:
    """A literal we cannot interpret degrades to its source text rather than vanishing."""
    js = b"const t={'a':1_0};"
    tree = _TS().parse(js)
    value_node = tree.root_node.named_children[0].named_children[0].child_by_field_name("value")
    assert value_node is not None

    assert _node_to_python(js, value_node) == {"a": 10}


def test_units_descriptor_table_parses_hex_keyed_entries() -> None:
    """Regression: hex-keyed tables previously normalized to nothing, emptying the table."""
    js = (
        b"const u={0x9:{'options':{0x0:'units.17.0',0x1:'units.17.1'}},"
        b"0xa:{'text':'units.10','value':_0x201288=>_0x201288*0x6},"
        b"0x31:{'text':'units.31','value':_0x4fdb4d=>Number(_0x4fdb4d*0.1)['toFixed'](0x1)}};"
        b"export{u as default};"
    )

    table = _catalog()._parse_units_descriptor_table_from_index(js)

    assert set(table) == {"9", "10", "49"}
    assert table["49"]["text"] == "units.31"
    assert table["9"]["options"] == {"0": "units.17.0", "1": "units.17.1"}
