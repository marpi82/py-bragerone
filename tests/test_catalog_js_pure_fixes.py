"""Coverage + regressions for pure JS parser parity fixes (#489 / #355)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from pybragerone.models.catalog import (
    LiveAssetsCatalog,
    _array_map_method,
    _Parser,
    _public_token_from_helper_args,
    extract_root_export,
    extract_root_object,
    make_object_factory,
    string_value,
)


def test_string_value_template_interpolates_and_keeps_unknown() -> None:
    """Backtick bodies substitute known idents and leave unknown ``${…}`` intact."""
    assert string_value("`parameters.STATUS_P5_${n}`", bindings={"n": 10}) == "parameters.STATUS_P5_10"
    assert string_value("`x_${missing}`", bindings={"n": 1}) == "x_${missing}"
    assert string_value("plain") == "plain"
    assert string_value("") == ""


def test_public_token_from_helper_args_shapes() -> None:
    """Obfuscated helper collapse covers 1-arg / 2-arg success and reject paths."""
    assert _public_token_from_helper_args("_0xabc", ["PARAM_1"]) == "PARAM_1"
    assert _public_token_from_helper_args("_0xabc", ["WRITE", "PARAM_45"]) == "PARAM_45"
    assert _public_token_from_helper_args("readable", ["PARAM_1"]) is None
    assert _public_token_from_helper_args("_0xabc", ["not-a-token"]) is None
    assert _public_token_from_helper_args("_0xabc", []) is None
    assert _public_token_from_helper_args("_0xabc", ["NOPE", "PARAM_1"]) is None
    assert _public_token_from_helper_args("_0xabc", ["WRITE", 12]) is None
    # Two-arg helpers must not collapse DISPLAY_*.
    assert _public_token_from_helper_args("_0xabc", ["WRITE", "DISPLAY_PARAMETER_LEVEL_1"]) is None


def test_bang_leftover_and_does_not_invent_value_path() -> None:
    """``![] && [path]`` stays unevaluable leftover."""
    value = _Parser("![] && [{group:'P6', number:1, use:'v'}]").parse_value()
    assert isinstance(value, str)
    assert value.startswith("![]")
    parser = _Parser("")
    assert parser._is_unevaluable_leftover(0) is False
    assert parser._is_unevaluable_leftover("   ") is False
    assert parser._is_unevaluable_leftover("!1") is True
    assert _Parser("!1 || fallback").parse_value() == "!1||fallback"


def test_divide_by_zero_keeps_source_text() -> None:
    """``1/0`` / ``1%0`` must not raise; keep source-like leftover."""
    assert _Parser("1/0").parse_value() == "1/0"
    assert _Parser("1%0").parse_value() == "1%0"
    assert extract_root_export(b"export default {a: 1/0}") == {"a": "1/0"}


def test_comma_operator_in_paren_keeps_last_expr_for_helper_call() -> None:
    """``(0, _0xabc)('PARAM_45')`` collapses to PARAM_45 like SPA IIFE helpers."""
    assert _Parser("(0,_0xabc)('PARAM_45')").parse_value() == "PARAM_45"


def test_array_map_method_success_failure_and_non_callable() -> None:
    """``array['map']`` keeps receiver tokens when the callback is unusable."""
    mapped = _array_map_method(["PARAM_1", "PARAM_2"])

    assert mapped(lambda item: {"parameter": item}) == [
        {"parameter": "PARAM_1"},
        {"parameter": "PARAM_2"},
    ]

    def _boom(_item: Any) -> Any:
        raise RuntimeError("nope")

    assert mapped(_boom) == ["PARAM_1", "PARAM_2"]
    assert mapped("not-callable") == ["PARAM_1", "PARAM_2"]
    assert mapped(list) == ["PARAM_1", "PARAM_2"]


def test_skip_one_value_span_covers_shapes() -> None:
    """Depth-limit skip path advances past objects, strings, numbers, idents, and junk."""
    cases = [
        ('{"a":1}', 7),
        ("[1,2]", 5),
        ("(1)", 3),
        ('"hi"', 4),
        ("`x`", 3),
        ("-12", 3),
        ("0x10", 4),
        ("fooBar", 6),
        ("@", 1),
        ("!", 1),
    ]
    for source, _expected_min in cases:
        parser = _Parser(source)
        start = parser.i
        parser._skip_one_value_span()
        assert parser.i > start, source

    # Empty input: ``if ch:`` false branch (no advance).
    empty = _Parser("")
    empty._skip_one_value_span()
    assert empty.i == 0


def test_parse_value_depth_limit_degrades() -> None:
    """Explicit depth ceiling degrades without raising."""
    parser = _Parser("[1]")
    parser._depth = 10_000
    assert parser.parse_value() is None


def test_non_string_callee_call_does_not_collapse_helper() -> None:
    """Numeric callees take the non-string leftover branch (branch coverage)."""
    parser = _Parser("1('WRITE','PARAM_9')")
    assert parser.parse_value() == "('WRITE','PARAM_9')"


def test_extract_root_recursion_guards_are_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Outer RecursionError guards stay defensive even when depth limit is bypassed."""

    def _boom(_code: bytes) -> Any:
        raise RecursionError

    monkeypatch.setattr("pybragerone.models.catalog.collect_bindings", _boom)
    assert extract_root_export(b"export default {}") is None

    def _boom_export(_code: bytes) -> Any:
        raise RecursionError

    monkeypatch.setattr("pybragerone.models.catalog.extract_root_export", _boom_export)
    assert extract_root_object(b"export default {}") is None


def test_pure_optional_chain_or_fallback_fills_minmax_paths() -> None:
    """Production pure path: ``_0x?.['minValue']||[{…}]`` must become paths.min/max (#329)."""
    code = b"""
    export default {
      PARAM_TEST: {
        value: [{group: 'P6', number: 1, use: 'v'}],
        minValue: _0x39dd22?.['minValue']||[{group: 'P6', number: 42, use: 'n'}],
        maxValue: _0x39dd22?.['maxValue']||[{group: 'P6', number: 42, use: 'x'}],
      }
    };
    """
    root = extract_root_export(code)
    assert isinstance(root, dict)
    param_obj = root["PARAM_TEST"]
    assert isinstance(param_obj, dict)
    assert param_obj["minValue"] == [{"group": "P6", "number": 42, "use": "n"}]
    assert param_obj["maxValue"] == [{"group": "P6", "number": 42, "use": "x"}]

    catalog = LiveAssetsCatalog(AsyncMock())
    built = catalog._build_param_map_from_obj(param_obj, "PARAM_TEST", "test")
    assert built is not None
    assert built.paths["min"] == [{"group": "P6", "number": 42, "use": "n"}]
    assert built.paths["max"] == [{"group": "P6", "number": 42, "use": "x"}]


def test_pure_optional_chain_nullish_and_missing_key() -> None:
    """``obj?.['missing']`` / unbound ``_0x?.['key']`` are undefined on the pure path."""
    assert _Parser("_0x39dd22?.['minValue']").parse_value() is None
    assert _Parser("obj?.['MISSING']", bindings={"obj": {"OTHER": 1}}).parse_value() is None
    assert _Parser("obj?.['present']", bindings={"obj": {"present": 7}}).parse_value() == 7
    assert _Parser("obj?.present", bindings={"obj": {"present": 7}}).parse_value() == 7
    assert _Parser("obj?.missing", bindings={"obj": {"present": 7}}).parse_value() is None
    assert _Parser("_0xabc?.foo").parse_value() is None
    assert _Parser("plainIdent?.foo").parse_value() is None
    assert _Parser("1?.foo").parse_value() is None
    assert _Parser("obj?.").parse_value() is None
    assert _Parser("1?.['x']").parse_value() is None
    assert _Parser("plainIdent?.['x']").parse_value() is None


def test_typeof_and_bitwise_ops_consume_spa_arrows() -> None:
    """``typeof`` / ``>>`` / ``&`` keep factory call args intact (#495)."""
    assert _Parser("typeof 1").parse_value() == "number"
    assert _Parser("typeof true").parse_value() == "boolean"
    assert _Parser("typeof null").parse_value() == "undefined"
    assert _Parser("typeof 'x'").parse_value() == "string"
    assert _Parser("typeof []").parse_value() == "object"
    assert _Parser("typeof {}").parse_value() == "object"
    assert _Parser("typeof undefined").parse_value() == "undefined"
    assert _Parser("typeof _0xabc").parse_value() == "undefined"
    assert _Parser("typeof fn", bindings={"fn": lambda: None}).parse_value() == "function"
    assert _Parser("typeof T", bindings={"T": int}).parse_value() == "function"
    # Non-callable objects fall through to undefined (SPA only needs cursor advance).
    assert _Parser("typeof x", bindings={"x": object()}).parse_value() == "undefined"
    assert _Parser("5>>1").parse_value() == 2
    assert _Parser("5<<1").parse_value() == 10
    assert _Parser("5&1").parse_value() == 1
    assert _Parser("5|2").parse_value() == 7
    assert _Parser("5^1").parse_value() == 4
    assert _Parser("8>>>1").parse_value() == 4
    assert _Parser("2*3").parse_value() == 6
    assert _Parser("8/2").parse_value() == 4.0
    assert _Parser("7%4").parse_value() == 3
    # Non-int operands keep source-like leftovers (still advance the cursor).
    assert _Parser("'a'>>1").parse_value() == "a>>1"
    assert _Parser("'a'<<1").parse_value() == "a<<1"
    assert _Parser("'a'>>>1").parse_value() == "a>>>1"
    assert _Parser("'a'&1").parse_value() == "a&1"
    assert _Parser("'a'|1").parse_value() == "a|1"
    assert _Parser("'a'^1").parse_value() == "a^1"
    # Logical ops must not be eaten by bitwise parsers.
    assert _Parser("0||7").parse_value() == 7
    assert _Parser("0&&7").parse_value() == 0
    # JavaScript equality binds tighter than bitwise; bool equality coerces like ToInt32.
    assert _Parser("1===1&0").parse_value() == 0
    assert _Parser("1===0|1").parse_value() == 1
    assert _Parser("1===1^0").parse_value() == 1
    assert _Parser("true<<1").parse_value() == 2
    assert _Parser("2.0>>1").parse_value() == 1
    assert _Parser("1.5&1").parse_value() == "1.5&1"


def test_factory_call_valuecallback_typeof_does_not_clobber_number() -> None:
    """Live index shape: ``valueCallback`` typeof/ternary/bit-filter must not rewrite ``number`` (#495)."""
    params = "{id:_0x408650,number:_0x9ae4b2,name:_0x29396b,valueCallback:valueCallback=void 0x0}"
    body = (
        "{const o={'id':_0x408650,'name':_0x29396b,"
        "'value':[{'group':'P100','number':_0x9ae4b2,'use':'v'}],"
        "'valueCallback':valueCallback};return o;}"
    )
    factory = make_object_factory(params, body, {})
    call = (
        "basicParameterBuilder_P100({'id':0x126d571b0af6,'number':0x1,"
        "'name':'parameters.INFOSCREEN_KOTLY_W_UZYCIU',"
        "'valueCallback':_0x499c0b=>typeof _0x499c0b==='number'"
        "?[0x0,0x1,0x2,0x3]['filter'](_0x3d459d=>_0x499c0b>>_0x3d459d&0x1)['length']"
        ":_0x499c0b})"
    )
    out = _Parser(call, bindings={"basicParameterBuilder_P100": factory}).parse_value()
    assert isinstance(out, dict)
    assert out["value"] == [{"group": "P100", "number": 1, "use": "v"}]
    assert set(out) >= {"id", "name", "value"}
    # Argument object must not grow operator-character junk keys from a truncated arrow.
    assert "&" not in out
    assert ">" not in out


def test_math_floor_folds_numeric_register_indexes() -> None:
    """``Math['floor']`` / ``Math.floor`` with numeric args become ints (#497)."""
    assert _Parser("Math['floor'](0x63/0x7)").parse_value() == 14
    assert _Parser("Math.floor(0x63/0x7)").parse_value() == 14
    assert _Parser("0x9+Math['floor'](0x3f/0x7)").parse_value() == 18
    assert _Parser("floor(9.9)", bindings={"floor": "floor"}).parse_value() == 9
    # Unbound numerators stay leftovers (no invented register indexes).
    assert _Parser("Math['floor'](_0xabc/0x7)").parse_value() == "floor(_0xabc/0x7)"
    assert _Parser("0x9+Math['floor'](_0xabc/0x7)").parse_value() == "9floor(_0xabc/0x7)"
    # Bound module consts fold through floor then additive ``+``.
    assert _Parser("0x9+Math['floor'](_0xabc/0x7)", bindings={"_0xabc": 0x3F}).parse_value() == 18
    # Non-floor / wrong arity must not fold.
    assert _Parser("ceil(1.2)", bindings={"ceil": "ceil"}).parse_value() == "ceil(1.2)"
    assert _Parser("Math['floor'](1,2)").parse_value() == "floor(1,2)"
    assert _Parser("Math['floor'](true)").parse_value() == "floor(true)"
    # Non-string callees must not raise when membership-testing floor names.
    assert _Parser("[1](2)").parse_value() == "(2)"
    assert _Parser("({a:1})(2)").parse_value() == "(2)"
    # Non-finite floats stay leftovers (``math.floor`` would OverflowError).
    assert _Parser("Math['floor'](1e999)").parse_value() == "floor(1e999)"
    assert _Parser("Math.floor(1e999)").parse_value() == "(1e999)"


def test_factory_math_floor_number_becomes_address_selector() -> None:
    """Factory path ``number`` from ``base+Math.floor(idx/7)`` stays an int (#497)."""
    from pybragerone.models.param_resolver import ParamResolver

    params = "{id:_id,number:_n,name:_name}"
    body = "{const o={'id':_id,'name':_name,'unit':[{'group':'P13','number':_n,'use':'u'}]};return o;}"
    factory = make_object_factory(params, body, {})
    call = "basicParameterBuilder_P15({'id':1,'number':0x9+Math['floor'](_0xidx/0x7),'name':'parameters.PARAM_P15_0'})"
    out = _Parser(
        call,
        bindings={"basicParameterBuilder_P15": factory, "_0xidx": 0x3F},
    ).parse_value()
    assert isinstance(out, dict)
    assert out["unit"] == [{"group": "P13", "number": 18, "use": "u"}]
    assert ParamResolver._is_address_selector_list(out["unit"]) is True


def test_factory_body_object_destructure_binds_number() -> None:
    """Bare-arg factories with ``const {number:n}=arg`` must bind locals (#497)."""
    from pybragerone.models.param_resolver import ParamResolver

    # Live ``basicParameterBuilder_TEST`` shape: whole-arg param + body destructure.
    params = "_0xarg"
    body = (
        "{const {id:_id,number:_n,name:_name}=_0xarg;"
        "const o={'id':_id,'name':_name??('parameters.PARAM_TEST_MODE_'+_n),"
        "'any':[{'if':[{'expected':null,'operation':'equalTo',"
        "'value':[{'group':'P5','number':_n,'use':'s'}]}],'then':null}],"
        "'status':{'INVISIBLE':[{'if':[{'expected':1,'operation':'equalTo',"
        "'value':[{'group':'P5','number':_n,'use':'s','bit':0}]}],'then':'![]'},"
        "{'else':'!![]'}]};"
        "return o;}"
    )
    factory = make_object_factory(params, body, {})
    out = factory({"id": 1, "number": 10, "name": "parameters.PARAM_TEST_MODE_10"})
    assert isinstance(out, dict)
    assert out["name"] == "parameters.PARAM_TEST_MODE_10"
    assert out["any"][0]["if"][0]["value"] == [{"group": "P5", "number": 10, "use": "s"}]
    inv = out["status"]["INVISIBLE"][0]["if"][0]["value"]
    assert inv == [{"group": "P5", "number": 10, "use": "s", "bit": 0}]
    assert ParamResolver._is_address_selector_list(inv) is True
    # Missing keys bind as None (no leftover minified idents).
    sparse = factory({"id": 2})
    assert isinstance(sparse, dict)
    assert sparse["any"][0]["if"][0]["value"][0]["number"] is None
    # Defaults in the destructure pattern apply when the key is absent.
    with_default = make_object_factory(
        "_arg",
        "{const {number:_n=7}=_arg; return {'value':[{'group':'P1','number':_n,'use':'v'}]};}",
        {},
    )
    assert with_default({})["value"][0]["number"] == 7
    assert with_default({"number": 3})["value"][0]["number"] == 3
    # Multi-line object RHS must still plan+bind (DOTALL on value side).
    multiline = make_object_factory(
        "_arg",
        "{const {number:_n}={\n'number':4\n}; return {'n':_n};}",
        {},
    )
    assert multiline({})["n"] == 4


def test_factory_body_object_destructure_parse_failure_binds_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Object-destructure RHS parse errors must not leave ``'_n'`` leftovers (#497)."""
    from pybragerone.models import catalog as catalog_mod

    real_parse = catalog_mod._Parser.parse_value

    def boom_parse(self: Any) -> Any:
        if self.source.strip().startswith("_boom"):
            msg = "bind fail"
            raise ValueError(msg)
        return real_parse(self)

    monkeypatch.setattr(catalog_mod._Parser, "parse_value", boom_parse)
    failed = make_object_factory(
        "_arg",
        "{const {number:_n}=_boom; return {'n':_n};}",
        {},
    )
    assert failed({})["n"] is None


def test_narrow_token_maps_resolve_module_floor_consts() -> None:
    """Narrow BasicParameters bindings fall through to module lazy consts (#497)."""
    from pybragerone.models import catalog as catalog_mod

    code = b"""
    const _0xidx = 0x3f;
    const _0xbare = 0x15;
    const basicParameterBuilder_P15 = ({id:_id,number:_n,name:_name}) => {
      const o = {'id':_id,'name':_name,
        'unit':[{'group':'P13','number':_n,'use':'u'}],
        'value':[{'group':'P15','number':_0xbare,'use':'v'}]};
      return o;
    };
    const BasicParameters = {
      PARAM_P15_0: basicParameterBuilder_P15({
        'id':1,
        'number':0x9+Math['floor'](_0xidx/0x7),
        'name':'parameters.PARAM_P15_0'
      })
    };
    """
    maps = LiveAssetsCatalog(AsyncMock())._parse_index_token_raw_maps(code)
    assert "PARAM_P15_0" in maps
    unit = maps["PARAM_P15_0"]["unit"]
    value = maps["PARAM_P15_0"]["value"]
    assert unit == [{"group": "P13", "number": 18, "use": "u"}]
    assert value == [{"group": "P15", "number": 21, "use": "v"}]
    # Parent keys must not inflate narrow iteration / len.
    ctx = catalog_mod._ModuleParseContext.from_bytes(code)
    narrow = catalog_mod._LazyBindings(
        catalog_mod._token_map_binding_items(ctx.source),
        parent=ctx.lazy,
    )
    assert "_0xidx" in narrow
    assert "_0xidx" not in list(narrow)
    assert len(narrow) == len(catalog_mod._token_map_binding_items(ctx.source))
