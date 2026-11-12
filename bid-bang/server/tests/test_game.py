import pytest

from app.errors import GameError
from app.game import OPENING_MIN, Game, min_step, normalize_mode, validate_settings


def test_min_step():
    assert min_step(40) == 10      # 3,2 -> 0 -> minimum 10
    assert min_step(200) == 20     # 16 -> 20
    assert min_step(480) == 40     # 38,4 -> 40


def test_settings_validation():
    assert validate_settings(None)["budget"] == 2200
    with pytest.raises(GameError):
        validate_settings({"budget": 999})
    with pytest.raises(GameError):
        validate_settings({"theme_id": "mars"})
    with pytest.raises(GameError):
        validate_settings({"mode": "zen"})


def test_needs_two_players(clock):
    with pytest.raises(GameError):
        Game([("a", "A")], {}, clock=clock)


def test_starting_state(make_game):
    g = make_game(item_count=6)
    assert g.phase == "auction" and len(g.items) == 6
    assert g.auction["bid"] is None
    assert g.required_bid() == OPENING_MIN


def test_opening_bid_is_free(make_game):
    g = make_game()
    price = g.auction["price"]
    assert price > OPENING_MIN
    with pytest.raises(GameError):
        g.bid("p1", OPENING_MIN - 1)
    g.bid("p1", OPENING_MIN)  # bien en dessous du prix de l'objet
    assert g.auction["leader"] == "p1" and g.auction["bid"] == OPENING_MIN


def test_opening_bid_can_exceed_price(make_game):
    g = make_game()
    g.bid("p1", g.auction["price"] * 2)
    assert g.auction["bid"] == g.auction["price"] * 2


def test_outbid_needs_step(make_game):
    g = make_game()
    price, step = 100, g.auction["step"]
    g.bid("p1", price)
    with pytest.raises(GameError):
        g.bid("p2", price + step - 1)
    g.bid("p2", price + step)
    assert g.auction["leader"] == "p2"


def test_leader_cannot_rebid_or_fold(make_game):
    g = make_game()
    g.bid("p1", g.auction["price"])
    with pytest.raises(GameError):
        g.bid("p1", g.auction["price"] + 100)
    with pytest.raises(GameError):
        g.fold("p1")


def test_cannot_bid_beyond_budget(make_game):
    g = make_game(budget=1200)
    with pytest.raises(GameError):
        g.bid("p1", 5000)
    with pytest.raises(GameError):
        g.bid("p1", "100")


def test_timer_resets_on_bid(make_game, clock):
    g = make_game(bid_timer=15)
    start = g.auction["deadline"]
    clock.advance(10)
    g.bid("p1", g.auction["price"])
    assert g.auction["deadline"] > start
    assert g.auction["deadline"] == clock() + 15


def test_timeout_awards_leader(make_game, clock):
    g = make_game()
    item = g.auction["item"]
    price = g.auction["price"]
    g.bid("p1", price)
    clock.advance(20)
    assert g.on_timeout(g.version)
    assert g.players["p1"]["budget"] == 2200 - price
    assert g.players["p1"]["items"] == [item]
    assert g.players["p1"]["purchases"] == [{"item": item, "purchase_price": price}]
    assert g.last_result["winner_id"] == "p1"
    assert g.index == 1


def test_timeout_without_bid_is_unsold(make_game):
    g = make_game()
    g.on_timeout(g.version)
    assert g.last_result["winner_id"] is None
    assert all(not p["items"] for p in g.players.values())


def test_stale_timeout_ignored(make_game):
    g = make_game()
    old = g.version
    g.bid("p1", g.auction["price"])
    assert g.on_timeout(old) is False
    assert g.index == 0


def test_all_fold_ends_round_unsold(make_game):
    g = make_game(n=3)
    g.fold("p1")
    g.fold("p2")
    assert g.index == 0
    g.fold("p3")
    assert g.index == 1 and g.last_result["winner_id"] is None


def test_round_ends_when_nobody_can_outbid(make_game):
    g = make_game(n=3)
    g.bid("p1", g.auction["price"])
    g.fold("p2")
    assert g.index == 0
    g.fold("p3")
    assert g.index == 1 and g.last_result["winner_id"] == "p1"


def test_round_ends_when_challengers_too_poor(make_game):
    g = make_game(n=2, budget=1200)
    g.players["p2"]["budget"] = 100  # peut miser 100, pas surenchérir
    g.bid("p1", 100)
    assert g.index == 1 and g.last_result["winner_id"] == "p1"


def test_cannot_afford_minimum_is_folded(make_game):
    g = make_game(n=3)
    g.players["p3"]["budget"] = OPENING_MIN - 1
    g.index = -1
    g.next_item()
    assert "p3" in g.auction["folded"]
    with pytest.raises(GameError):
        g.bid("p3", OPENING_MIN)


def test_poor_player_can_still_open_below_price(make_game):
    g = make_game(n=2)
    g.players["p2"]["budget"] = 30
    g.index = -1
    g.next_item()
    assert "p2" not in g.auction["folded"]
    g.bid("p2", 30)
    assert g.auction["leader"] == "p2"


def test_fold_twice_rejected(make_game):
    g = make_game(n=3)
    g.fold("p1")
    with pytest.raises(GameError):
        g.fold("p1")


def test_game_finishes_after_last_item(make_game):
    g = make_game(n=2, item_count=6)
    for _ in range(6):
        g.on_timeout(g.version)
    assert g.phase == "finished" and g.results is not None


def test_budget_never_negative(make_game, clock):
    g = make_game(n=2, budget=1200, item_count=10)
    while g.phase == "auction":
        a = g.auction
        pid = "p1" if g.players["p1"]["budget"] >= a["price"] else "p2"
        if g.players[pid]["budget"] >= a["price"]:
            g.bid(pid, a["price"])
        g.on_timeout(g.version)
    assert all(p["budget"] >= 0 for p in g.players.values())


def test_legacy_modes_are_migrated():
    assert normalize_mode("construction") == "normal"
    assert normalize_mode("survie") == "normal"
    assert normalize_mode("aveugle") == "aveugle"
    assert validate_settings({"mode": "survie"})["mode"] == "normal"
    assert validate_settings({"mode": "construction", "trial_pack": "x"})["mode"] == "normal"
    assert validate_settings(None)["mode"] == "normal"
    with pytest.raises(GameError):
        normalize_mode(None)
