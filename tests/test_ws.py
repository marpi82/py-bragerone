from bragerone.ws import WsClient
from bragerone.api import Api

def test_ws_construct():
    w = WsClient(Api())
    assert w.api is not None

def test_ws_callbacks_collect():
    ws = WsClient(lambda: "tok")
    seen = {}
    ws.add_event_cb(lambda n,d: seen.setdefault("e", 0) or seen.__setitem__("e", 1))
    ws.add_change_cb(lambda p: seen.setdefault("c", 0) or seen.__setitem__("c", 1))
    ws._emit_event("x", {})
    ws._emit_change({})
    assert seen["e"] == 1 and seen["c"] == 1
