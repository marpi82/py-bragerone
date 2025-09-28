"""Tests for JavaScript index resolver parsing functionality.

This module contains tests for the IndexResolver class which parses JavaScript
code to resolve parameter aliases and their definitions.
"""

from pybragerone.parsers.index_resolver import IndexResolver


def test_parameters_parse_basic() -> None:
    """Test basic parameter parsing with import statements.

    Verifies that the IndexResolver can correctly parse JavaScript code
    containing parameter imports to extract asset mappings.
    """
    js = """
    PARAM_6: import("./param-6-abc123.js"),
    PARAM_0: import("./param-0-def456.js"),
    OTHER_CONSTANT: import("./other-xyz789.js")
    """
    index_map = IndexResolver._parse_index(js)
    assert "PARAM_6" in index_map.parameters
    assert "PARAM_0" in index_map.parameters
    assert "OTHER_CONSTANT" in index_map.parameters
    assert index_map.parameters["PARAM_6"] == "/assets/param-6-abc123.js"
    assert index_map.parameters["PARAM_0"] == "/assets/param-0-def456.js"
    assert index_map.parameters["OTHER_CONSTANT"] == "/assets/other-xyz789.js"
