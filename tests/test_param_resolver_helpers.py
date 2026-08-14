"""Unit tests for ParamResolver / ComputedValueEvaluator helper branches."""

from __future__ import annotations

from typing import Any, cast

from pybragerone.models.menu import MenuResult
from pybragerone.models.param import ParamStore
from pybragerone.models.param_resolver import ComputedValueEvaluator, ParamResolver


def _evaluator(*pairs: tuple[str, object]) -> ComputedValueEvaluator:
    store = ParamStore()
    for key, value in pairs:
        store.upsert(key, value)
    return ComputedValueEvaluator(store)


def test_regex_from_literal_accepts_js_literals_and_rejects_junk() -> None:
    """Compile `/pattern/flags` literals; ignore non-strings and invalid patterns."""
    compiled = ComputedValueEvaluator._regex_from_literal("/WORK/i")
    assert compiled is not None
    assert compiled.search("work")

    assert ComputedValueEvaluator._regex_from_literal("/WORK/") is not None
    assert ComputedValueEvaluator._regex_from_literal(12) is None
    assert ComputedValueEvaluator._regex_from_literal("WORK") is None
    assert ComputedValueEvaluator._regex_from_literal("/") is None
    assert ComputedValueEvaluator._regex_from_literal("/abc") is None
    assert ComputedValueEvaluator._regex_from_literal("/(/i") is None


def test_compare_condition_covers_ops_and_void_expected() -> None:
    """Compare numeric/string ops, regex matches, and `void 0` expected values."""
    compare = ComputedValueEvaluator._compare_condition
    assert compare(op=None, actual=1, expected=1) is False
    assert compare(op="unknown", actual=1, expected=1) is False

    assert compare(op="equalTo", actual=None, expected="void 0") is True
    assert compare(op="notEqualTo", actual=1, expected=2) is True
    assert compare(op="greaterThan", actual=3, expected=2) is True
    assert compare(op="greaterThan", actual=None, expected=2) is False
    assert compare(op="greaterThanOrEqualTo", actual=2, expected=2) is True
    assert compare(op="lessThan", actual=1, expected=2) is True
    assert compare(op="lessThanOrEqualTo", actual=2, expected=2) is True
    assert compare(op="lessThan", actual=1, expected=None) is False

    assert compare(op="matches", actual="WORK", expected="/work/i") is True
    assert compare(op="notMatches", actual="IDLE", expected="/WORK/") is True
    assert compare(op="matches", actual=None, expected="/WORK/") is False
    assert compare(op="matches", actual="WORK", expected="not-a-regex") is False


def test_read_store_getter_walks_maps_lists_and_int_keys() -> None:
    """Resolve dotted storeGetter paths, including `{placeholders}` and list indexes."""
    evaluator = _evaluator()
    evaluator.set_context(
        {
            "module": "dev",
            "dev": {
                "items": [{"name": "pump"}, {"name": "fan"}],
                "by_id": {7: "int-key"},
            },
            "scalar": "leaf",
        }
    )

    assert evaluator._read_store_getter("{module}.items.0.name") == "pump"
    assert evaluator._read_store_getter("dev.items.1.name") == "fan"
    assert evaluator._read_store_getter("dev.by_id.7") == "int-key"
    assert evaluator._read_store_getter("{missing}") is None
    assert evaluator._read_store_getter("dev.items.9") is None
    assert evaluator._read_store_getter("dev.items.nope") is None
    assert evaluator._read_store_getter("dev.missing") is None
    assert evaluator._read_store_getter("scalar.child") is None
    evaluator.set_context(None)
    assert evaluator._read_store_getter("dev.items.0") is None


def test_eval_condition_any_store_getter_and_address_selectors() -> None:
    """Evaluate storeGetter conditions and bit/mask/raw address selectors."""
    evaluator = _evaluator(("P5.s4", 1 << 5), ("P6.v13", "2"), ("P7.v1", "nope"))
    evaluator.set_context({"mode": "auto"})

    assert evaluator._eval_condition_any({"operation": None, "expected": 1, "value": []}) is False
    assert evaluator._eval_condition_any({"operation": "equalTo", "expected": "auto", "value": {"storeGetter": "mode"}}) is True
    assert evaluator._eval_condition_any({"operation": "equalTo", "expected": 1, "value": {"storeGetter": "  "}}) is False
    assert evaluator._eval_condition_any({"operation": "equalTo", "expected": 1, "value": {"other": 1}}) is False
    assert evaluator._eval_condition_any({"operation": "equalTo", "expected": 1, "value": []}) is False
    assert evaluator._eval_condition_any({"operation": "equalTo", "expected": 1, "value": "bad"}) is False

    bit_hit = {
        "operation": "t.equalTo",
        "expected": 1,
        "value": [None, {"group": "P5", "number": 4, "use": "s", "bit": 5}],
    }
    assert evaluator._eval_condition_any(bit_hit) is True

    mask_hit = {
        "operation": "equalTo",
        "expected": 2,
        "value": [{"group": "P6", "number": 13, "use": "v", "mask": 0x0F}],
    }
    assert evaluator._eval_condition_any(mask_hit) is True

    raw_skip = {
        "operation": "equalTo",
        "expected": 1,
        "value": [
            {"group": "P9", "number": 1, "use": "v"},
            {"group": "P7", "number": 1, "use": "v"},
            {"group": 5, "number": 1, "use": "v"},
        ],
    }
    assert evaluator._eval_condition_any(raw_skip) is False


def test_eval_any_rules_skips_junk_and_normalizes_then() -> None:
    """Walk if/elseif chains, skip invalid rules, and normalize then-values."""
    evaluator = _evaluator(("P1.v0", 1))
    cond = {"operation": "equalTo", "expected": 1, "value": [{"group": "P1", "number": 0, "use": "v"}]}

    assert evaluator.evaluate("not-a-mapping") is None
    assert evaluator.evaluate({"other": []}) is None
    assert evaluator._eval_any_rules(["skip", {"if": None}, {"if": []}, {"if": [cond], "then": "o.WORK"}]) == "WORK"
    assert evaluator._eval_any_rules([{"elseif": [cond], "then": {"value": "e.ON"}}]) == "e.ON"
    assert evaluator._eval_any_rules([{"if": [cond], "then": 3.0}]) == "3"
    assert evaluator._normalize_computed_value("") is None
    assert evaluator._normalize_computed_value(1.5) is None
    assert evaluator._operation_name("  ") is None
    assert evaluator._operation_name(None) is None


def test_parse_and_apply_numeric_transform_variants() -> None:
    """Parse arrow-function transforms and apply shift/factor/precision."""
    parse = ParamResolver._parse_numeric_transform
    apply = ParamResolver._apply_numeric_transform

    assert parse(12) is None
    assert parse("   ") is None
    assert parse("e * 10") is None
    assert parse("e => { return e * 2; }") is None

    shift = parse("e => e + 1")
    assert shift is not None
    assert shift.shift == 1.0
    assert shift.factor == 1.0
    assert apply(10, "e => e + 1") == 11
    assert apply(255, "e => e - 127") == 128

    mul = parse("e => e * 0.1")
    assert mul is not None
    assert mul.shift == 0.0
    assert mul.factor == 0.1
    assert mul.precision is None

    div = parse("x => x / 2")
    assert div is not None
    assert div.factor == 0.5
    assert parse("x => x / 0") is None

    affine = parse("e => (e - 1) * 10")
    assert affine is not None
    assert affine.shift == -1.0
    assert affine.factor == 10.0

    plus = parse("e => (e + .5) * 2")
    assert plus is not None
    assert plus.shift == 0.5

    rounded = parse("e => Number((e * 0.1).toFixed(2))")
    assert rounded is not None
    assert rounded.precision == 2
    assert apply(15, "e => Number((e * 0.1).toFixed(2))") == 1.5
    assert apply(20, "e => e / 2") == 10
    assert apply("  ", "e => e * 2") == "  "
    assert apply("nope", "e => e * 2") == "nope"
    assert apply(True, "e => e * 2") is True
    assert apply([1], "e => e * 2") == [1]
    assert apply(3, None) == 3

    time_expr = 'e => { if(e===0)return"units.202.0"; return String((e-1)*10).padStart(2,"0"); }'
    assert apply(0, time_expr) == "units.202.0"
    assert apply(7, time_expr) == "01:00"
    assert apply(True, time_expr) is True
    assert apply("x", time_expr) == "x"

    live_time = (
        "_0x528242=>{if(_0x528242===0x0)return'units.202.0';"
        "const _0x3355bc=(_0x528242-0x1)*0xa,"
        "_0x39bbda=Math['floor'](_0x3355bc/0x3c),"
        "_0x3a625e=_0x3355bc%0x3c;"
        "return _0x39bbda['toString']()['padStart'](0x2,'0')+':'"
        "+_0x3a625e['toString']()['padStart'](0x2,'0');}"
    )
    assert ParamResolver._is_unit66_time_expr(live_time)
    assert apply(0, live_time) == "units.202.0"
    assert apply(7, live_time) == "01:00"


def test_format_command_rules_cleans_tags_and_targets() -> None:
    """Normalize command-rule tags and keep only well-formed target addresses."""
    formatted = ParamResolver._format_command_rules(
        [
            {
                "logic": "and",
                "kind": "write",
                "command": "A.WRITE",
                "value": "e.ON",
                "conditions": [
                    "skip",
                    {
                        "operation": "e.equalTo",
                        "expected": 1,
                        "targets": [
                            {"group": "P4", "number": 2, "use": "v", "condition": "drop-me"},
                            {"group": "P4", "use": "v"},
                        ],
                    },
                    {"operation": 1, "targets": "bad"},
                ],
            },
            {"value": 3},
        ]
    )
    assert formatted[0]["command"] == "WRITE"
    assert formatted[0]["value"] == "ON"
    assert formatted[0]["logic"] == "and"
    assert formatted[0]["conditions"][0]["operation"] == "equalTo"
    assert formatted[0]["conditions"][0]["targets"] == [{"address": "P4.v2", "channel": "P4.v2"}]
    assert "targets" not in formatted[0]["conditions"][1]
    assert formatted[1]["value"] == 3
    assert ParamResolver._format_command_rules(None) == []


def test_eval_status_rule_and_select_raw_any_branch() -> None:
    """Match status rules and pick the first matching any-branch (or else)."""
    values = {"P5.s0": 1, "P5.v1": "WORK"}
    equal = {
        "expected": 1,
        "operation": "e.equalTo",
        "value": [{"group": "P5", "number": 0, "use": "s"}],
    }
    assert ParamResolver._eval_status_rule(equal, values) is True
    assert ParamResolver._eval_status_rule({**equal, "operation": "e.notEqualTo", "expected": 0}, values) is True
    assert ParamResolver._eval_status_rule({**equal, "expected": "void 0"}, {"P5.s0": None}) is True

    match_rule = {
        "expected": "/work/i",
        "operation": "e.matches",
        "value": [{"group": "P5", "number": 1, "use": "v"}],
    }
    assert ParamResolver._eval_status_rule(match_rule, values) is True
    assert ParamResolver._eval_status_rule({**match_rule, "operation": "e.notMatches"}, values) is False
    assert ParamResolver._eval_status_rule({**match_rule, "expected": "plain"}, values) is False
    assert ParamResolver._eval_status_rule({**match_rule, "operation": "e.matches"}, {"P5.v1": None}) is False

    assert ParamResolver._eval_status_rule({"value": []}, values) is False
    assert ParamResolver._eval_status_rule({"value": ["bad"]}, values) is False
    assert ParamResolver._eval_status_rule({"operation": "e.equalTo", "value": [{"group": "P5"}]}, values) is False
    assert ParamResolver._eval_status_rule({**equal, "operation": "e.greaterThan"}, values) is False

    assert ParamResolver._select_raw_any_branch([{"if": [equal], "then": "not-a-mapping"}], values) is None
    selected = ParamResolver._select_raw_any_branch(
        [
            "skip",
            {"elseif": [equal], "then": {"status": {"visible": []}}},
            {"else": {"status": {"fallback": []}}},
        ],
        values,
    )
    assert selected == {"status": {"visible": []}}

    fallback = ParamResolver._select_raw_any_branch(
        [{"if": [{**equal, "expected": 9}], "else": {"ok": True}}],
        values,
    )
    assert fallback == {"ok": True}
    assert ParamResolver._select_raw_any_branch("nope", values) is None
    assert ParamResolver._select_raw_any_branch([{"if": []}], values) is None


def test_status_paths_for_visibility_prefers_paths_then_raw_then_branch() -> None:
    """Resolve visibility status rows from paths, raw.status, or the active any-branch."""
    from_paths = ParamResolver._status_paths_for_visibility(
        {"paths": {"status": [{"group": "P1", "number": 0, "use": "s"}, "skip"]}},
        {},
    )
    assert from_paths == [{"group": "P1", "number": 0, "use": "s"}]

    from_raw = ParamResolver._status_paths_for_visibility(
        {"raw": {"status": {"t.INVISIBLE": [{"group": "P2", "number": 1, "use": "s"}]}}},
        {},
    )
    assert from_raw[0]["condition"] == "t.INVISIBLE"

    from_branch = ParamResolver._status_paths_for_visibility(
        {
            "raw": {
                "any": [
                    {
                        "if": [
                            {
                                "expected": 1,
                                "operation": "e.equalTo",
                                "value": [{"group": "P5", "number": 0, "use": "s"}],
                            }
                        ],
                        "then": {"status": {"t.VISIBLE": [{"group": "P9", "number": 3, "use": "s"}]}},
                    }
                ]
            }
        },
        {"P5.s0": 1},
    )
    assert from_branch[0]["group"] == "P9"
    assert ParamResolver._status_paths_for_visibility({"raw": 1}, {}) == []
    assert ParamResolver._status_paths_from_raw_status(["bad"]) == []
    assert ParamResolver._status_paths_from_raw_status({"x": "nope"}) == []


def test_status_flag_value_reads_bits_and_if_else_rules() -> None:
    """Read a status flag from a bit path or from if/then/else rule rows."""
    bit_paths: list[dict[str, Any]] = [{"condition": "t.INVISIBLE", "group": "P5", "use": "s", "number": 0, "bit": 2}]
    assert (
        ParamResolver._status_flag_value(status_paths=bit_paths, flag_condition="t.INVISIBLE", flat_values={"P5.s0": 4}) is True
    )
    assert (
        ParamResolver._status_flag_value(status_paths=bit_paths, flag_condition="t.INVISIBLE", flat_values={"P5.s0": "x"}) is None
    )
    assert ParamResolver._status_flag_value(status_paths=bit_paths, flag_condition="other", flat_values={"P5.s0": 4}) is None

    rule_paths: list[dict[str, Any]] = [
        {
            "condition": "t.AVAILABLE",
            "if": [
                {
                    "expected": 1,
                    "operation": "e.equalTo",
                    "value": [{"group": "P1", "number": 0, "use": "v"}],
                }
            ],
            "then": "true",
            "else": "0",
        }
    ]
    assert (
        ParamResolver._status_flag_value(status_paths=rule_paths, flag_condition="t.AVAILABLE", flat_values={"P1.v0": 1}) is True
    )
    assert (
        ParamResolver._status_flag_value(status_paths=rule_paths, flag_condition="t.AVAILABLE", flat_values={"P1.v0": 0}) is False
    )
    assert ParamResolver._to_bool_value(True) is True
    assert ParamResolver._to_bool_value(0) is False
    assert ParamResolver._to_bool_value("!0") is True
    assert ParamResolver._to_bool_value("!1") is False
    assert ParamResolver._to_bool_value("maybe") is None


def test_format_channels_and_status_helpers() -> None:
    """Format path/status/flag payloads and extract mapping rule inputs/values."""
    channels = ParamResolver._format_channels(
        {
            "value": [{"group": "P4", "number": "3", "use": "value", "bit": 1}],
            "status": "skip",
            "empty": [{"group": "P4"}],
        }
    )
    assert channels["value"][0]["address"] == "P4.v3"
    assert channels["value"][0]["bit"] == 1
    assert ParamResolver._format_channels("bad") == {}

    conditions = ParamResolver._format_status_conditions({"t.INVISIBLE": [{"group": "P5", "index": 1, "use": "s"}]})
    assert "INVISIBLE" in conditions
    assert conditions["INVISIBLE"][0]["condition"] == "INVISIBLE"
    assert ParamResolver._format_status_conditions(None) == {}

    flags = ParamResolver._format_status_flags(["t.INVISIBLE", {"name": "e.ON"}, 3])
    assert flags[0] == "INVISIBLE"
    assert flags[1] == {"name": "ON"}
    assert flags[2] == 3

    inputs = ParamResolver._extract_mapping_rule_inputs(
        {
            "rules": [
                "skip",
                {
                    "conditions": [
                        {
                            "targets": [
                                {"address": "P1.v0", "bit": 2},
                                {"address": "P1.v0", "bit": 2},
                                {"address": ""},
                            ]
                        }
                    ]
                },
            ],
            "any": [
                {
                    "if": [
                        {
                            "value": [
                                {"group": "P2", "number": 4, "use": "s", "mask": 15},
                                {"group": "P2", "number": "x", "use": "s"},
                            ]
                        }
                    ]
                }
            ],
            "paths": {
                "value": [
                    {
                        "elseif": [
                            {"value": [{"group": "P3", "number": 1, "use": "v"}]},
                        ]
                    }
                ]
            },
        }
    )
    assert inputs == [
        {"address": "P1.v0", "bit": 2},
        {"address": "P2.s4", "mask": 15},
        {"address": "P3.v1"},
    ]
    assert ParamResolver._extract_mapping_rule_inputs("bad") == []
    assert ParamResolver._extract_mapping_rule_values({"rules": [{"value": "e.ON"}, {"value": "e.ON"}, {"value": 1}]}) == ["e.ON"]
    assert ParamResolver._extract_mapping_rule_values([]) == []


def test_mapping_primary_address_aliases_and_symbol_fallback() -> None:
    """Prefer value/status channels and fall back to PARAM_/STATUS_ symbol pools."""
    assert ParamResolver._mapping_primary_address({"group": "P4", "number": 2, "use": "value"}) == ("P4", "v", 2)
    assert ParamResolver._mapping_primary_address({"pool": 5, "index": "3", "path": "status"}) == ("P5", "s", 3)
    assert ParamResolver._mapping_primary_address({"group": "P1", "idx": 0, "chan": "[t.BIT]"}) == ("P1", "s", 0)
    assert ParamResolver._mapping_primary_address({"group": "P1", "number": 0, "use": "minValue"}) == ("P1", "n", 0)
    assert ParamResolver._mapping_primary_address({"group": "P1", "number": 0, "use": "weird"}) == ("P1", "w", 0)
    assert ParamResolver._mapping_primary_address({}, symbol="PARAM_P8_12") == ("P8", "v", 12)
    assert ParamResolver._mapping_primary_address({}, symbol="STATUS_P9_4") == ("P9", "s", 4)
    assert ParamResolver._mapping_primary_address({}, symbol="OTHER") is None
    assert ParamResolver._mapping_canonical_address("STATUS_P2_7", None) == ("P2", "s", 7)


def test_panel_route_diagnostics_from_menu_explains_accept_and_reject() -> None:
    """Report accepted routes, missing symbols, and non-module-item exclusions."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "boiler",
                    "name": "modules.menu.boiler",
                    "meta": {
                        "displayName": "Boiler",
                        "parameters": {"read": [{"parameter": "E(A.READ,'PARAM_1')"}]},
                    },
                    "children": [
                        {
                            "path": "empty-child",
                            "name": "modules.menu.empty",
                            "meta": {"displayName": "Empty"},
                        }
                    ],
                },
                {
                    "path": "modules",
                    "name": "routes.modules.menu.modules",
                    "meta": {
                        "displayName": "Modules",
                        "parameters": {"read": [{"parameter": "E(A.READ,'PARAM_9')"}]},
                    },
                },
            ]
        }
    )

    core = ParamResolver.panel_route_diagnostics_from_menu(menu, all_panels=False)
    by_path = {row["path"]: row for row in core}
    assert by_path["boiler"]["accepted"] is True
    assert by_path["boiler"]["reason"] == "accepted"
    assert by_path["empty-child"]["accepted"] is False
    assert by_path["empty-child"]["reason"] == "rejected:no-symbols"
    assert by_path["empty-child"]["panel_title"] == "Boiler/Empty"
    assert by_path["modules"]["accepted"] is True

    all_panels = ParamResolver.panel_route_diagnostics_from_menu(menu, all_panels=True)
    all_by_path = {row["path"]: row for row in all_panels}
    assert all_by_path["modules"]["accepted"] is False
    assert all_by_path["modules"]["reason"] == "rejected:not-module-item"
    assert all_by_path["empty-child"]["reason"] == "rejected:no-symbols"


def test_lookup_route_title_and_unit_label_fallbacks() -> None:
    """Cover dotted i18n lookup, route-title fallbacks, and unit value labels."""
    from types import SimpleNamespace

    evaluator = _evaluator()
    assert evaluator._read_address_value("not-an-address") is None
    assert evaluator.evaluate({"value": [{"if": [{"operation": "equalTo", "expected": 1, "value": []}], "then": "x"}]}) is None

    assert ParamResolver._lookup_dotted_path({}, "") is None
    assert ParamResolver._lookup_dotted_path({"a": {"b": "  "}}, "a.b") is None
    assert ParamResolver._lookup_dotted_path({"a": "leaf"}, "a.b") is None
    assert ParamResolver._lookup_dotted_path_raw({"a": {"b": "  "}}, "a.b") == "  "
    assert ParamResolver._lookup_dotted_path_raw({}, "") is None
    assert ParamResolver._lookup_dotted_path_raw({"a": 1}, "a.b") is None

    named = SimpleNamespace(
        name="modules.menu.boiler",
        path="boiler",
        meta=SimpleNamespace(display_name="routes.modules.menu.boiler"),
    )
    assert ParamResolver._route_title(named, routes_i18n={"modules": {"menu": {"boiler": "Kocioł"}}}) == "Kocioł"
    assert ParamResolver._route_title(SimpleNamespace(name="modules.menu.x", path="x", meta=None)) == "modules.menu.x"
    assert ParamResolver._route_title(SimpleNamespace(name="", path="fallback", meta=None)) == "fallback"

    mainmenu = SimpleNamespace(
        name="MAINMENU_MENU_TERMOSTATU",
        path="thermostats",
        meta=SimpleNamespace(display_name="MAINMENU_MENU_TERMOSTATU"),
    )
    assert (
        ParamResolver._route_title(
            mainmenu,
            routes_i18n={"MAINMENU_MENU_TERMOSTATU": "Menu termostatów"},
        )
        == "Menu termostatów"
    )
    dhw = SimpleNamespace(
        name="modules.menu.dhw",
        path="dhw",
        meta=SimpleNamespace(display_name="MAINMENU_USTAWIENIA_CWU"),
    )
    assert (
        ParamResolver._route_title(
            dhw,
            routes_i18n={"MAINMENU_USTAWIENIA_CWU": "Ustawienia CWU", "modules": {"menu": {}}},
        )
        == "Ustawienia CWU"
    )
    child = SimpleNamespace(
        name="modules.menu.thermostat.pump",
        path="pump",
        meta=SimpleNamespace(display_name="routes.modules.menu.thermostat.pump"),
    )
    assert (
        ParamResolver._panel_title_hierarchical(
            route=child,
            ancestors=(mainmenu,),
            routes_i18n={
                "MAINMENU_MENU_TERMOSTATU": "Menu termostatów",
                "modules": {"menu": {"thermostat": {"pump": "Pompa CO"}}},
            },
        )
        == "Menu termostatów/Pompa CO"
    )

    # Missed i18n lookups fall through to the raw display name / route name.
    assert (
        ParamResolver._route_title(
            SimpleNamespace(
                name="modules.menu.dhw",
                path="dhw",
                meta=SimpleNamespace(display_name="routes.modules.menu.missing"),
            ),
            routes_i18n={"modules": {"menu": {}}},
        )
        == "routes.modules.menu.missing"
    )
    assert (
        ParamResolver._route_title(
            SimpleNamespace(
                name="modules.menu.dhw",
                path="dhw",
                meta=SimpleNamespace(display_name="UNKNOWN_TOKEN"),
            ),
            routes_i18n={"modules": {"menu": {}}},
        )
        == "UNKNOWN_TOKEN"
    )
    assert (
        ParamResolver._route_title(
            SimpleNamespace(name="modules.menu.missing", path="x", meta=None),
            routes_i18n={"modules": {"menu": {}}},
        )
        == "modules.menu.missing"
    )
    assert (
        ParamResolver._route_title(
            SimpleNamespace(name="   ", path="fallback-path", meta=None),
            routes_i18n={},
        )
        == "fallback-path"
    )

    # Non-string name/display candidates are skipped while collecting tokens.
    junk_menu = SimpleNamespace(
        routes=[
            SimpleNamespace(name=123, meta=SimpleNamespace(display_name=None), children=[]),
            SimpleNamespace(name="MAINMENU_OK", meta=SimpleNamespace(display_name=99), children=[]),
            SimpleNamespace(name="DHW", meta=SimpleNamespace(display_name="CWU"), children=[]),
        ]
    )
    assert ParamResolver._collect_menu_title_tokens(cast(MenuResult, junk_menu)) == {"MAINMENU_OK"}

    assert ParamResolver._string_namespace_title("MAINMENU_X", {"MAINMENU_X": "Title"}) == "Title"
    assert ParamResolver._string_namespace_title("MAINMENU_X", {"__default__": "Title"}) == "Title"
    assert ParamResolver._string_namespace_title("MAINMENU_X", {"other": "Title"}) == "Title"
    assert ParamResolver._string_namespace_title("MAINMENU_X", {"a": "1", "b": "2"}) is None
    assert ParamResolver._string_namespace_title("MAINMENU_X", {"MAINMENU_X": "  "}) is None

    assert ParamResolver._route_allowed_in_module_item(SimpleNamespace(name=None)) is False
    assert ParamResolver._route_allowed_in_module_item(SimpleNamespace(name="other.item")) is False
    assert ParamResolver._route_allowed_in_module_item(SimpleNamespace(name="companies.modules.menu.x")) is True
    assert ParamResolver._route_allowed_in_module_item(SimpleNamespace(name="MAINMENU_USTAWIENIA_KOTLA")) is True
    assert ParamResolver._route_allowed_in_module_item(SimpleNamespace(name="MENUSERWIS_USTAWIENIA_ROZPALANIA")) is True
    assert ParamResolver._route_allowed_in_module_item(SimpleNamespace(name="routes.modules.menu.modules")) is False
    assert ParamResolver._route_allowed_in_module_item(SimpleNamespace(name="   ")) is False
    assert ParamResolver._route_allowed_in_module_item(SimpleNamespace(name="other.menu.item")) is False
    assert ParamResolver._route_allowed_in_module_item(SimpleNamespace(name="modules.menu.boiler")) is True

    assert ParamResolver._to_float_literal("") is None
    assert ParamResolver._to_float_literal(".5") == 0.5
    assert ParamResolver._to_float_literal("-.5") == -0.5
    assert ParamResolver._to_float_literal("nope") is None
    assert ParamResolver._apply_numeric_transform(3, "e => e * 0.5") == 1.5

    assert ParamResolver._clean_symbolic_tag(1) is None
    assert ParamResolver._clean_symbolic_tag("   ") is None
    assert ParamResolver._clean_symbolic_tag("[t.INVISIBLE]") == "INVISIBLE"

    assert ParamResolver._unit_mapping_value_label("C", 1) is None
    assert ParamResolver._unit_mapping_value_label({"1": "On", "e.OFF": "Off"}, "1") == "On"
    assert ParamResolver._unit_mapping_value_label({"1": "On"}, True) == "On"
    assert ParamResolver._unit_mapping_value_label({"2.0": "Two"}, 2.0) == "Two"
    assert ParamResolver._unit_mapping_value_label({"e.AUTO": "Auto"}, "[e.AUTO]") == "Auto"
    assert ParamResolver._unit_mapping_value_label({"x": "  "}, "missing") is None
    assert (
        ParamResolver._unit_mapping_value_label(
            {"BoilerState['STOP']": "app.one.burnerState.0", "BoilerState['WORK']": "app.one.boilerStatus.1"},
            "STOP",
        )
        == "app.one.burnerState.0"
    )
    assert (
        ParamResolver._unit_mapping_value_label(
            {'BoilerState["WORK"]': "app.one.boilerStatus.1"},
            "WORK",
        )
        == "app.one.boilerStatus.1"
    )
    assert ParamResolver._unit_options_map("C") is None
    assert ParamResolver._unit_options_map({"options": {"0": "Off"}}) == {"0": "Off"}
    assert ParamResolver._unit_options_map({"text": "x", "0": "Off"}) is None
    assert ParamResolver._unit_options_map({"0": "Off"}) == {"0": "Off"}
