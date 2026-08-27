"""Offline tests for ``scripts/live_contract.py``."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from pybragerone.models.catalog import ParamMap

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "live_contract.py"


class _LiveContractScript(Protocol):
    """Subset of ``live_contract`` used by tests (attribute callables — no Ellipsis bodies)."""

    parse_modules: Callable[[str | None], list[str]]
    classify_path_kind: Callable[[Any], str]
    normalize_selector: Callable[[Mapping[str, Any]], dict[str, Any]]
    symbol_contract: Callable[..., dict[str, Any]]
    build_contract: Callable[..., dict[str, Any]]
    compare_contracts: Callable[[Mapping[str, Any], Mapping[str, Any]], list[str]]
    unified_diff_lines: Callable[[Sequence[str]], list[str]]
    format_diff_markdown: Callable[..., str]
    write_diff_files: Callable[[Path, Sequence[str]], None]
    collect_symbol_tokens: Callable[[Mapping[str, object], Sequence[str]], list[str]]
    write_json: Callable[[Path, Mapping[str, Any]], None]
    read_json: Callable[[Path], dict[str, Any]]


def _load() -> _LiveContractScript:
    """Import the script module by path (not a package)."""
    spec = importlib.util.spec_from_file_location("live_contract", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(_LiveContractScript, module)


def _param_map(
    *,
    key: str = "PARAM_P4_59",
    group: str | None = "P4",
    component_type: str | None = "number",
    value: list[dict[str, Any]] | None = None,
    units: int | str | None = 1,
    status_conditions: dict[str, list[dict[str, Any]]] | None = None,
    command_rules: list[dict[str, Any]] | None = None,
) -> ParamMap:
    """Build a minimal ParamMap for contract tests."""
    if value is None:
        value = [
            {"group": "P4", "number": 59, "use": "v", "convert": "_0xdead"},
            {"group": "P4", "number": 60, "use": "v", "convert": "_0xbeef", "times": 65536},
        ]
    return ParamMap(
        key=key,
        group=group,
        paths={
            "value": value,
            "unit": [],
            "status": [],
            "command": [],
            "min": [],
            "max": [],
        },
        component_type=component_type,
        units=units,
        limits=None,
        status_flags=[],
        status_conditions=status_conditions,
        command_rules=command_rules or [],
        origin="inline:test",
        raw={"value": value, "units": units},
    )


def test_parse_modules_sorts_unique() -> None:
    """Module env lists are sorted and de-duplicated."""
    parse = _load().parse_modules
    assert parse("B, A, B") == ["A", "B"]
    assert parse(None) == []
    assert parse("  ") == []


def test_classify_path_kind_status_vs_selector() -> None:
    """Status rules and address selectors are distinguished."""
    classify = _load().classify_path_kind
    assert classify([]) == "empty"
    assert classify(None) == "empty"
    assert (
        classify(
            [
                {"group": "P4", "number": 59, "use": "v"},
                {"group": "P4", "number": 60, "use": "v", "times": 65536},
            ]
        )
        == "address_selector"
    )
    assert classify([{"if": "x", "then": "y"}]) == "status_rules"


def test_normalize_selector_converts_helper_to_bool() -> None:
    """Minified convert helper names collapse to a boolean presence flag."""
    normalize = _load().normalize_selector
    assert normalize({"group": "P4", "number": 59, "use": "v", "convert": "_0xabc", "times": 65536}) == {
        "group": "P4",
        "number": 59,
        "use": "v",
        "convert": True,
        "times": 65536,
    }


def test_normalize_selector_collapses_integer_valued_floats() -> None:
    """Integer-valued floats must not churn baselines as float vs int."""
    normalize = _load().normalize_selector
    assert normalize({"group": "P4", "number": 59.0, "use": "v", "times": 65536.0}) == {
        "group": "P4",
        "number": 59,
        "use": "v",
        "times": 65536,
    }
    assert normalize({"group": "P4", "number": 1, "use": "v", "times": 1.5}) == {
        "group": "P4",
        "number": 1,
        "use": "v",
        "times": 1.5,
    }


def test_symbol_contract_multi_word_and_flags() -> None:
    """Multi-word compose mappings expose structural flags without live values."""
    module = _load()
    entry = module.symbol_contract(_param_map(), units_i18n_ok=True, units_descriptor_ok=False)
    assert entry["multi_word"] is True
    assert entry["has_status_rules"] is False
    assert entry["path_kinds"]["value"] == "address_selector"
    assert entry["paths"]["value"][1]["times"] == 65536
    assert entry["paths"]["value"][0]["convert"] is True
    assert entry["units_i18n_ok"] is True
    assert entry["units_descriptor_ok"] is False


def test_symbol_contract_status_rules() -> None:
    """STATUS-style value rules set has_status_rules and path kind."""
    module = _load()
    mapping = _param_map(value=[{"if": "online", "then": 1}, {"else": 0}])
    entry = module.symbol_contract(mapping)
    assert entry["has_status_rules"] is True
    assert entry["multi_word"] is False
    assert entry["path_kinds"]["value"] == "status_rules"
    assert entry["paths"]["value"] == 2


def test_collect_symbol_tokens() -> None:
    """Only known symbol prefixes are collected and sorted."""
    collect = _load().collect_symbol_tokens
    tokens = collect(
        {"PARAM_66": object(), "module.menu": object(), "STATUS_FOO": object()},
        ["COMMAND_MODULE_RESTART", "noise", "PARAM_66"],
    )
    assert tokens == ["COMMAND_MODULE_RESTART", "PARAM_66", "STATUS_FOO"]


def test_compare_contracts_match() -> None:
    """Identical contracts produce no diffs."""
    module = _load()
    symbols = {"PARAM_P4_59": module.symbol_contract(_param_map())}
    contract = module.build_contract(
        lang="en",
        object_id=1,
        modules=["MOD"],
        fingerprint="2.08|index-x.js",
        symbols=symbols,
    )
    assert module.compare_contracts(contract, contract) == []


def test_compare_contracts_ignores_fingerprint() -> None:
    """Index-asset rebuilds are metadata, not structural drift."""
    module = _load()
    symbols = {"PARAM_P4_59": module.symbol_contract(_param_map())}
    left = module.build_contract(
        lang="en",
        object_id=1,
        modules=["MOD"],
        fingerprint="1.03.07|index-old.js",
        symbols=symbols,
    )
    right = module.build_contract(
        lang="en",
        object_id=1,
        modules=["MOD"],
        fingerprint="1.03.08|index-new.js",
        symbols=symbols,
    )
    assert module.compare_contracts(left, right) == []


def test_command_rules_collapse_minified_idents() -> None:
    """Minified SPA identifiers in command expressions must not churn the baseline."""
    module = _load()
    entry = module.symbol_contract(
        _param_map(
            command_rules=[
                {
                    "command": "ModuleCommands['TEST_MODE_'+_0x444f82+'_OFF']",
                    "conditions": [{"operation": "equalTo"}],
                }
            ]
        )
    )
    assert entry["command_rules"] == [{"command": "ModuleCommands['TEST_MODE_'+_0xMINIFIED+'_OFF']", "operations": ["equalTo"]}]


def test_compare_contracts_detects_removed_symbol_and_times_change() -> None:
    """Removed symbols and times/component_type drift are reported."""
    module = _load()
    baseline_symbols = {
        "PARAM_P4_59": module.symbol_contract(_param_map()),
        "PARAM_66": module.symbol_contract(_param_map(key="PARAM_66", value=[{"group": "P6", "number": 66, "use": "v"}])),
    }
    baseline = module.build_contract(
        lang="en",
        object_id=1,
        modules=["MOD"],
        fingerprint="2.08|index-x.js",
        symbols=baseline_symbols,
    )
    current_symbols = {
        "PARAM_P4_59": module.symbol_contract(
            _param_map(
                component_type="text",
                value=[
                    {"group": "P4", "number": 59, "use": "v", "convert": "_0xdead"},
                    {"group": "P4", "number": 60, "use": "v", "convert": "_0xbeef", "times": 1},
                ],
            )
        ),
    }
    current = module.build_contract(
        lang="en",
        object_id=1,
        modules=["MOD"],
        fingerprint="2.08|index-x.js",
        symbols=current_symbols,
    )
    diffs = module.compare_contracts(baseline, current)
    assert any(item.startswith("- symbols.PARAM_66") or item == "- symbols.PARAM_66" for item in diffs)
    assert any("times" in item for item in diffs)
    assert any("component_type" in item for item in diffs)


def test_seed_baseline_roundtrip(tmp_path: Path) -> None:
    """Missing baseline is written; a second read matches the snapshot."""
    module = _load()
    symbols = {"PARAM_P4_59": module.symbol_contract(_param_map())}
    contract = module.build_contract(
        lang="en",
        object_id=42,
        modules=["A", "B"],
        fingerprint="2.08|index-x.js",
        symbols=symbols,
    )
    baseline = tmp_path / "live_contract.json"
    assert not baseline.is_file()
    module.write_json(baseline, contract)
    loaded = module.read_json(baseline)
    assert module.compare_contracts(loaded, contract) == []
    assert loaded["symbol_count"] == 1
    assert json.loads(baseline.read_text(encoding="utf-8"))["object_id"] == 42


def test_status_kind_drift_fails_compare() -> None:
    """Changing path kind from address_selector to status_rules is a diff."""
    module = _load()
    baseline = module.build_contract(
        lang="en",
        object_id=1,
        modules=["MOD"],
        fingerprint=None,
        symbols={"PARAM_X": module.symbol_contract(_param_map(key="PARAM_X"))},
    )
    current = module.build_contract(
        lang="en",
        object_id=1,
        modules=["MOD"],
        fingerprint=None,
        symbols={
            "PARAM_X": module.symbol_contract(
                _param_map(key="PARAM_X", value=[{"if": "a", "then": 1}]),
            )
        },
    )
    diffs = module.compare_contracts(baseline, current)
    assert any("path_kinds" in item or "has_status_rules" in item for item in diffs)


def test_unified_diff_lines_pairs_scalar_and_length_changes() -> None:
    """Scalar and list-length rows become minus/plus pairs for GitHub ``diff`` fences."""
    unified = _load().unified_diff_lines(
        [
            "+ symbols.PARAM_NEW",
            "- symbols.PARAM_OLD",
            "~ symbols.PARAM_X.component_type: 'number' -> 'text'",
            "~ symbols.PARAM_X.paths.value length 2 -> 1",
        ]
    )
    assert unified == [
        "+ symbols.PARAM_NEW",
        "- symbols.PARAM_OLD",
        "- symbols.PARAM_X.component_type: 'number'",
        "+ symbols.PARAM_X.component_type: 'text'",
        "- symbols.PARAM_X.paths.value length: 2",
        "+ symbols.PARAM_X.paths.value length: 1",
    ]


def test_format_diff_markdown_empty_and_fence() -> None:
    """Drift comments wrap a unified listing; equal contracts produce no section."""
    module = _load()
    assert module.format_diff_markdown([]) == ""
    markdown = module.format_diff_markdown(
        [
            "+ symbols.PARAM_NEW",
            "~ symbols.PARAM_X.units_raw: 1 -> 2",
        ]
    )
    assert markdown.startswith("### Structural diffs (2)")
    assert "```diff" in markdown
    assert "--- baseline" in markdown
    assert "+++ current" in markdown
    assert "+ symbols.PARAM_NEW" in markdown
    assert "- symbols.PARAM_X.units_raw: 1" in markdown
    assert "+ symbols.PARAM_X.units_raw: 2" in markdown
    assert "truncated" not in markdown


def test_format_diff_markdown_truncates_to_budget() -> None:
    """Issue comments stay under GitHub's body cap by dropping trailing diffs."""
    module = _load()
    diffs = [f"+ symbols.PARAM_{index:04d}" for index in range(40)]
    markdown = module.format_diff_markdown(diffs, max_chars=400)
    assert "truncated" in markdown
    assert "PARAM_0000" in markdown
    assert "PARAM_0039" not in markdown
    assert markdown.endswith("```\n")


def test_write_diff_files_writes_listing_and_markdown(tmp_path: Path) -> None:
    """``--write-diffs`` emits the full listing plus a sibling markdown comment body."""
    module = _load()
    listing = tmp_path / "diffs.txt"
    module.write_diff_files(listing, ["+ symbols.PARAM_NEW", "- symbols.PARAM_OLD"])
    assert listing.read_text(encoding="utf-8") == "+ symbols.PARAM_NEW\n- symbols.PARAM_OLD\n"
    markdown = listing.with_suffix(".md").read_text(encoding="utf-8")
    assert "```diff" in markdown
    assert "+ symbols.PARAM_NEW" in markdown
    module.write_diff_files(listing, [])
    assert listing.read_text(encoding="utf-8") == ""
    assert listing.with_suffix(".md").read_text(encoding="utf-8") == ""
