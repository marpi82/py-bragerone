# mypy: disable-error-code=no-untyped-def
import aiohttp
import pytest
from aioresponses import aioresponses
from pybragerone.assets_client import AssetClient


@pytest.mark.asyncio
async def test_fetch_lang_units_and_params_basic():
    base = "https://one.brager.pl"

    # HTML z odnośnikiem do bundla index-*.js
    html = '<script src="/assets/index-XYZ.js"></script>'

    # Bundle index zawiera importy do plików językowych
    # Bundle index zawiera mapę tłumaczeń -> chunki JS dla PL
    index_js = """
    const translations = {
      "../../resources/languages/pl/units.json": () => d(() => import("./units-DDcKYJaU.js")),
      "../../resources/languages/pl/parameters.json": () => d(() => import("./parameters-CscKwIZR.js")),
    };
    """

    # Minimalne treści plików language
    units_js = 'export default {"1":"°C"};'
    params_js = 'PARAM_0 : Re\nRe = "Nastawa kotła"'

    async with aiohttp.ClientSession() as s:
        with aioresponses() as m:
            # Stub: index.html → wskazuje index-XYZ.js
            m.get(f"{base}/index.html", status=200, body=html)
            # Stub: pobranie index-XYZ.js
            m.get(f"{base}/assets/index-XYZ.js", status=200, body=index_js)
            # Stub: pliki językowe
            m.get(f"{base}/assets/units-DDcKYJaU.js", status=200, body=units_js)
            m.get(f"{base}/assets/parameters-CscKwIZR.js", status=200, body=params_js)

            client = AssetClient(s, base)
            units, labels = await client.fetch_lang_units_and_params("pl")

            assert units["1"] == "°C"
            assert labels["PARAM_0"] == "Nastawa kotła"
