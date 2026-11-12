"""Profil de génération : l'objectif de la partie contraint les cartes. Réponses IA simulées,
aucune clé, aucun réseau. Vérifie surtout qu'une carte hors sujet n'entre jamais dans la partie,
qu'aucune carte du catalogue n'est ajoutée, et qu'une génération insuffisante échoue franchement."""
import json
import logging

import pytest
from starlette.testclient import TestClient

from app.ai import base as ai_base
from app.ai import debug, generator, limits
from app.ai import profile as profile_mod
from app.errors import GameError
from app.game import Game
from app.items import catalog_item_map
from app.main import app
from app.rooms import registry

KEY = "sk-ant-TESTSECRET-0123456789abcdef"
FALLBACK = {"title": "T", "description": "Une situation de test."}
ROLES = ["Gardien", "Défenseur", "Milieu", "Attaquant"]


def prof(**over):
    p = {"goal": "Composer un onze historique", "allowed_entity_types": ["football_player"],
         "real_entities_only": True, "organization": "Olympique de Marseille",
         "required_roles": ROLES, "allow_unrelated_items": False}
    p.update(over)
    return p


def card(name, role="Milieu", kind="football_player", real=True, pts=50, **over):
    d = {"name": name, "description": f"{name}, fait vérifiable.", "category": role,
         "entity_type": kind, "is_real": real, "rarity": 1, "price": 150, "points": pts}
    d.update(over)
    return d


OM = [card("Steve Mandanda", "Gardien", pts=80), card("Fabien Barthez", "Gardien", pts=88),
      card("Basile Boli", "Défenseur", pts=90), card("Marcel Desailly", "Défenseur central", pts=92),
      card("Eric Abidal", "Défenseur", pts=60), card("Didier Deschamps", "Milieu", pts=75),
      card("Abedi Pelé", "Milieu", pts=91), card("Mathieu Valbuena", "Milieu", pts=70),
      card("Jean-Pierre Papin", "Attaquant", pts=98), card("Didier Drogba", "Attaquant", pts=95),
      card("Mamadou Niang", "Attaquant", pts=72), card("Franck Ribéry", "Milieu", pts=40)]


def body(items, profile=None, title="Titre", description="Description de la partie."):
    return json.dumps({"title": title, "description": description,
                       "profile": profile if profile is not None else prof(), "items": items})


class Script:
    """Faux fournisseur : renvoie les réponses dans l'ordre (la dernière se répète)."""
    name, label = "anthropic", "Fake"

    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls: list[dict] = []

    async def complete(self, *, api_key, system, prompt, max_tokens, timeout):
        self.calls.append({"prompt": prompt, "system": system, "api_key": api_key})
        i = min(len(self.calls) - 1, len(self.texts) - 1)
        return self.texts[i]


@pytest.fixture(autouse=True)
def _limits(monkeypatch):
    limits.reset()
    monkeypatch.setattr(limits, "MIN_INTERVAL_SECONDS", 0.0)
    yield
    limits.reset()


@pytest.fixture
def client():
    registry.rooms.clear()
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def use(monkeypatch, *texts):
    p = Script(*texts)
    monkeypatch.setattr(ai_base, "get_provider", lambda name: p)
    return p


def room(client, scenario="Le meilleur onze historique de l'Olympique de Marseille.", **over):
    s = {"creation_type": "ai", "mode": "normal", "item_count": 6, "scenario": {"description": scenario}}
    s.update(over)
    r = client.post("/rooms", json={"pseudo": "Alice", "settings": s})
    assert r.status_code == 200, r.text
    return r.json()


def auth(s):
    return {"Authorization": f"Bearer {s['token']}"}


def gen(client, s):
    return client.post(f"/rooms/{s['code']}/ai/generate", json={"provider": "anthropic", "api_key": KEY},
                       headers=auth(s))


def names(resp):
    return [i["name"] for i in resp.json()["items"]]


# ------------------------------------------------------- 1. onze historique de l'OM
def test_om_only_real_players_with_several_positions(client, monkeypatch):
    junk = [card("Limousine", "Matériel", kind="decoration", real=False),
            card("Gandalf", "Gardien", real=False),                 # fictif : refusé (réel exigé)
            card("Buteur argenté", "Attaquant", real=False),         # inventé : refusé
            card("Entraîneur charismatique", "Entraîneur"),          # rôle non prévu
            card("Ballon officiel", "Milieu", kind="equipment")]     # même thème, mais pas un joueur
    use(monkeypatch, body(OM + junk))
    s = room(client)
    r = gen(client, s)
    assert r.status_code == 200, r.text
    got = names(r)
    assert sorted(got) == sorted(c["name"] for c in OM)
    for bad in ("Limousine", "Gandalf", "Buteur argenté", "Entraîneur charismatique", "Ballon officiel"):
        assert bad not in got
    items = r.json()["items"]
    assert {i["entity_type"] for i in items} == {"football_player"} and all(i["is_real"] for i in items)
    assert {"Gardien", "Défenseur", "Milieu", "Attaquant"} <= {i["category"].split()[0] for i in items}
    assert r.json()["profile"]["organization"] == "Olympique de Marseille"
    assert r.json()["profile"]["real_entities_only"] is True


# ------------------------------------------------------------------ 2. équipe Marvel
def test_marvel_team_only_compatible_characters(client, monkeypatch):
    p = prof(goal="Composer l'équipe de Marvel la plus forte", allowed_entity_types=["marvel_character"],
             organization="Marvel", required_roles=["Combattant", "Stratège", "Soutien"], real_entities_only=False)
    cards = [card(n, r, kind="marvel_character", real=False, pts=pt) for n, r, pt in [
        ("Captain America", "Combattant", 85), ("Hulk", "Combattant", 90), ("Iron Man", "Stratège", 92),
        ("Black Widow", "Soutien", 70), ("Hawkeye", "Soutien", 55), ("Doctor Strange", "Stratège", 95),
        ("Thor", "Combattant", 96)]]
    bad = [card("Gandalf", "Stratège", kind="fantasy_character", real=False),
           card("Bouclier en vibranium", "Soutien", kind="equipment", real=False),
           card("Lionel Messi", "Combattant", kind="football_player")]
    use(monkeypatch, body(cards + bad, p))
    r = gen(client, room(client, "Une équipe Marvel pour sauver le monde."))
    got = names(r)
    assert set(got) == {c["name"] for c in cards}
    assert {"Gandalf", "Bouclier en vibranium", "Lionel Messi"}.isdisjoint(got)


# ------------------------------------------------------------------------ 3. startup
def test_startup_recruiting_only_professional_profiles(client, monkeypatch):
    p = prof(goal="Recruter l'équipe fondatrice d'une startup", allowed_entity_types=["job"],
             real_entities_only=False, organization=None, required_roles=["Tech", "Produit", "Vente"])
    cards = [card(n, r, kind="job", real=False, pts=pt) for n, r, pt in [
        ("Développeuse backend", "Tech", 88), ("Ingénieur DevOps", "Tech", 80), ("Chef de produit", "Produit", 85),
        ("Designer UX", "Produit", 70), ("Directeur commercial", "Vente", 82), ("Business developer", "Vente", 60)]]
    bad = [card("Baby-foot", "Divers", kind="decoration", real=False, pts=5),
           card("Machine à café", "Tech", kind="equipment", real=False, pts=10)]
    use(monkeypatch, body(cards + bad, p))
    r = gen(client, room(client, "Recrutez l'équipe d'une startup."))
    assert set(names(r)) == {c["name"] for c in cards}


# -------------------------------------------------------------- 4. apocalypse zombie
def test_zombie_apocalypse_equipment_and_resources_only(client, monkeypatch):
    p = prof(goal="Équiper un groupe de survivants", allowed_entity_types=["equipment", "resource"],
             real_entities_only=False, organization=None,
             required_roles=["Soins", "Nourriture", "Eau", "Protection"])
    cards = [card(n, r, kind=k, real=False, pts=pt) for n, r, k, pt in [
        ("Trousse de soins", "Soins", "equipment", 80), ("Antibiotiques", "Soins", "resource", 85),
        ("Conserves", "Nourriture", "resource", 70), ("Semences", "Nourriture", "resource", 45),
        ("Bidons d'eau", "Eau", "resource", 75), ("Filtre à eau", "Eau", "equipment", 78),
        ("Barricades", "Protection", "equipment", 82), ("Batte cloutée", "Protection", "equipment", 50)]]
    bad = [card("Rick Grimes", "Protection", kind="character", real=False),
           card("Jacuzzi", "Soins", kind="decoration", real=False, pts=2)]
    use(monkeypatch, body(cards + bad, p))
    r = gen(client, room(client, "Survivre à une apocalypse zombie."))
    assert set(names(r)) == {c["name"] for c in cards}
    assert {i["entity_type"] for i in r.json()["items"]} == {"equipment", "resource"}


# --------------------------------------------------------------------- 5. mariage
def test_wedding_covers_several_relevant_families(client, monkeypatch):
    p = prof(goal="Organiser un mariage extravagant",
             allowed_entity_types=["venue", "catering", "entertainment", "decoration"],
             real_entities_only=False, organization=None,
             required_roles=["Lieu", "Repas", "Animation", "Décor"])
    cards = [card(n, r, kind=k, real=False, pts=pt) for n, r, k, pt in [
        ("Château de Chantilly", "Lieu", "venue", 95), ("Salle des fêtes", "Lieu", "venue", 30),
        ("Traiteur étoilé", "Repas", "catering", 90), ("Buffet campagnard", "Repas", "catering", 45),
        ("Orchestre de jazz", "Animation", "entertainment", 85), ("DJ", "Animation", "entertainment", 60),
        ("Arche de fleurs", "Décor", "decoration", 75), ("Guirlandes", "Décor", "decoration", 20)]]
    use(monkeypatch, body(cards, p))
    r = gen(client, room(client, "Organisez un mariage extravagant."))
    items = r.json()["items"]
    assert len({i["entity_type"] for i in items}) >= 3 and len(items) == 8
    assert min(i["points"] for i in items) < 40 < max(i["points"] for i in items)  # faibles mais pertinentes


# ------------------------------------- 6. valide + cartes du catalogue : rien présélectionné
def test_catalog_cards_in_response_never_enter_the_ai_pool(client, monkeypatch):
    catalog_like = [{"catalog_id": "villa_01"}, {"catalog_id": "plage_01", "name": "Jacuzzi"},
                    card("Jacuzzi", "Milieu", kind="furniture", real=False),
                    {"name": "Limousine", "points": 40, "rarity": 1}]  # champs manquants
    use(monkeypatch, body(OM + catalog_like))
    s = room(client)
    r = gen(client, s)
    assert r.status_code == 200
    got = names(r)
    assert len(got) == len(OM) and "Jacuzzi" not in got and "Limousine" not in got
    library = {i["name"] for i in catalog_item_map().values()}
    assert not library & set(got)
    assert all(i["id"].startswith("ai_") and i["source"] == "ai" for i in r.json()["items"])
    assert set(registry.get(s["code"]).ai_items) == {i["id"] for i in r.json()["items"]}
    # l'hôte ne peut pas ajouter un objet du catalogue à une partie IA
    ids = [i["id"] for i in r.json()["items"]]
    put = client.put(f"/rooms/{s['code']}/selection", headers=auth(s), json={"item_ids": ids[:5] + ["villa_01"]})
    assert put.status_code == 400
    assert registry.get(s["code"]).settings["ready"] is False


# ------------------------------------------------------------------ 7. régénération
def test_regeneration_replaces_proposals_and_clears_selection(client, monkeypatch):
    first = [card(f"Joueur A{i}", ROLES[i % 4]) for i in range(8)]
    second = [card(f"Joueur B{i}", ROLES[i % 4]) for i in range(8)]
    use(monkeypatch, body(first), body(second))
    s = room(client)
    r1 = gen(client, s)
    old_ids = [i["id"] for i in r1.json()["items"]]
    ok = client.put(f"/rooms/{s['code']}/selection", headers=auth(s), json={"item_ids": old_ids[:6]})
    assert ok.status_code == 200 and registry.get(s["code"]).settings["ready"] is True
    r2 = gen(client, s)
    assert r2.status_code == 200 and all(n.startswith("Joueur B") for n in names(r2))
    rm = registry.get(s["code"])
    assert rm.settings["ready"] is False and rm.settings["item_ids"] == []   # ancienne sélection effacée
    assert all(rm.ai_items[i]["name"].startswith("Joueur B") for i in rm.ai_items)
    # les anciennes cartes ne sont plus sélectionnables
    stale = [i for i in old_ids if i not in rm.ai_items]
    assert stale and client.put(f"/rooms/{s['code']}/selection", headers=auth(s),
                                json={"item_ids": stale[:6]}).status_code == 400


# ------------------------------------------------ 8. réponse insuffisante : pas de remplissage
def test_insufficient_response_is_an_error_without_random_filling(client, monkeypatch):
    few = [card(f"Joueur {i}", ROLES[i % 4]) for i in range(3)]
    more = [card(f"Renfort {i}", ROLES[i % 4]) for i in range(2)]
    p = use(monkeypatch, body(few), body(more))
    s = room(client, item_count=8)
    r = gen(client, s)
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert "5 carte(s) valide(s)" in detail and "au moins 8" in detail and "Aucune carte n'a été ajoutée" in detail
    assert len(p.calls) == 2  # une seule tentative de correction, pas plus
    rm = registry.get(s["code"])
    assert rm.ai_items == {} and rm.settings["ready"] is False  # rien n'est enregistré, rien du catalogue
    assert KEY not in r.text


def test_correction_asks_only_for_missing_cards_and_succeeds(client, monkeypatch):
    first = [card(f"Joueur {i}", ROLES[i % 4]) for i in range(4)] + [card("Gandalf", "Gardien", real=False)]
    fix = [card(f"Renfort {i}", ROLES[i % 4]) for i in range(4)] + [card("Joueur 0", "Gardien")]  # doublon
    p = use(monkeypatch, body(first), body(fix))
    s = room(client, item_count=6, max_players=2)
    r = gen(client, s)
    assert r.status_code == 200, r.text
    assert r.json()["corrected"] is True and len(p.calls) == 2
    got = names(r)
    assert len(got) == len(set(got)) == 8 and "Gandalf" not in got and got.count("Joueur 0") == 1
    cp = p.calls[1]["prompt"]
    assert "Il manque 2 carte(s)" in cp and "Joueur 0" in cp and "Gandalf" not in cp.split("Profil à respecter")[0]
    assert "football_player" in cp and "<scenario>" in cp          # même profil, texte de l'hôte comme donnée
    assert p.calls[1]["api_key"] == KEY and KEY not in cp


def test_missing_role_triggers_one_correction_then_fails_clearly(client, monkeypatch):
    no_keeper = [card(f"Joueur {i}", ROLES[1 + i % 3]) for i in range(8)]
    p = use(monkeypatch, body(no_keeper))   # la correction répète le même défaut
    r = gen(client, room(client))
    assert r.status_code == 502 and "Rôles sans carte : Gardien" in r.json()["detail"]
    assert len(p.calls) == 2


def test_missing_role_fixed_by_the_correction(client, monkeypatch):
    no_keeper = [card(f"Joueur {i}", ROLES[1 + i % 3]) for i in range(8)]
    keepers = [card("Gardien A", "Gardien"), card("Gardien B", "Gardien")]
    p = use(monkeypatch, body(no_keeper), body(keepers))
    r = gen(client, room(client))
    assert r.status_code == 200 and "Gardien A" in names(r)
    assert "Rôles sans carte : Gardien" in p.calls[1]["prompt"]


def test_no_correction_when_the_first_answer_is_enough(client, monkeypatch):
    p = use(monkeypatch, body(OM))
    r = gen(client, room(client))
    assert r.status_code == 200 and r.json()["corrected"] is False and len(p.calls) == 1


def test_invalid_profile_is_rejected_not_guessed(client, monkeypatch):
    for bad in (None, "texte", {}, prof(allowed_entity_types=[]), prof(goal=""),
                prof(real_entities_only="oui"), prof(allowed_entity_types=["a"] * 7)):
        raw = json.dumps({"title": "T", "description": "Une description valide.",
                          "profile": bad, "items": OM})
        p = use(monkeypatch, raw)
        r = gen(client, room(client))
        assert r.status_code == 502 and "objectif valide" in r.json()["detail"]
        assert len(p.calls) == 1
        registry.rooms.clear()


# --------------------------------------------- 9. changement de situation : rien ne reste
def test_new_situation_keeps_nothing_from_the_previous_one(client, monkeypatch):
    use(monkeypatch, body(OM))
    s1 = room(client)
    ids1 = [i["id"] for i in gen(client, s1).json()["items"]]
    marvel = [card(f"Héros {i}", "Combattant", kind="marvel_character", real=False) for i in range(8)]
    p2 = prof(allowed_entity_types=["marvel_character"], real_entities_only=False, required_roles=["Combattant"])
    use(monkeypatch, body(marvel, p2))
    s2 = room(client, "Une équipe Marvel.")
    r2 = gen(client, s2)
    assert all(n.startswith("Héros") for n in names(r2))
    rm2 = registry.get(s2["code"])
    assert not set(ids1) & set(rm2.ai_items) and rm2.ai_profile["allowed_entity_types"] == ["marvel_character"]
    # une partie lancée depuis la seconde situation ne contient aucune carte de la première
    ids2 = list(rm2.ai_items)
    client.put(f"/rooms/{s2['code']}/selection", headers=auth(s2), json={"item_ids": ids2[:6]})
    g = Game([("a", "A"), ("b", "B")], rm2.settings, pool=list(rm2.ai_items.values()))
    assert all(i["name"].startswith("Héros") for i in g.items)


# ------------------------------------------------------------ profil : validation et règles
def test_profile_validation_and_normalisation():
    p = profile_mod.clean_profile({"goal": "  Composer   une équipe ", "allowed_entity_types": ["Football Player", "football_player"],
                                   "real_entities_only": True, "organization": " OM ",
                                   "required_roles": ["Gardien", "gardien", "Défenseur"], "extra": "ignoré"})
    assert p == {"goal": "Composer une équipe", "allowed_entity_types": ["football_player"],
                 "real_entities_only": True, "organization": "OM",
                 "required_roles": ["Gardien", "Défenseur"], "allow_unrelated_items": False}
    assert profile_mod.clean_profile({"goal": "x" * 141, "allowed_entity_types": ["a"], "real_entities_only": False}) is None
    assert profile_mod.clean_profile({"goal": "Un but", "allowed_entity_types": ["a"], "real_entities_only": False,
                                      "required_roles": ["r"] * 13}) is None
    assert profile_mod.clean_profile({"goal": "Un but", "allowed_entity_types": ["a"], "real_entities_only": False,
                                      "organization": None})["organization"] is None


def test_profile_is_generic_not_football_specific():
    p = profile_mod.clean_profile({"goal": "Monter un casting", "allowed_entity_types": ["actor"],
                                   "real_entities_only": True, "required_roles": ["Héros", "Méchant"],
                                   "allow_unrelated_items": False})
    ok = {"entity_type": "actor", "is_real": True, "category": "Méchant principal"}
    assert profile_mod.rejection(p, ok) is None
    assert profile_mod.rejection(p, {**ok, "entity_type": "football_player"}) == "type de carte non admis"
    assert profile_mod.rejection(p, {**ok, "is_real": False}) == "carte non réelle"
    assert profile_mod.rejection(p, {**ok, "is_real": None}) == "carte non réelle"
    assert profile_mod.rejection(p, {**ok, "category": "Costumier"}) == "rôle non prévu"
    assert profile_mod.missing_roles(p, [ok]) == ["Héros"]
    assert profile_mod.role_matches("Défenseur", "Défenseur central") and not profile_mod.role_matches("Milieu", "Gardien")


def test_allow_unrelated_items_lets_anything_through():
    p = prof(allow_unrelated_items=True, required_roles=[], real_entities_only=False)
    text = body([card("Limousine", "Matériel", kind="decoration", real=False)] +
                [card(f"Joueur {i}", "Milieu", real=False) for i in range(6)], p)
    res = generator.parse_response(text, 6, set(), FALLBACK)
    assert "Limousine" in [i["name"] for i in res.items]


def test_card_without_entity_type_is_dropped_when_the_profile_restricts():
    p = prof(real_entities_only=False, required_roles=[])
    items = [card(f"Joueur {i}", "Milieu", real=False) for i in range(6)] + \
            [{k: v for k, v in card("Sans type", "Milieu", real=False).items() if k != "entity_type"}]
    res = generator.parse_response(body(items, p), 6, set(), FALLBACK)
    assert "Sans type" not in [i["name"] for i in res.items]


# ------------------------------------------------------------- nombre de cartes (≤ 20)
def test_pool_size_scales_with_cards_and_players():
    assert generator.pool_size(8, 2) == 12 and generator.pool_size(8, 4) == 16
    assert generator.pool_size(20, 4) == 28
    assert generator.pool_size(20, 4) <= generator.MAX_POOL == 40
    assert generator.pool_size(6, 1) == 10  # au moins 2 joueurs comptés
    prompt = generator.build_prompt({"description": "Un onze."}, "normal", 20, players=4)
    assert "Nombre de cartes à proposer : 28" in prompt and "Cartes mises aux enchères : 20" in prompt
    assert "Nombre de joueurs : 4" in prompt


def test_host_can_play_with_20_cards(client, monkeypatch):
    pool = [card(f"Joueur {i}", ROLES[i % 4]) for i in range(28)]
    p = use(monkeypatch, body(pool))
    s = room(client, item_count=20, max_players=4)
    r = gen(client, s)
    assert r.status_code == 200 and len(r.json()["items"]) == 28
    assert "Nombre de cartes à proposer : 28" in p.calls[0]["prompt"]
    ids = [i["id"] for i in r.json()["items"]]
    assert client.put(f"/rooms/{s['code']}/selection", headers=auth(s), json={"item_ids": ids[:19]}).status_code == 400
    assert client.put(f"/rooms/{s['code']}/selection", headers=auth(s), json={"item_ids": ids[:20]}).status_code == 200
    rm = registry.get(s["code"])
    g = Game([("a", "A"), ("b", "B")], rm.settings, pool=list(rm.ai_items.values()))
    assert len(g.items) == 20 and g.snapshot("a")["item_total"] == 20
    too_many = client.post("/rooms", json={"pseudo": "A", "settings": {
        "creation_type": "ai", "item_count": 21, "scenario": {"description": "Un onze."}}})
    assert too_many.status_code == 400


# --------------------------------------------------------------- logs de développement
def test_debug_logs_show_card_names_and_never_the_key(client, monkeypatch, caplog):
    monkeypatch.setenv("BIDBANG_AI_DEBUG", "1")
    caplog.set_level(logging.DEBUG)
    use(monkeypatch, body(OM + [card("Limousine", "Matériel", kind="decoration", real=False)]))
    s = room(client)
    r = gen(client, s)
    ids = [i["id"] for i in r.json()["items"]][:6]
    client.put(f"/rooms/{s['code']}/selection", headers=auth(s), json={"item_ids": ids})
    log = caplog.text
    assert "Steve Mandanda" in log and "Limousine" in log and "type de carte non admis" in log
    assert "propositions enregistrées" in log and "sélection validée" in log
    assert KEY not in log


def test_debug_logs_are_silent_by_default(client, monkeypatch, caplog):
    monkeypatch.delenv("BIDBANG_AI_DEBUG", raising=False)
    caplog.set_level(logging.DEBUG)
    use(monkeypatch, body(OM))
    gen(client, room(client))
    assert "[ia]" not in caplog.text and not debug.enabled()


def test_mock_provider_follows_the_profile(client, monkeypatch):
    monkeypatch.setenv("BIDBANG_MOCK_AI", "1")
    s = room(client, "Un 11 de légende au football.", item_count=11)
    r = client.post(f"/rooms/{s['code']}/ai/generate", json={"provider": "mock", "api_key": "0123456789"},
                    headers=auth(s))
    assert r.status_code == 200, r.text
    assert {i["entity_type"] for i in r.json()["items"]} == {"football_player"}
    assert r.json()["profile"]["required_roles"] == ROLES
