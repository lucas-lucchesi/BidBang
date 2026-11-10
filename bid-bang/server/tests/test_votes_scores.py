import pytest

from app.errors import GameError


def finish_auctions(g):
    while g.phase == "auction":
        g.on_timeout(g.version)


def buy(g, pid, item_index=None):
    """Fait gagner l'objet courant à pid au prix de départ."""
    g.bid(pid, g.auction["price"])
    g.on_timeout(g.version)


def test_voting_opens_with_three_players(make_game):
    g = make_game(n=3, mode="construction")
    finish_auctions(g)
    assert g.phase == "voting" and g.vote_deadline is not None


def test_no_vote_with_two_players(make_game):
    g = make_game(n=2, mode="construction")
    finish_auctions(g)
    assert g.phase == "finished"


def test_no_vote_in_survival(make_game):
    g = make_game(n=3, mode="survie")
    finish_auctions(g)
    assert g.phase == "finished"


def test_vote_rules(make_game):
    g = make_game(n=3)
    with pytest.raises(GameError):
        g.vote("p1", "p2")  # pas encore ouvert
    finish_auctions(g)
    with pytest.raises(GameError):
        g.vote("p1", "p1")
    with pytest.raises(GameError):
        g.vote("p1", "zzz")
    g.vote("p1", "p2")
    assert g.phase == "voting"


def test_all_votes_finish_and_score(make_game):
    g = make_game(n=3)
    finish_auctions(g)
    g.vote("p1", "p2")
    g.vote("p3", "p2")
    g.vote("p2", "p1")
    assert g.phase == "finished"
    row = {r["player_id"]: r for r in g.results}
    assert row["p2"]["votes"] == 2 and row["p2"]["vote_points"] == 16
    assert row["p1"]["vote_points"] == 8
    assert row["p3"]["vote_points"] == 0
    assert g.results[0]["player_id"] == "p2"


def test_vote_timeout_finishes(make_game, clock):
    g = make_game(n=3)
    finish_auctions(g)
    clock.advance(46)
    assert g.on_timeout(g.version)
    assert g.phase == "finished"


def test_vote_can_be_changed(make_game):
    g = make_game(n=4)
    finish_auctions(g)
    g.vote("p1", "p2")
    g.vote("p1", "p3")
    assert g.votes["p1"] == "p3"


def test_ranking_tiebreak_by_budget_then_coop(make_game):
    g = make_game(n=2, mode="survie")
    finish_auctions(g)
    rows = g.results
    # personne n'a rien acheté : mêmes budgets -> co-vainqueurs
    assert all(r["winner"] for r in rows) and all(r["rank"] == 1 for r in rows)


def test_ranking_budget_breaks_tie(make_game):
    g = make_game(n=2, mode="survie")
    g.players["p1"]["budget"] = 500
    g.players["p2"]["budget"] = 100
    g.finish()
    assert g.results[0]["player_id"] == "p1" and g.results[0]["winner"]
    assert g.results[1]["rank"] == 2 and not g.results[1]["winner"]


def test_survival_trials_scoring(make_game):
    g = make_game(n=2, mode="survie", item_count=6)
    trial = g.location["survival"]["trials"][0]
    stat, thr = trial["stat"], trial["threshold"]
    ok_item = {"id": "x", "stats": {k: 0 for k in g.items[0]["stats"]}, "tags": ["z"],
               "rarity": 0, "price": 1, "name": "x"}
    ok_item["stats"][stat] = thr
    g.players["p1"]["items"] = [ok_item]
    t = g.trial_results("p1")[0]
    assert t["success"] and t["points"] == 18
    ok_item["stats"][stat] = thr // 2
    t = g.trial_results("p1")[0]
    assert not t["success"] and t["points"] == round(9 * (thr // 2) / thr)


def test_survival_threshold_scales_with_item_count(make_game):
    g6 = make_game(mode="survie", item_count=6)
    g10 = make_game(mode="survie", item_count=10)
    base = g6.location["survival"]["trials"][0]["threshold"]
    assert g6.trial_results("p1")[0]["threshold"] == base
    assert g10.trial_results("p1")[0]["threshold"] == round(base * 10 / 6)


def test_construction_has_no_trials(make_game):
    g = make_game(n=2, mode="construction")
    assert g.trial_results("p1") == []
