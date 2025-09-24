
from pathlib import Path

from pybragerconnect.parsers.mappings import parse_param_descriptors
from pybragerconnect.parsers.models import ParamDescriptor


def test_param_descriptor_parses_export_default():
    here = Path(__file__).parent / "fixtures"
    tested = False
    for p in here.glob("*.js"):
        if p.name.lower().startswith("param"):
            js = p.read_text(encoding="utf-8", errors="ignore")
            descs = parse_param_descriptors(js)
            assert isinstance(descs, dict)
            if descs:
                key, d = next(iter(descs.items()))
                assert isinstance(d, ParamDescriptor)
                tested = True
                break
    assert tested, "No param fixture parsed"
