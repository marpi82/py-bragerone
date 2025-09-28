# mypy: disable-error-code=no-untyped-def
import pytest

from pybragerone import BragerOneApiClient
from pybragerone import BragerOneGateway


def test_gateway_is_exposed_on_top_level():
    import pybragerone

    assert hasattr(pybragerone, "BragerOneGateway"), "BragerOneGateway nie jest eksportowany w __all__"
    # opcjonalnie: sprawdź, że to klasa
    assert isinstance(BragerOneGateway, type)


@pytest.mark.asyncio
async def test_api_construct():
    a = BragerOneApiClient()
    assert a.jwt is None


@pytest.mark.asyncio
async def test_api_login_monkeypatch(monkeypatch):
    api = BragerOneApiClient()

    async def fake_req(method, url, **kw):
        return {"accessToken": "abc"}

    monkeypatch.setattr(api, "_req", fake_req)

    data = await api.login("x", "y")
    assert api.jwt == "abc"
    assert "accessToken" in data
