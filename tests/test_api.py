import pytest
from bragerone.api import Api

def test_gateway_is_exposed_on_top_level():
    import bragerone
    assert hasattr(bragerone, "Gateway"), "Gateway nie jest eksportowany w __all__"
    # opcjonalnie: sprawdź, że to klasa
    assert isinstance(bragerone.Gateway, type)

@pytest.mark.asyncio
async def test_api_construct():
    a = Api()
    assert a.jwt is None

@pytest.mark.asyncio
async def test_api_login_monkeypatch(monkeypatch):
    api = Api()

    async def fake_req(method, url, **kw):
        return {"accessToken": "abc"}
    monkeypatch.setattr(api, "_req", fake_req)

    data = await api.login("x","y")
    assert api.jwt == "abc"
    assert "accessToken" in data
