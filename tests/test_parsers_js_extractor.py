"""Tests for JavaScript extractor parser functionality."""

from pybragerone.parsers.js_extract import _strip_trailing_commas, extract_embedded_json


def test_strip_trailing_commas() -> None:
    """Test removal of trailing commas from JSON-like strings.

    Verifies that the _strip_trailing_commas function correctly removes
    trailing commas from object and array structures.
    """
    s = '{"a": 1,"b": 2,}'
    out = _strip_trailing_commas(s)
    assert out == '{"a": 1,"b": 2}'

    # Test with array
    s_array = '["item1", "item2",]'
    out_array = _strip_trailing_commas(s_array)
    assert out_array == '["item1", "item2"]'


def test_extract_embedded_json_parse() -> None:
    """Test extraction of JSON data from JavaScript export statements.

    Verifies that the extract_embedded_json function can correctly parse
    and extract JSON data from JavaScript export default JSON.parse() statements,
    handling escaped quotes properly.
    """
    js = 'export default JSON.parse("{\\"a\\":1,\\"b\\":2}");'
    out = extract_embedded_json(js)
    assert out == {"a": 1, "b": 2}