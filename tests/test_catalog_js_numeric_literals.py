"""Tests for JavaScript numeric literal parsing in the assets catalog."""

from __future__ import annotations

from typing import Any, cast

import pytest

from pybragerone.api.client import BragerOneApiClient
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

    async def get_bytes(self, url: str) -> bytes:
        """Return empty JS so refresh_index tests can clear caches without network."""
        _ = url
        return b"const x={};"


def _catalog() -> LiveAssetsCatalog:
    return LiveAssetsCatalog(cast(BragerOneApiClient, _DummyApi()))


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


def test_node_to_python_parses_numeric_separators_in_values() -> None:
    """Separators are grouping only, so `1_0` is the number ten, not the text `1_0`."""
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


def test_units_descriptor_table_prefers_numeric_over_param_catalog() -> None:
    """Post-1.04 indexes also expose a large PARAM_* object; do not select it as units."""
    js = (
        b"const params={"
        b"PARAM_0:{'text':'parameters.0'},"
        b"PARAM_1:{'text':'parameters.1'},"
        b"PARAM_2:{'options':{0:'a',1:'b'}},"
        b"PARAM_3:{'text':'parameters.3'},"
        b"PARAM_4:{'text':'parameters.4'}};"
        b"const units={"
        b"0x270e:{'options':{'BoilerState[\\'STOP\\']':'units.9998.0','BoilerState[\\'STANDBY\\']':'units.9998.4'}},"
        b"0x270a:{'options':{0x0:'units.9994.0',0x1:'units.9994.1'}}};"
        b"export{params,units};"
    )

    table = _catalog()._parse_units_descriptor_table_from_index(js)

    assert "9998" in table
    assert "9994" in table
    assert "PARAM_0" not in table
    assert table["9998"]["options"]["BoilerState['STOP']"] == "units.9998.0"


def test_parse_custom_unit_codes_maps_boiler_state() -> None:
    """Parse CustomUnit bidirectional enum members in the 99xx band."""
    js = (
        b"var _0xcu=_0xcu||{};"
        b"_0xcu[_0xcu['DEVICE_STATE']=0x270a]='DEVICE_STATE',"
        b"_0xcu[_0xcu['BOILER_STATE']=0x270e]='BOILER_STATE',"
        b"_0xcu[_0xcu['OTHER']=0x10]='OTHER';"
    )
    catalog = _catalog()
    aliases = catalog._parse_custom_unit_codes_from_index(js)
    assert aliases == {"DEVICE_STATE": "9994", "BOILER_STATE": "9998"}


def test_units_descriptor_table_score_empty_and_param_penalty() -> None:
    """Empty tables score zero; PARAM_* keys lower the tertiary score."""
    assert LiveAssetsCatalog._units_descriptor_table_score({}) == (0, 0, 0)
    scored = LiveAssetsCatalog._units_descriptor_table_score(
        {
            "9998": {"options": {"STOP": "units.9998.0"}},
            "PARAM_0": {"text": "parameters.0"},
        }
    )
    assert scored[0] == 1
    assert scored[1] == 1
    assert scored[2] == 1  # len 2 - 1 PARAM key
    # Options without units.* tokens, and non-mapping options, do not bump the score.
    no_units = LiveAssetsCatalog._units_descriptor_table_score(
        {
            "9994": {"options": {"0": "off", "1": "on"}},
            "9995": cast(Any, {"options": "not-a-map"}),
            "9996": {"options": {}},
            "9997": cast(Any, "not-an-entry-mapping"),
        }
    )
    assert no_units[0] == 4
    assert no_units[1] == 0


def test_canonical_unit_code_aliases_named_custom_unit() -> None:
    """Named CustomUnit tokens collapse to the numeric code string."""
    catalog = _catalog()
    catalog._idx.index_bytes = (
        b"_0xcu[_0xcu['BOILER_STATE']=0x270e]='BOILER_STATE',_0xcu[_0xcu['DEVICE_STATE']=0x270a]='DEVICE_STATE';"
    )
    catalog._custom_unit_codes = None
    assert catalog.canonical_unit_code(9998) == "9998"
    assert catalog.canonical_unit_code("BOILER_STATE") == "9998"
    assert catalog.canonical_unit_code("DEVICE_STATE") == "9994"
    assert catalog.canonical_unit_code("not a unit") is None
    assert catalog.canonical_unit_code("UNKNOWN_STATE") is None


def test_canonical_unit_code_without_index_bytes_returns_none_for_names() -> None:
    """Named tokens cannot alias when the index has not been loaded."""
    catalog = _catalog()
    catalog._idx.index_bytes = b""
    catalog._custom_unit_codes = None
    assert catalog.canonical_unit_code("BOILER_STATE") is None


async def test_get_unit_descriptor_aliases_named_unit_from_cached_table() -> None:
    """``BOILER_STATE`` resolves via alias when the table is keyed by ``9998``."""
    catalog = _catalog()
    catalog._units_descriptor_table = {
        "9998": {"options": {"STOP": "units.9998.0"}, "text": "units.31"},
    }
    catalog._custom_unit_codes = {"BOILER_STATE": "9998"}
    desc = await catalog.get_unit_descriptor("BOILER_STATE")
    assert desc is not None
    assert desc["options"]["STOP"] == "units.9998.0"
    assert await catalog.get_unit_descriptor("not a unit") is None
    assert await catalog.get_unit_descriptor("MISSING") is None


async def test_get_unit_descriptor_loads_tables_from_index_bytes() -> None:
    """Uncached lookup parses index bytes and aliases named CustomUnit tokens."""
    catalog = _catalog()
    catalog._units_descriptor_table = None
    catalog._custom_unit_codes = None
    catalog._idx.index_bytes = (
        b"const units={0x270e:{'options':{'STOP':'units.9998.0'},'text':'units.31'}};"
        b"_0xcu[_0xcu['BOILER_STATE']=0x270e]='BOILER_STATE';"
    )
    desc = await catalog.get_unit_descriptor("BOILER_STATE")
    assert desc is not None
    assert desc["options"]["STOP"] == "units.9998.0"
    # Second call hits the cached table path.
    again = await catalog.get_unit_descriptor(9998)
    assert again is not None
    assert again["text"] == "units.31"


def test_ensure_units_tables_loaded_empty_without_index() -> None:
    """Missing index bytes yields empty descriptor and alias caches."""
    catalog = _catalog()
    catalog._units_descriptor_table = None
    catalog._custom_unit_codes = None
    catalog._idx.index_bytes = b""
    assert catalog._ensure_units_tables_loaded() == {}
    assert catalog._custom_unit_codes == {}


def test_ensure_units_tables_loaded_returns_cached_table() -> None:
    """Cached descriptor table is returned without re-parsing."""
    catalog = _catalog()
    cached = {"9998": {"text": "units.31"}}
    catalog._units_descriptor_table = cached
    assert catalog._ensure_units_tables_loaded() is cached


async def test_refresh_index_clears_custom_unit_codes_cache() -> None:
    """Successful index refresh drops cached CustomUnit aliases."""
    catalog = _catalog()
    catalog._custom_unit_codes = {"BOILER_STATE": "9998"}
    catalog._units_descriptor_table = {"9998": {"text": "units.31"}}
    await catalog.refresh_index("https://example.invalid/assets/index-test.js", allow_recover=False)
    # refresh_index clears caches; read via Any so mypy does not keep the pre-call dict types.
    codes: Any = catalog._custom_unit_codes
    table: Any = catalog._units_descriptor_table
    assert codes is None
    assert table is None


def test_normalize_unit_key_accepts_named_and_custom_unit() -> None:
    """Post-1.04 units may be bare names or ``CustomUnit['…']`` leftovers."""
    catalog = _catalog()
    assert catalog._normalize_unit_key("DEVICE_STATE") == "DEVICE_STATE"
    assert catalog._normalize_unit_key("CustomUnit['CASCADE_CONTROLLER_STATE']") == "CASCADE_CONTROLLER_STATE"
    assert catalog._normalize_unit_key(9994) == "9994"
    assert catalog._normalize_unit_key("not a unit") is None
