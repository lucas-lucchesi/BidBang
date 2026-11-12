"""Revanche : relancer une partie dans le même salon, sans recréer de salon."""
import pytest
from starlette.testclient import TestClient

from app.ai import base as ai_base
from app.ai import limits
from app.main import app
from app.rooms import registry

KEY = "sk-ant-TESTSECRET-0123456789abcdef"


@pytest.fixture
def client():
    registry.rooms.clear()
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def drain(ws, kind, limit=40):
    for _ in range(limit):
        m = ws.receive_json()
        if m["type"] == kind:
            return m
    raise AssertionError(f"pas de message {kind}")


def setup_room(client, **settings):
    a = client.post("/rooms", json={"pseudo": "Alice", "settings": {"item_count": 6, **settings}}).json()
    b = client.post(f"/rooms/{a['code']}/join", json={"pseudo": "Bob"}).json()
    return a, b


def finish(code):
    """Termine la partie en cours directement dans le moteur (équivalent à des enchères jouées)."""
    room = registry.get(code)
    g = room.game
    while g.phase == "auction":
        g.on_timeout(g.version)
    room.status = "finished"
    return room


def test_host_can_replay_in_the_same_room(client):
    a, b = setup_room(client)
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa, \
         client.websocket_connect(f"/ws/{a['code']}?token={b['token']}") as wb:
        wa.send_json({"type": "start_game"})
        first = drain(wa, "game_state")["game"]
        room = finish(a["code"])
        old_game = room.game
        wa.send_json({"type": "rematch"})
        for ws in (wa, wb):
            assert drain(ws, "rematch")["type"] == "rematch"
        assert room.status == "lobby" and room.game is None and room.game is not old_game
        assert set(room.players) == {a["player_id"], b["player_id"]}  # mêmes joueurs, mêmes jetons
        assert room.room_state()["status"] == "lobby" and room.host_id == a["player_id"]
        assert room.settings["mode"] == "normal" and room.settings["item_count"] == 6  # réglages conservés
        wa.send_json({"type": "start_game"})
        second = drain(wa, "game_state")["game"]
        assert second["phase"] == "auction" and second["item_index"] == 1
        assert all(p["budget"] == 2200 and p["purchases"] == [] for p in second["players"])  # neuve
        assert registry.get(a["code"]) is room  # même salon, même code
        assert first["settings"] == second["settings"]


def test_replay_can_change_mode_and_settings(client):
    a, b = setup_room(client)
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa:
        wa.send_json({"type": "start_game"})
        drain(wa, "game_state")
        room = finish(a["code"])
        wa.send_json({"type": "rematch", "settings": {"mode": "aveugle", "budget": 3500,
                                                      "bid_timer": 30, "item_count": 8}})
        drain(wa, "rematch")
        assert (room.settings["mode"], room.settings["budget"], room.settings["bid_timer"],
                room.settings["item_count"]) == ("aveugle", 3500, 30, 8)
        wa.send_json({"type": "start_game"})
        g = drain(wa, "game_state")["game"]
        assert g["mode"] == "aveugle" and g["auction"]["blind"] is True
        assert g["players"][0]["budget"] == 3500 and g["item_total"] == 8


def test_legacy_mode_names_are_migrated_on_replay(client):
    a, _ = setup_room(client)
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa:
        wa.send_json({"type": "start_game"})
        drain(wa, "game_state")
        room = finish(a["code"])
        wa.send_json({"type": "rematch", "settings": {"mode": "survie"}})
        drain(wa, "rematch")
        assert room.settings["mode"] == "normal"


def test_only_the_host_and_only_when_finished(client):
    a, b = setup_room(client)
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa, \
         client.websocket_connect(f"/ws/{a['code']}?token={b['token']}") as wb:
        wa.send_json({"type": "rematch"})  # salon d'attente : rien à relancer
        assert "pas terminée" in drain(wa, "error")["message"]
        wa.send_json({"type": "start_game"})
        drain(wa, "game_state")
        wa.send_json({"type": "rematch"})  # partie en cours
        assert "pas terminée" in drain(wa, "error")["message"]
        room = finish(a["code"])
        wb.send_json({"type": "rematch"})  # pas l'hôte
        assert "hôte" in drain(wb, "error")["message"]
        assert room.status == "finished" and room.game is not None  # rien n'a changé


@pytest.mark.parametrize("changes", [{"mode": "zen"}, {"budget": 999}, {"bid_timer": 7}, {"item_count": 5},
                                     {"item_count": 21}, {"item_count": 13}, {"theme_id": "plage"},
                                     {"max_players": 2}, {"scenario": "x"}, "texte", [1]])
def test_invalid_changes_are_refused_and_nothing_is_reset(client, changes):
    a, _ = setup_room(client)
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa:
        wa.send_json({"type": "start_game"})
        drain(wa, "game_state")
        room = finish(a["code"])
        before = dict(room.settings)
        wa.send_json({"type": "rematch", "settings": changes})
        assert drain(wa, "error")["message"]
        assert room.status == "finished" and room.game is not None and room.settings == before


def test_classic_replay_draws_new_cards(client):
    a, _ = setup_room(client, theme_id="cabane", item_count=6)
    seen = []
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa:
        for _ in range(4):
            wa.send_json({"type": "start_game"})
            drain(wa, "game_state")
            room = finish(a["code"])
            seen.append(tuple(i["id"] for i in room.game.items))
            wa.send_json({"type": "rematch"})
            drain(wa, "rematch")
    assert len(set(seen)) > 1  # tirage au hasard à chaque partie


def test_reconnection_after_replay_goes_to_the_lobby_not_the_old_game(client):
    a, b = setup_room(client)
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa:
        wa.send_json({"type": "start_game"})
        drain(wa, "game_state")
        finish(a["code"])
        wa.send_json({"type": "rematch"})
        drain(wa, "rematch")
    with client.websocket_connect(f"/ws/{a['code']}?token={b['token']}") as wb:
        m = wb.receive_json()
        assert m["type"] == "room_state" and m["room"]["status"] == "lobby"
        wb.send_json({"type": "ping"})
        assert wb.receive_json()["type"] == "pong"  # aucun game_state ancien entre-temps


def test_players_can_join_or_be_kicked_after_a_replay(client):
    a, b = setup_room(client, max_players=3)
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa:
        wa.send_json({"type": "start_game"})
        drain(wa, "game_state")
        finish(a["code"])
        assert client.post(f"/rooms/{a['code']}/join", json={"pseudo": "Zed"}).status_code == 400  # pas en cours de revanche
        wa.send_json({"type": "rematch"})
        drain(wa, "rematch")
        c = client.post(f"/rooms/{a['code']}/join", json={"pseudo": "Zed"})
        assert c.status_code == 200
        wa.send_json({"type": "kick", "target": b["player_id"]})
        room = registry.get(a["code"])
        for _ in range(10):  # le salon d'attente reste utilisable : l'exclusion est diffusée
            ids = [p["id"] for p in drain(wa, "room_state")["room"]["players"]]
            if b["player_id"] not in ids:
                break
        assert b["player_id"] not in ids and len(ids) == 2 and len(room.players) == 2


def test_scores_of_the_previous_game_do_not_leak(client):
    a, _ = setup_room(client)
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa:
        wa.send_json({"type": "start_game"})
        drain(wa, "game_state")
        room = finish(a["code"])
        room.game.players[a["player_id"]]["budget"] = 1
        wa.send_json({"type": "rematch"})
        drain(wa, "rematch")
        wa.send_json({"type": "start_game"})
        g = drain(wa, "game_state")["game"]
        assert g["results"] is None and g["last_result"] is None and g["bargains"] is None
        assert all(p["budget"] == 2200 for p in g["players"])


def test_ai_game_replay_keeps_the_validated_cards_without_calling_the_ai(client, monkeypatch):
    from tests.test_ai_profile import OM, Script, body, prof
    limits.reset()
    monkeypatch.setattr(limits, "MIN_INTERVAL_SECONDS", 0.0)
    p = Script(body(OM))
    monkeypatch.setattr(ai_base, "get_provider", lambda name: p)
    a = client.post("/rooms", json={"pseudo": "Alice", "settings": {
        "creation_type": "ai", "item_count": 6, "scenario": {"description": "Un onze de l'OM."}}}).json()
    client.post(f"/rooms/{a['code']}/join", json={"pseudo": "Bob"})
    auth = {"Authorization": f"Bearer {a['token']}"}
    ids = [i["id"] for i in client.post(f"/rooms/{a['code']}/ai/generate",
                                         json={"provider": "anthropic", "api_key": KEY}, headers=auth).json()["items"]]
    client.put(f"/rooms/{a['code']}/selection", headers=auth, json={"item_ids": ids[:8]})
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa:
        wa.send_json({"type": "start_game"})
        drain(wa, "game_state")
        room = finish(a["code"])
        wa.send_json({"type": "rematch", "settings": {"mode": "aveugle", "item_count": 8}})
        drain(wa, "rematch")
        assert room.settings["ready"] is True and room.settings["item_ids"] == ids[:8]
        wa.send_json({"type": "start_game"})
        g = drain(wa, "game_state")["game"]
        assert g["mode"] == "aveugle" and g["item_total"] == 8
        assert {i["name"] for i in room.game.items} <= {c["name"] for c in OM}
        assert len(p.calls) == 1  # aucun nouvel appel IA
        finish(a["code"])
        # item_count au-delà de la sélection validée : refusé, la partie terminée reste en place
        wa.send_json({"type": "rematch", "settings": {"item_count": 12}})
        assert "insuffisante" in drain(wa, "error")["message"]
        assert room.status == "finished"
