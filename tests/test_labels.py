from bragerone.labels import LabelFetcher

def test_labels_construct():
    l = LabelFetcher()
    assert l.count_vars() == 0
    assert l.count_langs() == 0

def test_labels_basic():
    lf = LabelFetcher()
    lf.register_param_alias("P6", 7, "parameters.PARAM_7")
    lf.set_translation("pl", "parameters.PARAM_7", "Temperatura załączenia pomp")
    assert lf.param_label("P6", 7, "pl") == "Temperatura załączenia pomp"
