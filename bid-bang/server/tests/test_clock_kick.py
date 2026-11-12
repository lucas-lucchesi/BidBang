"""Contrôle d'horloge serveur avant mise / abandon, et exclusion d'un joueur du salon."""
import pytest
from starlette.testclient import TestClient

from app.errors import GameError
from app.main import app
from app.rooms import registry


# ------------------------------------------------------------- horloge
def test_bid_after_deadline_is_rejected_and_auction_closes(make_game, clock):
    g = make_game(n=3, bid_timer=10)
    first = g.auction["item"]["id"]
    g.bid("p1", g.required_bid())
    clock.advance(10.5)  # échéance dépassée, mais le chronomètre asyncio n'a pas encore tiré
    with pytest.raises(GameError, match="Temps écoulé"):
        g.bid("p2", 500)
    # la mise tardive n'est pas prise en compte ; p1 (meneur) a remporté l'objet
    assert g.last_result["winner_id"] == "p1" and g.last_result["item"]["id"] == first
    assert g.players["p2"]["budget"] == 2200 and g.index == 1


def test_bid_before_deadline_still_works(make_game, clock):
    g = make_game(n=3, bid_timer=10)
    clock.advance(9.9)
    g.bid("p1", g.required_bid())
    assert g.auction["leader"] == "p1"


def test_fold_after_deadline_rejected(make_game, clock):
    g = make_game(n=3, bid_timer=10)
    g.bid("p1", g.required_bid())
    clock.advance(11)
    with pytest.raises(GameError, match="Temps écoulé"):
        g.fold("p2")
    assert g.last_result["winner_id"] == "p1"


def test_late_action_on_unsold_item(make_game, clock):
    g = make_game(n=2, bid_timer=10)
    clock.advance(11)
    with pytest.raises(GameError):
        g.fold("p1")
    assert g.last_result["winner_id"] is None and g.index == 1


def test_blind_late_bid_rejected(make_game, clock):
    g = make_game(n=2, mode="aveugle", bid_timer=10)
    g.bid("p1", 100)
    clock.advance(11)
    with pytest.raises(GameError, match="Temps écoulé"):
        g.bid("p2", 900)
    assert g.last_result["winner_id"] == "p1" and g.last_result["purchase_price"] == 100


def test_game_goes_straight_to_results_without_vote_phase(make_game):
    g = make_game(n=3)
    while g.phase == "auction":
        g.on_timeout(g.version)
    assert g.phase == "finished" and g.results is not None
    assert not hasattr(g, "vote") and "vote" not in g.snapshot("p1")


def test_stale_timer_still_ignored(make_game, clock):
    g = make_game(n=3)
    v = g.version
    g.bid("p1", g.required_bid())
    assert g.on_timeout(v) is False


# ---------------------------------------------------------------- API
@pytest.fixture
def client():
    registry.rooms.clear()
    with TestClient(app) as c:
        yield c


def room_with(client, *names):
    a = client.post("/rooms", json={"pseudo": names[0], "settings": {}}).json()
    others = [client.post(f"/rooms/{a['code']}/join", json={"pseudo": n}).json() for n in names[1:]]
    return a, others


def recv_until(ws, kind):
    while True:
        m = ws.receive_json()
        if m["type"] == kind:
            return m


def test_late_ws_bid_broadcasts_new_state(client):
    a, (b,) = room_with(client, "Alice", "Bob")
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa, \
         client.websocket_connect(f"/ws/{a['code']}?token={b['token']}") as wb:
        wa.send_json({"type": "start_game"})
        recv_until(wa, "game_state")
        room = registry.get(a["code"])
        room.game.auction["deadline"] = room.game.clock() - 1  # échéance déjà passée
        wb.send_json({"type": "bid", "amount": 100})
        last = None
        while True:  # le nouvel état est diffusé avant l'erreur renvoyée à l'auteur
            m = wb.receive_json()
            if m["type"] == "game_state":
                last = m["game"]
            elif m["type"] == "error":
                break
        assert "Temps écoulé" in m["message"]
        assert last["item_index"] == 2 and last["last_result"]["winner"] is None


# ---------------------------------------------------------------- kick
def test_host_kicks_player(client):
    a, (b, c) = room_with(client, "Alice", "Bob", "Cléo")
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa, \
         client.websocket_connect(f"/ws/{a['code']}?token={b['token']}") as wb:
        wa.send_json({"type": "kick", "target": b["player_id"]})
        assert recv_until(wb, "kicked")
        room = registry.get(a["code"])
        assert b["player_id"] not in room.players and len(room.players) == 2
        state = recv_until(wa, "room_state")
        while len(state["room"]["players"]) != 2:
            state = recv_until(wa, "room_state")
        # le jeton de Bob ne marche plus, et son pseudo est banni du salon
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/{a['code']}?token={b['token']}"):
                pass
        r = client.post(f"/rooms/{a['code']}/join", json={"pseudo": "bob"})
        assert r.status_code == 403 and "exclu" in r.json()["detail"]
        assert client.post(f"/rooms/{a['code']}/join", json={"pseudo": "Dan"}).status_code == 200


def test_kick_rules(client):
    a, (b,) = room_with(client, "Alice", "Bob")
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa, \
         client.websocket_connect(f"/ws/{a['code']}?token={b['token']}") as wb:
        wb.send_json({"type": "kick", "target": a["player_id"]})  # pas l'hôte
        assert "hôte" in recv_until(wb, "error")["message"]
        wa.send_json({"type": "kick", "target": a["player_id"]})  # soi-même
        assert "vous-même" in recv_until(wa, "error")["message"]
        wa.send_json({"type": "kick", "target": "zzz"})
        assert "inconnu" in recv_until(wa, "error")["message"]
        wa.send_json({"type": "kick"})
        assert "inconnu" in recv_until(wa, "error")["message"]
        wa.send_json({"type": "start_game"})
        recv_until(wa, "game_state")
        wa.send_json({"type": "kick", "target": b["player_id"]})  # partie lancée
        assert "avant le début" in recv_until(wa, "error")["message"]
        assert b["player_id"] in registry.get(a["code"]).players
