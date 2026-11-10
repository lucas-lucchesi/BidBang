import pytest
from starlette.testclient import TestClient

from app.main import app
from app.rooms import registry


@pytest.fixture
def client():
    registry.rooms.clear()
    with TestClient(app) as c:
        yield c


def create(client, pseudo="Alice", **settings):
    r = client.post("/rooms", json={"pseudo": pseudo, "settings": settings})
    assert r.status_code == 200, r.text
    return r.json()


def test_health_and_locations(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert len(client.get("/locations").json()["locations"]) == 6


def test_create_and_join(client):
    s = create(client)
    assert len(s["code"]) == 6 and s["room"]["host_id"] == s["player_id"]
    r = client.post(f"/rooms/{s['code'].lower()}/join", json={"pseudo": "Bob"})
    assert r.status_code == 200
    assert len(r.json()["room"]["players"]) == 2


def test_join_errors_in_french(client):
    s = create(client)
    assert client.post("/rooms/ZZZZZZ/join", json={"pseudo": "Bob"}).json()["detail"] == "Salon introuvable."
    r = client.post(f"/rooms/{s['code']}/join", json={"pseudo": "alice"})
    assert r.status_code == 400 and "pseudo" in r.json()["detail"].lower()


def test_room_full(client):
    s = create(client)
    for n in range(3):
        assert client.post(f"/rooms/{s['code']}/join", json={"pseudo": f"J{n}"}).status_code == 200
    r = client.post(f"/rooms/{s['code']}/join", json={"pseudo": "Trop"})
    assert r.status_code == 400 and "complet" in r.json()["detail"]


def test_invalid_settings(client):
    r = client.post("/rooms", json={"pseudo": "A", "settings": {"budget": 1}})
    assert r.status_code == 400


def test_ws_rejects_bad_token(client):
    s = create(client)
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/{s['code']}?token=nope"):
            pass


def test_ws_full_flow(client):
    a = create(client, "Alice", item_count=6, mode="survie")
    b = client.post(f"/rooms/{a['code']}/join", json={"pseudo": "Bob"}).json()
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa, \
         client.websocket_connect(f"/ws/{a['code']}?token={b['token']}") as wb:
        assert wa.receive_json()["type"] == "room_state"
        # Bob ne peut pas lancer
        wb.send_json({"type": "start_game"})
        msgs = []
        while True:
            m = wb.receive_json()
            msgs.append(m)
            if m["type"] == "error":
                break
        assert "hôte" in m["message"]
        wa.send_json({"type": "start_game"})
        game = None
        while game is None:
            m = wa.receive_json()
            if m["type"] == "game_state":
                game = m["game"]
        assert game["phase"] == "auction" and game["you"] == a["player_id"]
        price = game["auction"]["required_bid"]
        wa.send_json({"type": "bid", "amount": price})
        while True:
            m = wa.receive_json()
            if m["type"] == "game_state" and m["game"]["auction"]["current_bid"] == price:
                break
        assert m["game"]["auction"]["leader_id"] == a["player_id"]
        wa.send_json({"type": "bid", "amount": price})
        while True:
            m = wa.receive_json()
            if m["type"] == "error":
                break
        assert "menez" in m["message"]
