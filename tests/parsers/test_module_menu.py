
from pybragerconnect.parsers.module_menu import parse_module_menu


def test_module_menu_minimal():
    js = '''
    const A={DISPLAY_PARAMETER_LEVEL_1:1};
    const E={READ:0,WRITE:1,STATUS:2};
    export default {
      sections: [
        { label: t("menu.section.boiler"), permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameters: e([E.READ,"PARAM_0",E.WRITE,"PARAM_1",E.STATUS,"PARAM_2"]) }
      ]
    };
    '''
    tree = parse_module_menu(js, module_code="TEST")
    assert tree.module_code == "TEST"
    assert tree.root
    first = tree.root[0]
    params = first.params if first.params else (first.children[0].params if first.children else [])
    assert any(p.key == "PARAM_0" and p.operation == "READ" for p in params)
    assert any(p.key == "PARAM_1" and p.operation == "WRITE" for p in params)
    assert any(p.key == "PARAM_2" and p.operation == "STATUS" for p in params)
