"""Unit tests for LiveAssetsCatalog fallbacks and JS-value helpers."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from tree_sitter import Node

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models.catalog import AssetRef, LiveAssetsCatalog, _walk


def _catalog() -> LiveAssetsCatalog:
    api = cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient))
    catalog = LiveAssetsCatalog(api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/dummy.js", base="dummy", hash="x")]
    return catalog


def _first_node(root: Node, node_type: str) -> Node:
    for node in _walk(root):
        if node.type == node_type:
            return node
    raise AssertionError(f"missing {node_type} node")


def _largest_node(root: Node, node_type: str) -> Node:
    best: Node | None = None
    best_sz = -1
    for node in _walk(root):
        if node.type != node_type:
            continue
        size = node.end_byte - node.start_byte
        if size > best_sz:
            best = node
            best_sz = size
    if best is None:
        raise AssertionError(f"missing {node_type} node")
    return best


def test_attach_parameters_tokens_normalizes_calls_dicts_and_children() -> None:
    """Extract tokens from call strings, dicts, and recurse into children."""

    class _Blank:
        def __str__(self) -> str:
            return ""

    catalog = _catalog()
    attached = catalog._attach_parameters_tokens(
        {
            "path": "boiler",
            "parameters": {
                "read": [
                    "E(A.READ,'PARAM_1')",
                    "PLAIN_TOKEN",
                    {"parameter": "E(A.WRITE,'PARAM_2')"},
                    {"token": "PARAM_3"},
                    {"parameter": "PLAIN_FROM_DICT"},
                    {"parameter": "KEEP_PLAIN", "token": "KEEP_TOKEN"},
                    {"name": "no-token"},
                    {"label": "E(A.READ,'PARAM_FALLBACK')"},
                    7,
                    None,
                    ("E(A.READ,'PARAM_SEQ')",),
                    _Blank(),
                ],
                "write": None,
            },
            "children": [
                {"path": "child", "parameters": {"status": ["E(A.STATUS,'STATUS_P5_1')"]}},
                "keep-me",
            ],
        }
    )

    read = attached["parameters"]["read"]
    assert read[0]["token"] == "PARAM_1"
    assert read[1]["token"] == "PLAIN_TOKEN"
    assert read[2]["token"] == "PARAM_2"
    assert read[3]["parameter"] == "PARAM_3"
    assert read[4]["token"] == "PLAIN_FROM_DICT"
    assert read[5]["token"] == "KEEP_TOKEN"
    assert read[6] == {"name": "no-token"}
    assert read[7]["token"] == "PARAM_FALLBACK"
    assert read[8]["token"] == "7"
    assert read[10]["token"] == "PARAM_SEQ"
    assert attached["parameters"]["write"] == []
    assert attached["children"][0]["parameters"]["status"][0]["token"] == "STATUS_P5_1"
    assert attached["children"][1] == "keep-me"

    converted = catalog._attach_parameters_tokens({"path": "x", "children": "wA"})
    assert converted["children"] == []

    leftover = catalog._attach_parameters_tokens(
        {
            "path": "userMenu",
            "meta": {
                "parameters": {
                    "write": (
                        "['PARAM_45','PARAM_34']['map'](_0x46820c=>"
                        "({'permissionModule':_0x58838d['DISPLAY_PARAMETER_LEVEL_1'],"
                        "'parameter':_0x2d2290(_0x870f31['WRITE'],_0x46820c)}))"
                    )
                }
            },
        }
    )
    write_tokens = [item["token"] for item in leftover["meta"]["parameters"]["write"]]
    assert write_tokens == ["PARAM_45", "PARAM_34"]

    double_quote_map = catalog._parameter_section_items("['PARAM_99'][\"map\"](x => ({parameter: helper(WRITE, x)}))")
    assert double_quote_map == [{"parameter": "PARAM_99"}]
    assert catalog._parameter_section_items("not-a-map") == []
    assert catalog._parameter_section_items(None) == []


def test_build_param_map_from_obj_normalizes_command_branches_and_status() -> None:
    """Normalize any/if/else command rules, status maps, use-aliases, and units."""
    catalog = _catalog()
    pm = catalog._build_param_map_from_obj(
        {
            "PARAM_CMD": {
                "group": "P4",
                "componentType": "button",
                "unit": 9,
                "limits": {"min": 0, "max": 1},
                "statusFlags": "ignore-non-list",
                "status": {"t.INVISIBLE": [{"group": "P5", "number": 0, "use": "s"}]},
                "minValue": {"group": "P4", "number": 1, "use": "n"},
                "max": [{"group": "P4", "number": 1, "use": "x"}],
                "any": [
                    "skip",
                    {
                        "if": [{"operation": "e.equalTo", "expected": "!0", "value": [{"group": "P4", "number": 1}]}],
                        "then": {"command": "a.WRITE", "value": "e.ON"},
                    },
                    {
                        "elseif": [{"operation": "[t.equalTo]", "expected": "void 0", "value": "bad"}],
                        "then": {"command": "WRITE", "value": "undefined"},
                    },
                    {"else": {"command": "a.WRITE", "value": "!1"}},
                    {"then": {"command": "a.WRITE", "value": 2}},
                    {"if": [], "then": {}},
                ],
                "all": {"not": "a-list"},
            }
        },
        "PARAM_CMD",
        "test",
    )
    assert pm is not None
    assert pm.group == "P4"
    assert pm.component_type == "button"
    assert pm.units == 9
    assert pm.limits == {"min": 0, "max": 1}
    assert pm.status_flags == []
    assert pm.status_conditions is not None
    assert "t.INVISIBLE" in pm.status_conditions
    assert pm.paths["min"][0]["use"] == "n"
    assert pm.paths["max"][0]["use"] == "x"

    kinds = [rule["kind"] for rule in pm.command_rules]
    assert kinds == ["if", "elseif", "else", "if"]
    assert pm.command_rules[0]["command"] == "WRITE"
    assert pm.command_rules[0]["value"] == "e.ON"
    assert pm.command_rules[0]["conditions"][0]["expected"] is True
    assert pm.command_rules[1]["conditions"][0]["operation"] == "equalTo"
    assert pm.command_rules[1]["conditions"][0]["expected"] is None
    leftover = catalog._build_param_map_from_obj(
        {
            "PARAM_CMD": {
                "group": "P4",
                "any": [
                    {
                        "if": [
                            {
                                "operation": "_0x4891b3['equalTo']",
                                "expected": 1,
                                "value": [{"group": "P4", "number": 1}],
                            }
                        ],
                        "then": {"command": "_0xabc['WRITE']", "value": "e.ON"},
                    }
                ],
            }
        },
        "PARAM_CMD",
        "test",
    )
    assert leftover is not None
    assert leftover.command_rules[0]["conditions"][0]["operation"] == "equalTo"
    assert leftover.command_rules[0]["command"] == "WRITE"

    from_use = catalog._build_param_map_from_obj(
        {
            "use": {
                "v": {"group": "P1", "number": 0},
                "u": {"group": "P1", "number": 0},
                "s": [{"group": "P1", "number": 0, "use": "s"}],
                "n": {"group": "P1", "number": 0},
                "x": {"group": "P1", "number": 0},
            },
            "unit_name": "C",
            "range": {"min": 1, "max": 2},
            "status_bits": [{"bit": 1}],
        },
        "PARAM_USE",
        "test",
    )
    assert from_use is not None
    assert from_use.units == "C"
    assert from_use.paths["value"]
    assert from_use.paths["status"]
    assert from_use.limits == {"min": 1, "max": 2}
    assert from_use.status_flags == [{"bit": 1}]

    listed_status = catalog._build_param_map_from_obj({"status": [{"group": "P2", "number": 3}]}, "X", "test")
    assert listed_status is not None
    assert listed_status.status_conditions == {"default": [{"group": "P2", "number": 3}]}


def test_parse_i18n_from_js_handles_export_styles_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parse default-object exports, `export { x as default }`, and non-object fallbacks."""
    catalog = _catalog()
    assert catalog._parse_i18n_from_js(b'export default { "hi": "there" };') == {"hi": "there"}

    reexport = b"const bundle = { ok: true };\nexport { bundle as default };\n"
    assert catalog._parse_i18n_from_js(reexport) == {"ok": True}

    assert catalog._parse_i18n_from_js(b"export default 12;") == {}
    assert catalog._parse_i18n_from_js(b"const only = { a: 1 };") == {"a": 1}

    class _BoomTS:
        def parse(self, _code: bytes) -> Any:
            raise RuntimeError("parse failed")

    monkeypatch.setattr(catalog, "_ts", _BoomTS())
    assert catalog._parse_i18n_from_js(b"export default {};") == {}


def test_parse_js_value_and_translations_array_heuristics() -> None:
    """Parse JS literals and accept translation arrays only above the 70% threshold."""
    catalog = _catalog()
    source = """
    const cfg = {
      translations: [
        {id: "pl", flag: "PL", extra: {ok: true}, n: 1, f: 2.5, on: true, off: false, z: null, raw: ident},
        {id: "en", flag: "EN", tags: ["a", "b"]}
      ],
      defaultTranslation: "pl"
    };
    """
    tree = catalog._ts.parse(source.encode())
    array = _first_node(tree.root_node, "array")
    obj = _largest_node(tree.root_node, "object")
    assert catalog._is_translations_array(array, source) is True
    assert catalog._is_translations_array_bytes(array, source.encode()) is True

    parsed = catalog._parse_js_value(obj, source)
    assert parsed["defaultTranslation"] == "pl"
    first = parsed["translations"][0]
    assert first["id"] == "pl"
    assert first["n"] == 1
    assert first["f"] == 2.5
    assert first["on"] is True
    assert first["off"] is False
    assert first["z"] is None
    assert first["extra"] == {"ok": True}
    assert first["raw"] == "ident"

    parsed_bytes = catalog._parse_js_value_bytes(obj, source.encode())
    assert parsed_bytes == parsed
    assert catalog._extract_default_translation(obj, source) == "pl"
    assert catalog._extract_default_translation_bytes(obj, source.encode()) == "pl"
    assert catalog._extract_translations_array(obj, source) is not None
    assert catalog._extract_translations_array(obj, source) == catalog._extract_translations_array_bytes(obj, source.encode())

    quoted = "const cfg={'translations':[{'id':'pl','flag':'PL'}],'defaultTranslation':'pl'};"
    quoted_tree = catalog._ts.parse(quoted.encode())
    quoted_obj = _largest_node(quoted_tree.root_node, "object")
    quoted_parsed = catalog._parse_js_value(quoted_obj, quoted)
    assert quoted_parsed == catalog._parse_js_value_bytes(quoted_obj, quoted.encode())
    assert quoted_parsed["translations"][0]["id"] == "pl"
    assert catalog._extract_default_translation(quoted_obj, quoted) == "pl"

    weak = "const xs = [{id: 'pl', flag: 'PL'}, {foo: 1}, {bar: 2}];"
    weak_array = _first_node(catalog._ts.parse(weak.encode()).root_node, "array")
    assert catalog._is_translations_array(weak_array, weak) is False
    assert catalog._is_translations_array_bytes(weak_array, weak.encode()) is False
    empty = "const xs = [];"
    empty_array = _first_node(catalog._ts.parse(empty.encode()).root_node, "array")
    assert catalog._is_translations_array(empty_array, empty) is False

    cfg = catalog._parse_language_config_from_js(source.encode())
    assert cfg.default_translation == "pl"
    assert cfg.translations[0]["id"] == "pl"
    with pytest.raises(ValueError, match="not found"):
        catalog._parse_language_config_from_js(b"export default { foo: 1 };")


def test_parse_menu_routes_extracts_nested_routes_and_attaches_tokens() -> None:
    """Walk nested menu wrappers and normalize parameter tokens on routes."""
    catalog = _catalog()
    js = b"""
    export default {
      deviceMenu: {
        menu: [
          {
            path: "boiler",
            name: "modules.menu.boiler",
            parameters: { read: ["E(A.READ,'PARAM_1')"] },
            children: "wA"
          }
        ]
      }
    };
    """
    routes = catalog._parse_menu_routes(js)
    assert routes[0]["path"] == "boiler"
    assert routes[0]["parameters"]["read"][0]["token"] == "PARAM_1"
    assert routes[0]["children"] == []
    assert catalog._parse_menu_routes(b"export default 1;") == []


async def test_get_param_mapping_index_token_map_and_unresolved_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hit index token-map, reject empty maps, and leave unreadable assets unresolved."""
    catalog = _catalog()
    index_js = """
    export default {
      PARAM_TOKENMAP: { group: "P8", name: "token-map", value: [{ group: "P8", number: 1, use: "v" }] },
      PARAM_EMPTY: {},
      "local.key": { group: "P9", name: "weird" }
    };
    """
    catalog._idx.index_bytes = index_js.encode()
    catalog._idx.inline_param_candidates = [(-1, 4), (2, 2)]

    mapped = await catalog.get_param_mapping(["PARAM_TOKENMAP", "PARAM_EMPTY", "local.key", "NOPE"])
    assert mapped["PARAM_TOKENMAP"].group == "P8"
    assert mapped["local.key"].group == "P9"
    assert "PARAM_EMPTY" not in mapped
    assert "NOPE" not in mapped

    catalog._idx.assets_by_basename["PARAM_BADASSET"] = [
        AssetRef(url="https://example.com/PARAM_BADASSET-z.js", base="PARAM_BADASSET", hash="z")
    ]

    monkeypatch.setattr(catalog._api, "get_bytes", AsyncMock(return_value=b"export default 1;"))
    missing = await catalog.get_param_mapping(["PARAM_BADASSET"])
    assert "PARAM_BADASSET" not in missing
