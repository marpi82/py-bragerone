"""Tests for evaluating rule-based computed STATUS assets.

These assets encode a chain of if/elseif rules that depend on several register
values (P?.s* bits/masks, P?.v* modes). We do not test full BragerOne assets here;
we only validate that our lightweight evaluator can:

- read referenced addresses from ParamStore
- apply bit and mask extraction
- match conditions and return the normalized computed value
"""

from __future__ import annotations

from pybragerone.models import ComputedValueEvaluator, ParamStore


def test_evaluate_computed_status_any_rules_bit_and_mask() -> None:
    """Evaluate a rule chain using bit and mask extraction."""
    store = ParamStore()
    evaluator = ComputedValueEvaluator(store)
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

    assert evaluator.evaluate(raw) == "WORK"


def test_evaluate_computed_status_returns_none_without_values() -> None:
    """Return None if the evaluator lacks required input values."""
    store = ParamStore()
    evaluator = ComputedValueEvaluator(store)
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
    assert evaluator.evaluate(raw) is None


def test_evaluate_computed_status_paths_value_rules_enum_output() -> None:
    """Evaluate enum-like outputs from `paths.value` rule lists."""
    store = ParamStore()
    evaluator = ComputedValueEvaluator(store)
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

    assert evaluator.evaluate(raw) == "e.ON"


def test_evaluate_inline_status_clause_operation_enum_members() -> None:
    """Index-inline STATUS factories leave ClauseOperation/DiodeState enum leftovers.

    Dedicated STATUS_*.js assets emit cleaned ``equalTo`` / ``ON`` tokens. The same
    rules parsed from the index as ``ClauseOperation['equalTo']`` and
    ``DiodeState['OFF']`` must still match bits and normalize to the public tag.
    """
    store = ParamStore()
    evaluator = ComputedValueEvaluator(store)
    # bit 1 clear → OFF branch (same shape as STATUS_P5_10 / STATUS_P5_11)
    store.upsert("P5.s10", 1)  # bit 0 only
    store.upsert("P5.s11", 1)
    store.upsert("P5.s20", 1)  # mask 30 → 0 → DISABLED

    diode_paths = {
        "value": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "ClauseOperation['equalTo']",
                        "value": [{"group": "P5", "number": 10, "use": "s", "bit": 1}],
                    }
                ],
                "then": "DiodeState['ON']",
            },
            {
                "elseif": [
                    {
                        "expected": 0,
                        "operation": "ClauseOperation['equalTo']",
                        "value": [{"group": "P5", "number": 10, "use": "s", "bit": 1}],
                    }
                ],
                "then": "DiodeState['OFF']",
            },
            {"else": None},
        ]
    }
    assert evaluator.evaluate(diode_paths) == "OFF"

    pump_any = {
        "any": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "ClauseOperation['equalTo']",
                        "value": [{"group": "P5", "number": 11, "use": "s", "bit": 1}],
                    }
                ],
                "then": {"value": "DiodeState['ON']"},
            },
            {
                "elseif": [
                    {
                        "expected": 0,
                        "operation": "ClauseOperation['equalTo']",
                        "value": [{"group": "P5", "number": 11, "use": "s", "bit": 1}],
                    }
                ],
                "then": {"value": "DiodeState['OFF']"},
            },
            {"else": None},
        ]
    }
    assert evaluator.evaluate(pump_any) == "OFF"

    valve_paths = {
        "value": [
            {
                "if": [
                    {
                        "expected": 7,
                        "operation": "ClauseOperation['equalTo']",
                        "value": [{"group": "P5", "number": 20, "use": "s", "mask": 7}],
                    }
                ],
                "then": "ThreeWayValveState['CLOSING']",
            },
            {
                "elseif": [
                    {
                        "expected": 0,
                        "operation": "ClauseOperation['equalTo']",
                        "value": [{"group": "P5", "number": 20, "use": "s", "mask": 30}],
                    }
                ],
                "then": "ThreeWayValveState['DISABLED']",
            },
            {"else": None},
        ]
    }
    assert evaluator.evaluate(valve_paths) == "DISABLED"
