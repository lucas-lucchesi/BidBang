"""Points figés, score = somme des points, prix estimé / prix payé, économies, classements."""
import random
from copy import deepcopy

import pytest

from app import catalog, scoring
from app.game import Game, purchase_row


def play(g, plan):
    """plan : liste de (pid, mise) par objet ; pid None = personne ne mise (invendu)."""
    for pid, amount in plan:
        if pid is not None:
            g.bid(pid, amount)
        g.on_timeout(g.version)
    assert g.phase == "finished"


def make(clock, n=2, **kw):
    kw.setdefault("item_count", 6)
    players = [(f"p{i}", f"J{i}") for i in range(1, n + 1)]
    return Game(players, {"theme_id": "cabane", **kw}, rng=random.Random(5), clock=clock)


def test_points_are_frozen_at_start_and_identical_for_everyone(clock):
    g = make(clock)
    crit = g.situation["criteria"]
    for it in g.items:
        assert it["points"] == scoring.item_points(it, crit) and 1 <= it["points"] <= 100
    seen = g.snapshot("p1")["auction"]["item"], g.snapshot("p2")["auction"]["item"]
    assert seen[0] == seen[1]  # même objet, mêmes points pour tous les joueurs


def test_points_do_not_depend_on_what_others_bought(clock):
    g = make(clock)
    before = {i["id"]: i["points"] for i in g.items}
    g.bid("p1", 100)
    g.on_timeout(g.version)
    g.bid("p2", 200)
    g.on_timeout(g.version)
    assert {i["id"]: i["points"] for i in g.items} == before
    nxt = g.items[g.index]
    assert nxt["points"] == before[nxt["id"]]


def test_catalog_changes_do_not_affect_a_running_game(clock, monkeypatch):
    g = make(clock)
    frozen = deepcopy(g.items)
    raw = catalog.load_catalog()
    monkeypatch.setattr(catalog, "_load", lambda: raw)
    for it in raw["items"]:  # on « modifie la bibliothèque » en cours de partie
        it["price"] += 1000
        it["base_points"] = 0
        it["attributes"] = {"luxe": 5}
    try:
        assert g.items == frozen
        assert g.snapshot("p1")["auction"]["item"] == frozen[0]
    finally:
        for it, orig in zip(raw["items"], __import__("json").load(open(catalog.CATALOG_PATH, encoding="utf-8"))["items"]):
            it.update(orig)


def test_game_items_are_independent_copies(clock):
    g = make(clock)
    g.items[0]["attributes"]["abri"] = 99
    g.items[0]["price"] = 1
    again = make(clock)
    assert again.items[0]["attributes"].get("abri") != 99 and again.items[0]["price"] != 1
    assert all(i["attributes"].get("abri", 0) != 99
               for i in catalog.get_items("cabane"))  # le catalogue n'a pas bougé


def test_score_is_only_the_sum_of_points(clock):
    g = make(clock, n=3)
    play(g, [("p1", 100), ("p2", 130), ("p1", 90), (None, 0), ("p3", 60), ("p2", 50)])
    for r in g.results:
        owned = g.players[r["player_id"]]["items"]
        assert r["score"] == sum(i["points"] for i in owned)  # rareté, synergies : rien d'autre
    assert set(g.results[0]) >= {"score", "estimated_value", "total_spent", "savings", "budget", "rank"}
    for gone in ("items_points", "synergy_points", "trials", "votes", "vote_points"):
        assert gone not in g.results[0]


def test_estimated_price_stays_distinct_from_purchase_price(clock):
    g = make(clock)
    item = g.auction["item"]
    est = item["price"]
    g.bid("p1", est - 50 if est > 60 else 30)
    paid = g.auction["bid"]
    g.on_timeout(g.version)
    pu = g.players["p1"]["purchases"][0]
    assert pu["purchase_price"] == paid and pu["item"]["price"] == est != paid
    assert "price" not in pu  # plus d'ambiguïté : `price` n'existe que sur l'objet
    assert g.last_result["purchase_price"] == paid and g.last_result["item"]["price"] == est
    row = purchase_row(pu)
    assert row["savings"] == est - paid
    assert g.snapshot("p2")["players"][0]["purchases"][0]["savings"] == est - paid


def test_totals_savings_and_overpayment(clock):
    g = make(clock)
    prices = [i["price"] for i in g.items]
    plan = [("p1", prices[0] - 30), ("p1", prices[1] + 70)] + [(None, 0)] * 4
    play(g, plan)
    r = {x["player_id"]: x for x in g.results}["p1"]
    assert r["estimated_value"] == prices[0] + prices[1]
    assert r["total_spent"] == prices[0] + prices[1] + 40
    assert r["savings"] == -40 == r["estimated_value"] - r["total_spent"]
    assert [p["savings"] for p in r["purchases"]] == [30, -70]  # économie puis surcoût
    assert r["budget"] == 2200 - r["total_spent"]
    assert {x["player_id"]: x for x in g.results}["p2"]["savings"] == 0


def test_player_without_purchase_has_zero_everything(clock):
    g = make(clock)
    play(g, [(None, 0)] * 6)
    for r in g.results:
        assert (r["score"], r["items_count"], r["estimated_value"], r["total_spent"], r["savings"]) == (0, 0, 0, 0, 0)
    assert g.awards["best_bidder"] is None and g.awards["best_deal"] is None
    assert g.awards["most_useful"] is None and g.awards["most_valuable"] is None


def fake_results(*rows):
    out = []
    for n, (pid, score, budget, buys) in enumerate(rows):
        purchases = [{"item": {"id": f"{pid}{k}", "price": est, "points": 1}, "purchase_price": paid,
                      "savings": est - paid} for k, (est, paid) in enumerate(buys)]
        est = sum(b[0] for b in buys)
        spent = sum(b[1] for b in buys)
        out.append({"player_id": pid, "pseudo": pid, "score": score, "budget": budget,
                    "items_count": len(buys), "purchases": purchases, "estimated_value": est,
                    "total_spent": spent, "savings": est - spent})
    return out


def test_bargain_ranking_and_awards_are_informative_only():
    # Alex gagne aux points mais Emma est la meilleure enchérisseuse
    rows = fake_results(("alex", 120, 1130, [(500, 320), (850, 750)]),
                        ("thomas", 95, 1000, [(1100, 1200)]),
                        ("emma", 80, 1500, [(900, 700)]),
                        ("zoe", 0, 2200, []))
    bargains = Game.compute_bargains(rows)
    assert [b["player_id"] for b in bargains] == ["alex", "emma", "thomas", "zoe"]
    assert [b["savings"] for b in bargains] == [280, 200, -100, 0]
    assert bargains[-1]["items_count"] == 0  # sans achat : en fin de liste
    aw = Game.compute_awards(rows)
    assert aw["best_bidder"]["player_id"] == "alex" and aw["best_bidder"]["value"] == 280
    assert aw["best_deal"]["player_id"] == "emma" and aw["best_deal"]["value"] == 200  # 900 -> 700
    assert aw["most_valuable"]["player_id"] == "alex" and aw["most_useful"]["player_id"] == "alex"
    assert all(a is None or a["player_id"] != "zoe" for a in aw.values())


def test_no_best_bidder_when_nobody_saved_money_and_none_for_buyerless():
    rows = fake_results(("a", 50, 900, [(100, 150)]), ("b", 0, 2200, []))
    aw = Game.compute_awards(rows)
    assert aw["best_bidder"] is None and aw["best_deal"] is None  # surcoût : pas de distinction
    assert aw["most_valuable"]["player_id"] == "a"
    assert Game.compute_awards(fake_results(("b", 0, 2200, []))) == {
        "best_bidder": None, "best_deal": None, "most_valuable": None, "most_useful": None}


def test_financial_ranking_never_changes_the_main_winner(clock):
    g = make(clock, n=3)
    prices = [i["price"] for i in g.items]
    # p2 fait de très bonnes affaires, p1 surpaie mais prend les objets les plus utiles
    order = sorted(range(6), key=lambda k: -g.items[k]["points"])
    plan = [(None, 0)] * 6
    for rank, k in enumerate(order):
        plan[k] = ("p1", prices[k] + 100) if rank < 3 else ("p2", 10) if rank < 5 else (None, 0)
    before = deepcopy(g.items)
    play(g, plan)
    winner = g.results[0]
    assert winner["winner"] and winner["player_id"] == "p1"
    assert g.bargains[0]["player_id"] == "p2" != winner["player_id"]
    assert g.awards["best_bidder"]["player_id"] == "p2"
    assert [r["rank"] for r in g.results] == sorted(r["rank"] for r in g.results)
    assert g.results[0]["score"] == max(r["score"] for r in g.results)
    assert g.items == before


def test_tie_broken_by_remaining_budget_then_shared_win(clock):
    g = make(clock, n=3)
    g.phase = "finished"  # on reconstruit directement des joueurs à égalité de points
    it = {"id": "x", "name": "x", "price": 100, "points": 40, "rarity": 0}
    for pid, budget in (("p1", 500), ("p2", 900), ("p3", 900)):
        g.players[pid]["budget"] = budget
        g.players[pid]["purchases"] = [{"item": it, "purchase_price": 100}]
    rows = g.compute_results()
    assert [(r["player_id"], r["rank"], r["winner"]) for r in rows] == [
        ("p2", 1, True), ("p3", 1, True), ("p1", 3, False)]  # co-vainqueurs, puis 3e
    g.players["p3"]["budget"] = 800
    rows = g.compute_results()
    assert [r["player_id"] for r in rows] == ["p2", "p3", "p1"]
    assert [r["rank"] for r in rows] == [1, 2, 3] and rows[0]["winner"] and not rows[1]["winner"]


def test_higher_score_beats_higher_budget():
    g = Game([("a", "A"), ("b", "B")], {"theme_id": "cabane", "item_count": 6}, rng=random.Random(1))
    g.players["a"]["budget"], g.players["b"]["budget"] = 10, 2000
    g.players["a"]["purchases"] = [{"item": {"price": 50, "points": 60}, "purchase_price": 40}]
    g.players["b"]["purchases"] = [{"item": {"price": 50, "points": 59}, "purchase_price": 40}]
    assert g.compute_results()[0]["player_id"] == "a"


@pytest.mark.parametrize("mode", ["normal", "aveugle"])
def test_both_auction_modes_use_the_same_scoring(clock, mode):
    g = Game([("p1", "A"), ("p2", "B")],
             {"theme_id": "plage", "mode": mode, "item_count": 6}, rng=random.Random(2), clock=clock)
    for _ in range(6):
        g.bid("p1", 40)
        if mode == "aveugle":
            g.fold("p2")
        else:
            g.on_timeout(g.version)
    assert g.phase == "finished"
    top = g.results[0]
    assert top["player_id"] == "p1" and top["score"] == sum(i["points"] for i in g.items)
    assert top["total_spent"] == 240 and top["savings"] == sum(i["price"] for i in g.items) - 240
    assert g.snapshot("p1")["bargains"][0]["player_id"] == "p1"
    assert g.snapshot("p1")["awards"]["most_useful"]["player_id"] == "p1"


def catalog_items_for(ids):
    from app.items import catalog_item_map
    m = catalog_item_map()
    return [m[i] for i in ids]


def test_three_creation_types_score_the_same_way(clock):
    """Classique et personnalisée : formule des critères. IA : points de l'IA. Dans les trois cas,
    le score est la somme des points figés."""
    crit = [{"id": "eau", "necessary": True, "importance": 5},
            {"id": "abri", "necessary": True, "importance": 3}]
    ids = [f"plage_{n:02d}" for n in range(1, 9)]
    classic = Game([("a", "A"), ("b", "B")], {"theme_id": "plage", "item_count": 6},
                   rng=random.Random(1), clock=clock)
    custom = Game([("a", "A"), ("b", "B")],
                  {"creation_type": "custom", "item_count": 6, "item_ids": ids,
                   "scenario": {"description": "Une île sans eau potable.", "criteria": crit}},
                  rng=random.Random(1), clock=clock)
    cards = [{"id": f"ai_{n}", "name": f"Carte {n}", "price": 100 + n, "rarity": 0, "base_points": 0,
              "attributes": {}, "points": 10 * n, "category": "Milieu", "source": "ai"}
             for n in range(1, 9)]
    ai = Game([("a", "A"), ("b", "B")],
              {"creation_type": "ai", "item_count": 6, "item_ids": [c["id"] for c in cards],
               "scenario": {"description": "Une île sans eau potable.", "criteria": []}},
              rng=random.Random(1), clock=clock, pool=cards)
    for g in (classic, custom):
        for it in g.items:
            assert it["points"] == scoring.item_points(it, g.situation["criteria"])
    assert all(i["points"] == int(i["id"][3:]) * 10 for i in ai.items)  # points de l'IA, inchangés
    for g in (classic, custom, ai):
        for _ in range(6):
            g.bid("a", 50)
            g.on_timeout(g.version)
        assert g.phase == "finished"
        assert g.results[0]["score"] == sum(i["points"] for i in g.items)
