"""Tests for evaluating rule-based computed STATUS assets.

These assets encode a chain of if/elseif rules that depend on several register
values (P?.s* bits/masks, P?.v* modes). We do not test full BragerOne assets here;
we only validate that our lightweight evaluator can:

- read referenced addresses from ParamStore
- apply bit and mask extraction
- match conditions and return the normalized computed value
"""

from __future__ import annotations

from pybragerone.models.param import ParamStore


def test_evaluate_computed_status_any_rules_bit_and_mask() -> None:
    """Evaluate a rule chain using bit and mask extraction."""
    store = ParamStore()
    # P5.s4 bit 5 == 1
    store.upsert("P5.s4", 1 << 5)
    # P5.s5 masked with 0x0F00 equals 0x0300
    store.upsert("P5.s5", 0x0300)
    # P6.v13 equals 0
    store.upsert("P6.v13", 0)

    raw = {
        "any": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 4, "use": "s", "bit": 5}],
                    },
                    {
                        "expected": 0,
                        "operation": "equalTo",
                        "value": [{"group": "P6", "number": 13, "use": "v"}],
                    },
                    {
                        "expected": 0x0300,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 5, "use": "s", "mask": 0x0F00}],
                    },
                ],
                "then": {"value": "o.WORK"},
            }
        ]
    }

    assert store._evaluate_computed_value(raw) == "WORK"


def test_evaluate_computed_status_returns_none_without_values() -> None:
    """Return None if the evaluator lacks required input values."""
    store = ParamStore()
    raw = {
        "any": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 0, "use": "s", "bit": 0}],
                    }
                ],
                "then": {"value": "STOP"},
            }
        ]
    }
    assert store._evaluate_computed_value(raw) is None


def test_evaluate_computed_status_paths_value_rules_enum_output() -> None:
    """Evaluate enum-like outputs from `paths.value` rule lists."""
    store = ParamStore()
    # P5.s13 has bit 1 set
    store.upsert("P5.s13", 1 << 1)

    raw = {
        "paths": {
            "value": [
                {
                    "if": [
                        {
                            "expected": 1,
                            "operation": "t.equalTo",
                            "value": [{"bit": 1, "group": "P5", "number": 13, "use": "s"}],
                        }
                    ],
                    "then": "e.ON",
                },
                {
                    "if": [
                        {
                            "expected": 0,
                            "operation": "t.equalTo",
                            "value": [{"bit": 1, "group": "P5", "number": 13, "use": "s"}],
                        }
                    ],
                    "then": "e.OFF",
                },
            ]
        }
    }

    assert store._evaluate_computed_value(raw) == "e.ON"
