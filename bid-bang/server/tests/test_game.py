import pytest

from app.errors import GameError
from app.game import Game, item_points, min_step, synergy_points, validate_settings


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
    assert g.required_bid() == g.auction["price"]


def test_first_bid_at_least_start_price(make_game):
    g = make_game()
    price = g.auction["price"]
    with pytest.raises(GameError):
        g.bid("p1", price - 1)
    g.bid("p1", price)
    assert g.auction["leader"] == "p1"


def test_outbid_needs_step(make_game):
    g = make_game()
    price, step = g.auction["price"], g.auction["step"]
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
    g.players["p2"]["budget"] = g.auction["price"]  # peut miser le prix, pas surenchérir
    g.bid("p1", g.auction["price"])
    assert g.index == 1 and g.last_result["winner_id"] == "p1"


def test_cannot_afford_start_price_is_folded(make_game):
    g = make_game(n=3)
    g.players["p3"]["budget"] = 0
    g.index = -1
    g.next_item()
    assert "p3" in g.auction["folded"]
    with pytest.raises(GameError):
        g.bid("p3", g.auction["price"])


def test_fold_twice_rejected(make_game):
    g = make_game(n=3)
    g.fold("p1")
    with pytest.raises(GameError):
        g.fold("p1")


def test_game_finishes_after_last_item(make_game):
    g = make_game(item_count=6)
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


def test_item_points_and_synergies():
    a = {"stats": {"x": 2, "y": 3}, "rarity": 2, "tags": ["t1", "t2"]}
    b = {"stats": {"x": 1}, "rarity": 0, "tags": ["t1"]}
    c = {"stats": {"x": 1}, "rarity": 0, "tags": ["t1", "t2"]}
    assert item_points(a, "construction") == 5 + 4
    assert item_points(a, "survie") == 5
    assert synergy_points([a, b]) == 3
    assert synergy_points([a, b, c]) == 3 * 2 + 3 * 1
    assert synergy_points([a]) == 0
