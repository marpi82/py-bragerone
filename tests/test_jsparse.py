# mypy: disable-error-code=no-untyped-def
from pybragerone import jsparse


def test_parameters_parse_basic():
    js = """
    // aliases
    PARAM_6 : Te,
    PARAM_0 : Re,
    // defs
    Te = "Maksymalna wydajność dmuchawy"
    Re = "Nastawa kotła"
    """
    out = jsparse.parse_parameters_js(js)
    assert out["PARAM_6"].startswith("Maksymalna")
    assert out["PARAM_0"].startswith("Nastawa")
