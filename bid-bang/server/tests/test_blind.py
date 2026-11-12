import pytest

from app.errors import GameError
from app.game import OPENING_MIN


@pytest.fixture
def blind(make_game):
    return lambda n=3, **kw: make_game(n=n, mode="aveugle", **kw)


def test_other_bids_hidden_in_snapshot(blind):
    g = blind()
    g.bid("p1", 300)
    a = g.snapshot("p2")["auction"]
    assert a["blind"] and a["submitted"] == ["p1"] and a["your_bid"] is None
    assert a["current_bid"] is None and a["leader_id"] is None
    assert g.snapshot("p1")["auction"]["your_bid"] == 300
    assert 300 not in g.snapshot("p2")["auction"].values()


def test_resolves_when_everyone_played_highest_wins_pays_own_bid(blind):
    g = blind()
    item = g.auction["item"]
    g.bid("p1", 200)
    g.bid("p2", 350)
    assert g.index == 0
    g.fold("p3")
    assert g.index == 1
    assert g.players["p2"]["items"] == [item]
    assert g.players["p2"]["budget"] == 2200 - 350
    assert g.players["p1"]["budget"] == 2200
    assert g.last_result["winner_id"] == "p2" and g.last_result["purchase_price"] == 350
    amounts = {b["player_id"]: b["amount"] for b in g.last_result["bids"]}
    assert amounts == {"p1": 200, "p2": 350, "p3": 0}


def test_tie_goes_to_first_sender(blind):
    g = blind(n=2)
    g.bid("p2", 100)
    g.bid("p1", 100)
    assert g.last_result["winner_id"] == "p2"


def test_everyone_passes_unsold(blind):
    g = blind(n=2)
    g.fold("p1")
    g.fold("p2")
    assert g.last_result["winner_id"] is None and g.index == 1


def test_timeout_resolves_with_sealed_bids(blind, clock):
    g = blind()
    g.bid("p1", 120)
    clock.advance(99)
    assert g.on_timeout(g.version)
    assert g.last_result["winner_id"] == "p1" and g.index == 1


def test_timer_not_reset_by_bids(blind, clock):
    g = blind()
    deadline = g.auction["deadline"]
    clock.advance(3)
    g.bid("p1", 100)
    assert g.auction["deadline"] == deadline


def test_cannot_play_twice(blind):
    g = blind()
    g.bid("p1", 100)
    with pytest.raises(GameError):
        g.bid("p1", 200)
    with pytest.raises(GameError):
        g.fold("p1")


def test_bid_limits(blind):
    g = blind()
    with pytest.raises(GameError):
        g.bid("p1", OPENING_MIN - 1)
    with pytest.raises(GameError):
        g.bid("p1", 99999)
    with pytest.raises(GameError):
        g.bid("p1", "100")


def test_broke_player_auto_passes(blind):
    g = blind(n=2)
    g.players["p2"]["budget"] = 0
    g.index = -1
    g.next_item()
    g.bid("p1", 50)
    assert g.last_result["winner_id"] == "p1"


def test_full_blind_game_scores_sum_of_points_only(blind):
    g = blind(n=3, item_count=6)
    for _ in range(6):
        g.bid("p1", 50)
        g.fold("p2")
        g.fold("p3")
    assert g.phase == "finished"  # pas de phase de vote
    row = next(r for r in g.results if r["player_id"] == "p1")
    assert row["score"] == sum(i["points"] for i in g.players["p1"]["items"])
    assert row["total_spent"] == 300 and g.players["p1"]["budget"] == 2200 - 300
