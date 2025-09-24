
from pathlib import Path

from pybragerconnect.parsers.i18n import load_i18n_generic


def test_i18n_generic_loads_any_asset():
    here = Path(__file__).parent / "fixtures"
    found = False
    for p in here.glob("*.js"):
        if "parameters" in p.name or "units" in p.name:
            data = p.read_text(encoding="utf-8", errors="ignore")
            mapping = load_i18n_generic(data)
            assert isinstance(mapping, dict)
            assert len(mapping) > 0
            found = True
            break
    assert found, "No i18n fixture found"
