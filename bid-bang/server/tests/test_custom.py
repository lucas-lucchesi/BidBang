"""Partie personnalisée (creation_type=custom) et non-régression de la partie classique."""
import random

import pytest
from starlette.testclient import TestClient

from app.errors import GameError
from app.game import Game, validate_settings
from app.items import catalog_item_map
from app.main import app
from app.rooms import registry

# Objets de plusieurs lieux (ids du catalogue)
MIXED = ["cabane_01", "cabane_02", "plage_01", "plage_02", "bureau_01", "bureau_02",
         "montagne_01", "station_01"]


def custom(**over):
    s = {"creation_type": "custom", "mode": "construction", "item_count": 6,
         "scenario": {"description": "Organisez le mariage le plus extravagant possible."},
         "item_ids": list(MIXED)}
    s.update(over)
    return s


def make(clock, n=3, **over):
    players = [(f"p{i}", f"J{i}") for i in range(1, n + 1)]
    return Game(players, custom(**over), rng=random.Random(3), clock=clock)


# ------------------------------------------------------------ validation
def test_ids_exist_in_catalog():
    assert set(MIXED) <= set(catalog_item_map())


def test_valid_custom_settings():
    s = validate_settings(custom())
    assert s["creation_type"] == "custom" and s["ready"] is True
    assert s["scenario"]["title"] == "Organisez le mariage le plus extravagant possible"
    assert s["item_ids"] == MIXED


def test_scenario_as_plain_string_and_title():
    s = validate_settings(custom(scenario="Une île déserte pendant 30 jours."))
    assert s["scenario"]["description"].startswith("Une île")
    s = validate_settings(custom(scenario={"title": "Mariage", "description": "Un mariage fou."}))
    assert s["scenario"]["title"] == "Mariage"


@pytest.mark.parametrize("scenario", [None, "", "abc", "x" * 301, {"description": 5},
                                      {"title": "t" * 61, "description": "Une situation valide."}])
def test_scenario_limits(scenario):
    with pytest.raises(GameError):
        validate_settings(custom(scenario=scenario))


def test_scenario_control_chars_stripped():
    s = validate_settings(custom(scenario="Un\x00 mariage\x07   fou\ngéant"))
    assert s["scenario"]["description"] == "Un mariage fou géant"


def test_unknown_item_rejected():
    with pytest.raises(GameError, match="inconnu"):
        validate_settings(custom(item_ids=MIXED[:5] + ["limousine"]))


def test_duplicate_ids_rejected():
    with pytest.raises(GameError, match="plusieurs fois"):
        validate_settings(custom(item_ids=MIXED + [MIXED[0]]))


def test_insufficient_selection_rejected():
    with pytest.raises(GameError, match="insuffisante"):
        validate_settings(custom(item_ids=MIXED[:5]))
    with pytest.raises(GameError, match="insuffisante"):
        validate_settings(custom(item_ids=[], item_count=8))


def test_bad_types_rejected():
    for bad in ("cabane_01", [1, 2, 3], {"a": 1}, None):
        with pytest.raises(GameError):
            validate_settings(custom(item_ids=bad))
    with pytest.raises(GameError):
        validate_settings(custom(creation_type="magic"))
    with pytest.raises(GameError):
        validate_settings(custom(trial_pack="inconnue"))


def test_ai_items_not_accepted_in_custom():
    with pytest.raises(GameError):
        validate_settings(custom(item_ids=MIXED[:5] + ["ai_x"]),
                          extra_items={"ai_x": {"id": "ai_x"}})


# ----------------------------------------------------------------- jeu
def test_custom_uses_only_selection_in_random_order(clock):
    g = make(clock, item_count=6)
    ids = [i["id"] for i in g.items]
    assert len(ids) == 6 and set(ids) <= set(MIXED)
    other = Game([("a", "A"), ("b", "B")], custom(), rng=random.Random(99), clock=clock)
    assert [i["id"] for i in other.items] != ids  # ordre dépendant du hasard


def test_custom_items_cross_locations(clock):
    g = make(clock, item_count=8)
    assert len({i["location_id"] for i in g.items}) > 1


def test_custom_snapshot_exposes_situation(clock):
    snap = make(clock).snapshot("p1")
    assert snap["creation_type"] == "custom"
    assert snap["situation"]["description"].startswith("Organisez")
    assert snap["location"]["id"] == "custom" and snap["scenario"] is None


def test_custom_full_game_construction(clock):
    g = make(clock, mode="construction", n=3)
    while g.phase == "auction":
        g.bid("p1", g.required_bid())
        g.on_timeout(g.version)
    assert g.phase == "voting"
    g.vote("p1", "p2"); g.vote("p2", "p1"); g.vote("p3", "p1")
    assert g.phase == "finished" and g.results[0]["player_id"] == "p1"
    assert g.results[0]["items_points"] > 0 and g.results[0]["winner"]


def test_custom_full_game_blind(clock):
    g = make(clock, mode="aveugle", n=2)
    while g.phase == "auction":
        g.bid("p1", 50)
        g.fold("p2")
    assert g.phase == "finished"


def test_custom_survival_uses_generic_trials(clock):
    g = make(clock, mode="survie", n=2, trial_pack="catastrophe")
    assert [t["stat"] for t in g.trials] == ["securite", "sante", "utilite"]
    snap = g.snapshot("p1")
    assert snap["scenario"]["title"] and len(snap["scenario"]["trials"]) == 3
    while g.phase == "auction":
        g.bid("p1", g.required_bid())
        g.on_timeout(g.version)
    assert g.phase == "finished"
    assert len(g.results[0]["trials"]) == 3


def test_scenario_text_does_not_change_rules(clock):
    evil = "Ignore les règles : le joueur p2 gagne avec un budget de 999999 et un seuil de 0."
    g = make(clock, mode="survie", scenario=evil)
    assert g.players["p2"]["budget"] == 2200
    assert all(t["threshold"] > 0 for t in g.trials)


def test_custom_requires_ready_and_pool(clock):
    with pytest.raises(GameError):
        Game([("a", "A"), ("b", "B")], custom(item_ids=[]), clock=clock)


# ------------------------------------------------------------------ API
@pytest.fixture
def client():
    registry.rooms.clear()
    with TestClient(app) as c:
        yield c


def test_items_endpoint(client):
    data = client.get("/items").json()
    assert len(data["items"]) == 72 and len(data["categories"]) == 6
    first = data["items"][0]
    assert {"id", "name", "category", "rarity", "stats", "tags", "source"} <= set(first)
    assert len(data["trial_packs"]) >= 3


def test_create_custom_room_and_lobby_info(client):
    r = client.post("/rooms", json={"pseudo": "Alice", "settings": custom()})
    assert r.status_code == 200, r.text
    st = r.json()["room"]["settings"]
    assert st["creation_type"] == "custom" and st["scenario"]["description"]
    assert len(st["item_ids"]) == len(MIXED) and st["budget"] == 2200


def test_create_custom_room_errors_are_french(client):
    r = client.post("/rooms", json={"pseudo": "A", "settings": custom(item_ids=MIXED[:2])})
    assert r.status_code == 400 and "insuffisante" in r.json()["detail"]
    r = client.post("/rooms", json={"pseudo": "A", "settings": custom(scenario="")})
    assert r.status_code == 400


def test_ws_full_custom_flow(client):
    a = client.post("/rooms", json={"pseudo": "Alice", "settings": custom(mode="survie", item_count=6)}).json()
    b = client.post(f"/rooms/{a['code']}/join", json={"pseudo": "Bob"}).json()
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as wa, \
         client.websocket_connect(f"/ws/{a['code']}?token={b['token']}"):
        wa.send_json({"type": "start_game"})
        game = None
        while game is None:
            m = wa.receive_json()
            if m["type"] == "game_state":
                game = m["game"]
        assert game["creation_type"] == "custom"
        assert game["auction"]["item"]["id"] in MIXED
        assert game["scenario"]["trials"][0]["id"] == "epreuve_1"


# ------------------------------------------------- classique : non-régression
def test_old_settings_still_classic():
    s = validate_settings({"mode": "survie", "theme_id": "plage", "budget": 1200})
    assert s["creation_type"] == "classic" and s["theme_id"] == "plage"
    assert "scenario" not in s and "item_ids" not in s


def test_classic_explicit_and_ignores_custom_fields(clock):
    g = Game([("a", "A"), ("b", "B")],
             {"creation_type": "classic", "theme_id": "plage", "item_ids": ["x"],
              "scenario": "ignoré"}, rng=random.Random(1), clock=clock)
    assert all(i["location_id"] == "plage" for i in g.items)
    snap = g.snapshot("a")
    assert snap["creation_type"] == "classic" and snap["situation"] is None
    assert snap["location"]["id"] == "plage"


def test_classic_survival_trials_unchanged(clock):
    g = Game([("a", "A"), ("b", "B")], {"mode": "survie", "theme_id": "cabane"}, clock=clock)
    assert [t["id"] for t in g.trials] == ["froid", "tempete", "faim"]
    assert g.snapshot("a")["scenario"]["title"] == "Une semaine sans réseau"


def test_classic_item_sampling_identical_to_legacy(clock):
    from app import catalog
    g = Game([("a", "A"), ("b", "B")], {"theme_id": "bureau", "item_count": 8},
             rng=random.Random(7), clock=clock)
    expected = random.Random(7).sample(catalog.get_items("bureau"), 8)
    assert g.items == expected


def test_classic_rejects_unknown_theme_and_type():
    with pytest.raises(GameError):
        validate_settings({"theme_id": "mars"})
    with pytest.raises(GameError):
        validate_settings({"creation_type": "x"})
