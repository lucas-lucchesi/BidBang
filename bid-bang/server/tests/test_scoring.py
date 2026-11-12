"""Formule de points : pertinence pour la situation, jamais prix ni rareté."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from app import criteria, scoring
from app.errors import GameError
from app.items import catalog_item_map

CAT = catalog_item_map()
ZOMBIE = criteria.get_template("apocalypse_zombie")["criteria"]
WEDDING = criteria.get_template("mariage")["criteria"]
VILLA = criteria.get_template("villa_luxueuse")["criteria"]


def by_name(name):
    return next(i for i in CAT.values() if i["name"] == name)


def pts(name, crit):
    return scoring.item_points(by_name(name), crit)


def item(attrs, rarity=0, price=100, base=20):
    return {"id": "x", "name": "x", "price": price, "rarity": rarity, "base_points": base,
            "attributes": attrs}


def test_useful_item_beats_useless_item():
    assert pts("Trousse médicale", ZOMBIE) > pts("Jacuzzi", ZOMBIE) + 40
    assert pts("Véhicule blindé", ZOMBIE) > pts("Œuvre d'art", ZOMBIE) + 40


def test_same_item_scores_differently_by_situation():
    assert pts("Jacuzzi", ZOMBIE) < 15 < 60 < pts("Jacuzzi", VILLA)
    assert pts("Trousse médicale", ZOMBIE) > 50 > pts("Trousse médicale", WEDDING)
    assert pts("Fontaine de chocolat", WEDDING) > pts("Fontaine de chocolat", ZOMBIE)
    assert pts("Véhicule blindé", ZOMBIE) > 3 * pts("Véhicule blindé", VILLA)


def test_rarity_and_price_do_not_change_points():
    base = item({"soins": 4})
    for rarity in range(4):
        for price in (20, 150, 600):
            assert scoring.item_points({**base, "rarity": rarity, "price": price}, ZOMBIE) \
                   == scoring.item_points(base, ZOMBIE)


def test_common_essential_beats_useless_legendary():
    common = item({"soins": 5}, rarity=0, price=40)
    legendary = item({"luxe": 5, "decoration": 5, "confort": 5}, rarity=3, price=600, base=20)
    assert scoring.item_points(common, ZOMBIE) > scoring.item_points(legendary, ZOMBIE) + 40


def test_many_attributes_are_not_an_automatic_advantage():
    focused = item({"soins": 5})
    scattered = item({"soins": 1, "confort": 5, "luxe": 5, "decoration": 5, "nature": 5,
                      "divertissement": 5})
    assert scoring.item_points(focused, ZOMBIE) > scoring.item_points(scattered, ZOMBIE)
    # un objet qui touche à tout superficiellement ne dépasse pas un objet très pertinent
    many_weak = item({"soins": 2, "eau": 2, "nourriture": 2, "protection": 2, "transport": 2})
    assert scoring.item_points(focused, ZOMBIE) > scoring.item_points(many_weak, ZOMBIE)


def test_extra_relevant_attributes_have_diminishing_value():
    one = scoring.relevance(item({"soins": 5}), ZOMBIE)
    two = scoring.relevance(item({"soins": 5, "eau": 5}), ZOMBIE)
    assert one < two <= 1.0
    assert two - one < one  # le 2e critère apporte moins que le 1er


def test_importance_matters():
    crit = [{"id": "soins", "necessary": True, "importance": 5},
            {"id": "confort", "necessary": True, "importance": 1}]
    assert scoring.item_points(item({"soins": 3}), crit) > scoring.item_points(item({"confort": 3}), crit)


def test_non_necessary_criteria_give_nothing():
    crit = [{"id": "soins", "necessary": True, "importance": 5},
            {"id": "luxe", "necessary": False, "importance": 0}]
    a = scoring.item_points(item({"soins": 3}), crit)
    assert scoring.item_points(item({"soins": 3, "luxe": 5}), crit) == a


def test_points_bounds_and_minimum():
    for it in CAT.values():
        for crit in (ZOMBIE, WEDDING, VILLA):
            assert 1 <= scoring.item_points(it, crit) <= 100
    assert scoring.item_points(item({}, base=0), ZOMBIE) == 1  # objet inutile : 1 point
    perfect = item({c["id"]: 5 for c in ZOMBIE if c["necessary"]}, base=50)
    assert scoring.item_points(perfect, ZOMBIE) == 100


def test_degenerate_inputs():
    # situation sans critère nécessaire : seul base_points compte, jamais d'erreur
    none_needed = [{"id": "luxe", "necessary": False, "importance": 0}]
    assert scoring.item_points(item({"luxe": 5}, base=0), none_needed) == 1
    assert scoring.item_points(item({"luxe": 5}, base=50), []) == 11
    # critère inconnu de l'objet, valeurs négatives ou hors limites : ignorés / bornés
    odd = item({"soins": -3, "inconnu": 4, "eau": 99, "nourriture": True, "x": "5"})
    assert 1 <= scoring.item_points(odd, ZOMBIE) <= 100
    assert scoring.item_points(odd, ZOMBIE) == scoring.item_points(item({"eau": 5}), ZOMBIE)
    weird = [{"id": "soins", "necessary": True, "importance": -4},
             {"id": "inexistant", "necessary": True, "importance": 5}]
    assert scoring.item_points(item({"soins": 5}, base=0), weird) == 1
    assert scoring.item_points({"attributes": None, "base_points": -50}, ZOMBIE) == 1
    assert scoring.item_points({"attributes": {"soins": 5}, "base_points": 10**6}, ZOMBIE) <= 100


def test_deterministic_and_config_is_tunable():
    a = [scoring.item_points(i, ZOMBIE) for i in CAT.values()]
    assert a == [scoring.item_points(i, ZOMBIE) for i in CAT.values()]
    tuned = scoring.ScoringConfig(relevance_span=50.0, base_span=0.0)
    assert scoring.item_points(by_name("Trousse médicale"), ZOMBIE, tuned) < 55


def test_freeze_returns_independent_copy_with_points():
    original = by_name("Trousse médicale")
    snapshot = deepcopy(original)
    frozen = scoring.freeze_item(original, ZOMBIE)
    assert original == snapshot and "points" not in original  # source intacte
    assert frozen["points"] == scoring.item_points(original, ZOMBIE)
    assert frozen["useful_criteria"][0] == "soins" and frozen["usefulness"] == "high"
    frozen["attributes"]["soins"] = 1
    assert original["attributes"]["soins"] == 5  # copie indépendante
    assert scoring.freeze_item(by_name("Jacuzzi"), ZOMBIE)["usefulness"] in ("none", "low")


def test_catalog_best_items_are_not_just_the_rarest():
    """Apocalypse : le haut du classement n'est pas fait que d'objets rares ; un commun
    indispensable dépasse un légendaire de luxe. (En situation de luxe, les objets de luxe
    gagnent : c'est voulu, la situation le demande.)"""
    top = sorted(CAT.values(), key=lambda i: -scoring.item_points(i, ZOMBIE))[:8]
    assert sum(1 for i in top if i["rarity"] <= 1) >= 3 and any(i["rarity"] == 0 for i in top)
    assert pts("Trousse médicale", ZOMBIE) > pts("Limousine", ZOMBIE)


def test_clean_criteria_validation():
    ok = criteria.clean_criteria([{"id": "Décoration", "necessary": True, "importance": 4},
                                  {"id": "luxe", "necessary": False, "importance": 3}])
    assert ok == [{"id": "decoration", "necessary": True, "importance": 4},
                  {"id": "luxe", "necessary": False, "importance": 0}]
    bad = [
        [], "x", [{"id": "inconnu", "necessary": True, "importance": 3}],
        [{"id": "soins", "necessary": True, "importance": 0}],
        [{"id": "soins", "necessary": True, "importance": 6}],
        [{"id": "soins", "necessary": True, "importance": -1}],
        [{"id": "soins", "necessary": True}],
        [{"id": "soins", "necessary": "oui", "importance": 3}],
        [{"id": "soins", "necessary": True, "importance": 3}, {"id": "soins", "necessary": True, "importance": 2}],
        [{"id": "soins", "necessary": False}],  # aucun critère nécessaire
        [{"id": 5, "necessary": True, "importance": 3}],
    ]
    for raw in bad:
        with pytest.raises(GameError):
            criteria.clean_criteria(raw)
    assert criteria.clean_criteria([{"id": "soins", "necessary": False}], require_necessary=False)


def test_registry_can_be_extended_without_touching_the_engine(tmp_path, monkeypatch):
    data = json.loads(criteria.CRITERIA_PATH.read_text(encoding="utf-8"))
    data["criteria"].append({"id": "magie", "label": "Magie"})
    p = tmp_path / "criteria.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(criteria, "CRITERIA_PATH", p)
    criteria._load.cache_clear()
    try:
        crit = criteria.clean_criteria([{"id": "magie", "necessary": True, "importance": 5}])
        assert scoring.item_points(item({"magie": 5}), crit) > 50
    finally:
        monkeypatch.undo()
        criteria._load.cache_clear()
