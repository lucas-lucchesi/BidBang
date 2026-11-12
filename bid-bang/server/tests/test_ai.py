"""Partie générée par IA : validation des réponses, sécurité de la clé, limites. Fournisseur simulé :
aucune vraie clé, aucun appel réseau, aucune dépense.

Une partie IA n'a pas de critères : l'IA attribue directement les points (1 à 100) de chaque carte
(objet, joueur, métier, personnalité...), que le serveur valide puis fige au lancement."""
import json
import logging

import anthropic
import httpx2
import pytest
from starlette.testclient import TestClient

from app.ai import base as ai_base
from app.ai import generator, limits
from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import ProviderError
from app.errors import GameError
from app.items import compute_price, normalize_ai_item
from app.main import app
from app.rooms import registry

KEY = "sk-ant-TESTSECRET-0123456789abcdef"
SCENARIO = "Composez un onze de légende au football."


PROFILE = {"goal": "Composer un onze de légende", "allowed_entity_types": ["football_player"],
           "real_entities_only": False, "organization": None, "required_roles": [],
           "allow_unrelated_items": False}


def good_item(n=0, **over):
    d = {"name": f"Légende {n}", "description": "Un joueur de légende.", "category": "Milieu",
         "entity_type": "football_player", "is_real": False, "rarity": n % 4, "price": 150, "points": 5 + n * 6}
    d.update(over)
    return d


def response(items=None, **extra):
    data = {"title": "Onze de légende", "description": "Les meilleurs joueurs de l'histoire.",
            "profile": PROFILE, "items": items if items is not None else [good_item(i) for i in range(14)]}
    data.update(extra)
    return json.dumps(data)


class FakeProvider:
    name = "anthropic"
    label = "Fake"

    def __init__(self, text=None, error=None):
        self.text, self.error = text, error
        self.calls: list[dict] = []

    async def complete(self, *, api_key, system, prompt, max_tokens, timeout):
        self.calls.append({"api_key": api_key, "system": system, "prompt": prompt,
                           "max_tokens": max_tokens, "timeout": timeout})
        if self.error:
            raise self.error
        return self.text if self.text is not None else response()


@pytest.fixture(autouse=True)
def _limits(monkeypatch):
    limits.reset()
    monkeypatch.setattr(limits, "MIN_INTERVAL_SECONDS", 0.0)
    yield
    limits.reset()


@pytest.fixture
def provider(monkeypatch):
    p = FakeProvider()
    monkeypatch.setattr(ai_base, "get_provider", lambda name: p)
    return p


@pytest.fixture
def client():
    registry.rooms.clear()
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def ai_settings(**over):
    s = {"creation_type": "ai", "mode": "normal", "item_count": 6,
         "scenario": {"description": SCENARIO}}
    s.update(over)
    return s


def new_room(client, **over):
    r = client.post("/rooms", json={"pseudo": "Alice", "settings": ai_settings(**over)})
    assert r.status_code == 200, r.text
    return r.json()


def auth(s):
    return {"Authorization": f"Bearer {s['token']}"}


def generate(client, s, key=KEY, headers=None):
    return client.post(f"/rooms/{s['code']}/ai/generate", json={"provider": "anthropic", "api_key": key},
                       headers=headers if headers is not None else auth(s))


# ------------------------------------------------------ validation des cartes
def test_valid_card_converted_with_server_generated_id():
    taken: set[str] = set()
    it = normalize_ai_item(good_item(1, id="catalogue_01", icon="http://evil", winner="p1"), taken)
    assert it["id"] == "ai_legende_1" and it["source"] == "ai" and "ai_legende_1" in taken
    assert it["icon"] == "box" and it["image"] is None
    assert it["points"] == 11 and it["category"] == "Milieu" and it["price"] == 150
    assert "winner" not in it and it["attributes"] == {}  # pas de critères en partie IA


def test_points_are_given_by_the_ai_within_bounds():
    for ok in (1, 50, 100):
        assert normalize_ai_item(good_item(1, points=ok), set())["points"] == ok


@pytest.mark.parametrize("bad", [0, -5, 101, 1000, "50", 50.5, True, None])
def test_invalid_points_reject_the_card(bad):
    assert normalize_ai_item(good_item(1, points=bad), set()) is None


def test_proposed_price_kept_only_within_bounds():
    assert normalize_ai_item(good_item(1, price=254), set())["price"] == 250
    for bad in (19, 601, -5, "100", 99.5, True, None):
        it = normalize_ai_item(good_item(1, price=bad), set())
        assert it["price"] == compute_price(it["points"], it["rarity"])


def test_category_is_free_text_with_default():
    assert normalize_ai_item(good_item(1, category="Gardien de but"), set())["category"] == "Gardien de but"
    assert normalize_ai_item(good_item(1, category=""), set())["category"] == "Divers"
    assert normalize_ai_item(good_item(1, category="x" * 31), set()) is None


@pytest.mark.parametrize("over", [
    {"rarity": 4}, {"rarity": -1}, {"rarity": "rare"}, {"rarity": 1.5}, {"rarity": True},
    {"name": ""}, {"name": "x" * 41}, {"description": "d" * 141},
])
def test_invalid_cards_rejected(over):
    assert normalize_ai_item(good_item(1, **over), set()) is None


def test_missing_fields_rejected():
    for field in ("name", "rarity", "points"):
        d = good_item(1)
        del d[field]
        assert normalize_ai_item(d, set()) is None
    assert normalize_ai_item("pas une carte", set()) is None
    assert normalize_ai_item(None, set()) is None


def test_duplicate_ids_get_suffix_and_never_collide():
    taken = {"ai_objet"}
    a = normalize_ai_item(good_item(1, name="Objet"), taken)
    b = normalize_ai_item(good_item(2, name="Objet"), taken)
    assert a["id"] != b["id"] and a["id"] != "ai_objet"


def test_control_chars_removed_from_text():
    assert normalize_ai_item(good_item(1, name="Gén\x00é\x1brateur"), set())["name"] == "Générateur"


# ------------------------------------------------------------ parse_response
FALLBACK = {"title": "Titre hôte", "description": "Description de l'hôte pour la partie."}


def parse(text, min_items=6, taken=None):
    return generator.parse_response(text, min_items, taken if taken is not None else set(), FALLBACK)


def test_parse_valid_response_with_code_fence():
    res = parse("```json\n" + response() + "\n```")
    assert len(res.items) == 14 and res.new_items == res.items
    assert res.situation == {"title": "Onze de légende",
                             "description": "Les meilleurs joueurs de l'histoire.", "criteria": []}
    assert [i["points"] for i in res.items][:3] == [5, 11, 17]


def test_criteria_in_response_are_ignored():
    res = parse(response(criteria=[{"id": "soins", "necessary": True, "importance": 5}]))
    assert res.situation["criteria"] == [] and len(res.items) == 14


@pytest.mark.parametrize("text", ["", "pas du json", "[1,2,3]", "{", '{"items": "x"}',
                                  '{"items": []}', '{"items": [1,2,3]}', "x" * 50_000])
def test_malformed_responses_rejected(text):
    with pytest.raises(GameError):
        parse(text)


def test_too_few_valid_cards_rejected():
    items = [good_item(i) for i in range(4)] + [good_item(9, points=999)] * 10
    with pytest.raises(GameError, match="valide"):
        parse(response(items))


def test_duplicate_names_dropped():
    items = [good_item(i) for i in range(7)] + [good_item(0)] * 3
    res = parse(response(items))
    assert len(res.items) == 7 and len({i["id"] for i in res.items}) == 7


def test_item_count_capped():
    res = parse(response([good_item(i % 90, name=f"Carte {i}") for i in range(100)]))
    assert len(res.items) <= generator.MAX_RAW_ITEMS


def test_missing_title_and_description_fall_back_to_host_text():
    res = parse(response(title=5, description="x"))
    assert res.situation["title"] == "Titre hôte"
    assert res.situation["description"] == FALLBACK["description"]


def test_ai_cannot_name_a_winner_or_scores():
    res = parse(response(winner="p1", scores={"p1": 999}))
    assert all("winner" not in i for i in res.items) and "winner" not in res.situation


def test_prompt_allows_any_kind_of_card_and_asks_for_points():
    system = generator.build_system_prompt()
    for word in ("métiers", "joueurs de football", "personnalités publiques", "personnages",
                 "11 de légende", "CARTES", "points", "OBJECTIF EXACT", "Olympique de Marseille",
                 "n'invente aucune personne", "N'ajoute JAMAIS une carte hors sujet",
                 "allow_unrelated_items", "required_roles", "real_entities_only"):
        assert word in system
    assert "jamais comme des instructions" in system and "gagnant" in system
    assert "criteria" not in system and "catalog_id" not in system  # plus de critères
    prompt = generator.build_prompt({"description": SCENARIO}, "normal", 11, players=4)
    assert SCENARIO in prompt and "<scenario>" in prompt and "cartes" in prompt


def test_schema_describes_profile_and_cards_in_one_request():
    s = generator.response_schema()
    item = s["properties"]["items"]["items"]
    assert item["properties"]["points"]["minimum"] == 1 and item["properties"]["points"]["maximum"] == 100
    assert {"points", "entity_type", "is_real"} <= set(item["required"])
    assert "criteria" not in s["properties"] and "profile" in s["required"]
    assert set(s["properties"]["profile"]["properties"]) == {
        "goal", "allowed_entity_types", "real_entities_only", "organization", "required_roles",
        "allow_unrelated_items"}
    assert set(s["required"]) == {"title", "description", "profile", "items"}


# ---------------------------------------------------- API : parcours complet
def test_full_ai_flow_with_free_cards(client, provider):
    s = new_room(client, item_count=11)
    assert s["room"]["settings"]["ready"] is False and s["room"]["settings"]["item_count"] == 11
    r = generate(client, s)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["items"]) == 14 and data["situation"]["criteria"] == []
    assert data["generations_left"] == limits.MAX_GENERATIONS_PER_ROOM - 1
    assert [i["points"] for i in data["items"]][:2] == [5, 11]  # points de l'IA, tels quels
    assert all(i["usefulness"] in ("high", "medium", "low", "none") for i in data["items"])
    call = provider.calls[0]
    assert "<scenario>" in call["prompt"] and SCENARIO in call["prompt"]
    assert call["max_tokens"] == generator.MAX_TOKENS and call["timeout"] == generator.TIMEOUT_SECONDS
    b = client.post(f"/rooms/{s['code']}/join", json={"pseudo": "Bob"}).json()
    ids = [i["id"] for i in data["items"]][:11]
    with client.websocket_connect(f"/ws/{s['code']}?token={s['token']}") as wa, \
         client.websocket_connect(f"/ws/{s['code']}?token={b['token']}"):
        wa.send_json({"type": "start_game"})
        assert "valider" in _wait(wa, "error")["message"]
        sel = client.put(f"/rooms/{s['code']}/selection", headers=auth(s), json={"item_ids": ids})
        assert sel.status_code == 200 and sel.json()["room"]["settings"]["ready"] is True
        wa.send_json({"type": "start_game"})
        game = _wait(wa, "game_state")["game"]
        assert game["creation_type"] == "ai" and game["phase"] == "auction" and game["item_total"] == 11
        item = game["auction"]["item"]
        assert item["id"] in ids
        expected = next(i["points"] for i in data["items"] if i["id"] == item["id"])
        assert item["points"] == expected  # points de l'IA, figés au lancement
        assert game["situation"]["title"] == "Onze de légende" and game["situation"]["criteria"] == []
        assert generate(client, s).status_code == 409  # plus de génération après le lancement


def _wait(ws, kind):
    while True:
        m = ws.receive_json()
        if m["type"] == kind:
            return m


def test_ai_game_has_no_criteria_and_rejects_them(client, provider):
    s = new_room(client)
    ids = [i["id"] for i in generate(client, s).json()["items"]][:6]
    base = f"/rooms/{s['code']}/selection"
    r = client.put(base, headers=auth(s), json={"item_ids": ids, "criteria": [
        {"id": "soins", "necessary": True, "importance": 5}]})
    assert r.status_code == 400 and "critères" in r.json()["detail"]
    assert client.put(base, headers=auth(s), json={"item_ids": ids}).status_code == 200


def test_catalog_items_are_not_selectable_in_ai_games(client, provider):
    s = new_room(client)
    ids = [i["id"] for i in generate(client, s).json()["items"]]
    base = f"/rooms/{s['code']}/selection"
    assert client.put(base, headers=auth(s), json={"item_ids": ids[:5] + ["plage_01"]}).status_code == 400


def test_points_are_frozen_copies_in_game(client, provider):
    from app.game import Game
    s = new_room(client)
    ids = [i["id"] for i in generate(client, s).json()["items"]][:6]
    client.put(f"/rooms/{s['code']}/selection", headers=auth(s), json={"item_ids": ids})
    room = registry.get(s["code"])
    g = Game([("a", "A"), ("b", "B")], room.settings, pool=list(room.ai_items.values()))
    before = {i["id"]: i["points"] for i in g.items}
    room.ai_items[ids[0]]["points"] = 100  # même si la source change ensuite
    assert {i["id"]: i["points"] for i in g.items} == before


def test_selection_rules(client, provider):
    s = new_room(client)
    generate(client, s)
    base = f"/rooms/{s['code']}/selection"
    assert client.put(base, headers=auth(s), json={"item_ids": ["ai_inconnu"] * 2}).status_code == 400
    ids = [i["id"] for i in generate(client, s).json()["items"]]
    assert client.put(base, headers=auth(s), json={"item_ids": ids[:3]}).status_code == 400  # insuffisant
    assert client.put(base, headers=auth(s), json={"item_ids": ids[:6] + ids[:1]}).status_code == 400  # doublon
    assert client.put(base, headers=auth(s), json={"item_ids": ids[:6]}).status_code == 200
    assert generate(client, s).status_code == 200  # une régénération invalide la sélection
    assert registry.get(s["code"]).settings["ready"] is False


def test_card_count_is_chosen_by_the_host_up_to_20():
    from app.game import validate_settings
    for n in (6, 11, 12, 20):
        assert validate_settings({"creation_type": "ai", "item_count": n, "scenario": {"description": SCENARIO}},
                                 require_selection=False)["item_count"] == n
    for bad in (5, 21, 100, 0, -3, "8", 8.5, True, None):
        with pytest.raises(GameError):
            validate_settings({"item_count": bad})
    with pytest.raises(GameError, match="au plus 12"):  # un lieu classique n'a que 12 objets
        validate_settings({"theme_id": "cabane", "item_count": 20})


def test_mock_provider_generates_football_cards_without_key(client, monkeypatch):
    monkeypatch.setenv("BIDBANG_MOCK_AI", "1")
    assert "mock" in [p["id"] for p in client.get("/ai/providers").json()["providers"]]
    s = new_room(client, item_count=11, scenario={"description": "Un 11 de légende au football."})
    r = client.post(f"/rooms/{s['code']}/ai/generate",
                    json={"provider": "mock", "api_key": "0123456789"}, headers=auth(s))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["situation"]["title"] == "Onze de légende" and len(data["items"]) >= 12
    assert {i["category"] for i in data["items"]} >= {"Gardien", "Défenseur", "Milieu", "Attaquant"}
    assert all(1 <= i["points"] <= 100 for i in data["items"])
    monkeypatch.delenv("BIDBANG_MOCK_AI")
    assert "mock" not in [p["id"] for p in client.get("/ai/providers").json()["providers"]]


# ------------------------------------------------------ autorisation
def test_only_host_can_generate(client, provider):
    s = new_room(client)
    b = client.post(f"/rooms/{s['code']}/join", json={"pseudo": "Bob"}).json()
    r = generate(client, s, headers=auth(b))
    assert r.status_code == 403 and not provider.calls
    assert client.put(f"/rooms/{s['code']}/selection", headers=auth(b),
                      json={"item_ids": []}).status_code == 403


def test_invalid_token_and_unknown_room(client, provider):
    s = new_room(client)
    assert generate(client, s, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert generate(client, s, headers={}).status_code == 401
    r = client.post("/rooms/ZZZZZZ/ai/generate", json={"api_key": KEY}, headers=auth(s))
    assert r.status_code == 400 and "introuvable" in r.json()["detail"]
    assert not provider.calls


def test_non_ai_room_refuses_generation(client, provider):
    s = client.post("/rooms", json={"pseudo": "A", "settings": {}}).json()
    r = generate(client, s)
    assert r.status_code == 400 and not provider.calls


def test_failed_auth_attempts_are_rate_limited(client, provider):
    s = new_room(client)
    for _ in range(limits.MAX_FAILURES_PER_MINUTE):
        generate(client, s, headers={"Authorization": "Bearer x"})
    assert generate(client, s).status_code == 429  # même avec le bon jeton
    assert not provider.calls


def test_key_requires_https_or_loopback(provider, monkeypatch):
    registry.rooms.clear()
    monkeypatch.delenv("BIDBANG_ALLOW_INSECURE_AI", raising=False)
    with TestClient(app, base_url="http://example.com") as c:
        s = new_room(c)
        r = generate(c, s)
        assert r.status_code == 400 and "HTTPS" in r.json()["detail"] and not provider.calls
    with TestClient(app, base_url="http://127.0.0.1") as c:
        s = new_room(c)
        assert generate(c, s).status_code == 200


# -------------------------------------------------------------- limites
def test_generation_limit_per_room(client, provider):
    s = new_room(client)
    for _ in range(limits.MAX_GENERATIONS_PER_ROOM):
        assert generate(client, s).status_code == 200
    r = generate(client, s)
    assert r.status_code == 429 and len(provider.calls) == limits.MAX_GENERATIONS_PER_ROOM


def test_failed_generations_count_toward_limit(client, monkeypatch):
    monkeypatch.setattr(ai_base, "get_provider",
                        lambda n: FakeProvider(error=ProviderError("Erreur.", 502)))
    s = new_room(client)
    for _ in range(limits.MAX_GENERATIONS_PER_ROOM):
        assert generate(client, s).status_code == 502
    assert generate(client, s).status_code == 429


def test_min_interval_between_generations(client, provider, monkeypatch):
    monkeypatch.setattr(limits, "MIN_INTERVAL_SECONDS", 60.0)
    s = new_room(client)
    assert generate(client, s).status_code == 200
    assert generate(client, s).status_code == 429


def test_one_generation_at_a_time_and_global_cap(client, provider):
    s = new_room(client)
    room = registry.get(s["code"])
    room.ai_busy = True
    assert generate(client, s).status_code == 429
    room.ai_busy = False
    sem = limits.global_slot()
    for _ in range(limits.MAX_CONCURRENT_GENERATIONS):
        sem._value = 0  # noqa: SLF001 - simule des générations en cours
    assert generate(client, s).status_code == 429


def test_ai_prompt_size_limit_at_creation(client):
    ok = client.post("/rooms", json={"pseudo": "A", "settings": ai_settings(scenario="x" * 600)})
    assert ok.status_code == 200
    r = client.post("/rooms", json={"pseudo": "A", "settings": ai_settings(scenario="x" * 601)})
    assert r.status_code == 400


def test_max_players_setting(client):
    s = new_room(client, max_players=2)
    assert s["room"]["max_players"] == 2
    assert client.post(f"/rooms/{s['code']}/join", json={"pseudo": "Bob"}).status_code == 200
    r = client.post(f"/rooms/{s['code']}/join", json={"pseudo": "Zed"})
    assert r.status_code == 400 and "complet" in r.json()["detail"]
    for bad in (1, 5, "3", True):
        r = client.post("/rooms", json={"pseudo": "A", "settings": ai_settings(max_players=bad)})
        assert r.status_code == 400
    assert client.post("/rooms", json={"pseudo": "A", "settings": {}}).json()["room"]["max_players"] == 4


# -------------------------------------------------- erreurs du fournisseur
@pytest.mark.parametrize("error", [ProviderError("Le fournisseur n'a pas répondu à temps.", 504),
                                   ProviderError("Limite atteinte.", 502)])
def test_provider_errors_returned_cleanly(client, monkeypatch, error):
    monkeypatch.setattr(ai_base, "get_provider", lambda n: FakeProvider(error=error))
    s = new_room(client)
    r = generate(client, s)
    assert r.status_code == error.status and r.json() == {"detail": error.message}
    assert not registry.get(s["code"]).ai_busy  # l'état est libéré


def test_malformed_ai_response_rejected_by_api(client, monkeypatch):
    monkeypatch.setattr(ai_base, "get_provider", lambda n: FakeProvider(text="désolé, pas de JSON"))
    s = new_room(client)
    r = generate(client, s)
    assert r.status_code == 502 and "exploitable" in r.json()["detail"]
    assert registry.get(s["code"]).ai_items == {}


def test_missing_api_key_rejected(client, provider):
    s = new_room(client)
    for body in ({}, {"api_key": ""}, {"api_key": "court"}, {"provider": "anthropic"}):
        r = client.post(f"/rooms/{s['code']}/ai/generate", json=body, headers=auth(s))
        assert r.status_code == 422 and r.json() == {"detail": "Requête invalide."}
    assert not provider.calls


def test_unknown_provider(client):
    s = new_room(client)
    r = client.post(f"/rooms/{s['code']}/ai/generate",
                    json={"provider": "inconnu", "api_key": KEY}, headers=auth(s))
    assert r.status_code == 400 and KEY not in r.text


# ---- AnthropicProvider : toutes les erreurs deviennent des messages génériques
def _req():
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(cls, status):
    resp = httpx2.Response(status, request=_req(), json={"error": {"message": f"secret {KEY}"}})
    return cls(f"secret {KEY}", response=resp, body=None)


class _Messages:
    def __init__(self, behaviour):
        self.behaviour = behaviour

    async def create(self, **kwargs):
        if isinstance(self.behaviour, BaseException):
            raise self.behaviour
        return self.behaviour


class _FakeClient:
    behaviour: object = None
    seen: dict = {}

    def __init__(self, **kwargs):
        _FakeClient.seen = kwargs
        self.messages = _Messages(_FakeClient.behaviour)

    async def close(self):
        pass


@pytest.mark.parametrize("error,status", [
    (_status_error(anthropic.AuthenticationError, 401), 502),
    (_status_error(anthropic.PermissionDeniedError, 403), 502),
    (_status_error(anthropic.RateLimitError, 429), 502),
    (_status_error(anthropic.InternalServerError, 500), 502),
    (_status_error(anthropic.BadRequestError, 400), 502),
    (anthropic.APITimeoutError(request=_req()), 504),
    (TimeoutError(f"secret {KEY}"), 504),
    (anthropic.APIConnectionError(message=f"secret {KEY}", request=_req()), 502),
    (RuntimeError(f"secret {KEY}"), 502),
])
async def test_anthropic_provider_errors_leak_nothing(monkeypatch, error, status):
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _FakeClient)
    _FakeClient.behaviour = error
    with pytest.raises(ProviderError) as exc:
        await AnthropicProvider().complete(api_key=KEY, system="s", prompt="p", max_tokens=10, timeout=5)
    assert exc.value.status == status
    assert KEY not in exc.value.message and KEY not in repr(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__


async def test_anthropic_provider_success_and_settings(monkeypatch):
    class Block:
        type, text = "text", "{}"

    class Resp:
        stop_reason, content = "end_turn", [Block()]

    monkeypatch.setattr(anthropic, "AsyncAnthropic", _FakeClient)
    _FakeClient.behaviour = Resp()
    out = await AnthropicProvider().complete(api_key=KEY, system="s", prompt="p", max_tokens=10, timeout=7)
    assert out == "{}"
    assert _FakeClient.seen["max_retries"] == 0 and _FakeClient.seen["timeout"] == 7
    Resp.stop_reason = "refusal"
    with pytest.raises(ProviderError):
        await AnthropicProvider().complete(api_key=KEY, system="s", prompt="p", max_tokens=10, timeout=7)


# --------------------------------------------- la clé ne fuit jamais
def _dump(obj) -> str:
    return json.dumps(obj, default=lambda o: repr(vars(o)) if hasattr(o, "__dict__") else repr(o))


def test_key_never_leaks(client, provider, caplog):
    caplog.set_level(logging.DEBUG)
    s = new_room(client)
    b = client.post(f"/rooms/{s['code']}/join", json={"pseudo": "Bob"}).json()
    with client.websocket_connect(f"/ws/{s['code']}?token={s['token']}") as wa, \
         client.websocket_connect(f"/ws/{s['code']}?token={b['token']}") as wb:
        frames: list[str] = []
        r = generate(client, s)
        assert r.status_code == 200
        assert KEY not in r.text and KEY not in _dump(dict(r.headers))
        sel = client.put(f"/rooms/{s['code']}/selection", headers=auth(s),
                         json={"item_ids": [i["id"] for i in r.json()["items"]][:6]})
        assert KEY not in sel.text
        wa.send_json({"type": "ping"})
        b_id = b["player_id"]
        client.post(f"/rooms/{s['code']}/join", json={"pseudo": "Zed"})
        wa.send_json({"type": "start_game"})
        for ws in (wa, wb):
            for _ in range(3):
                frames.append(json.dumps(ws.receive_json()))
        assert b_id and all(KEY not in f for f in frames)
    room = registry.get(s["code"])
    assert KEY not in _dump(room.__dict__) and KEY not in _dump(room.room_state())
    assert KEY not in _dump(room.game.snapshot(s["player_id"]))
    assert KEY not in caplog.text


def test_key_not_in_validation_errors_or_provider_errors(client, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    s = new_room(client)
    r = client.post(f"/rooms/{s['code']}/ai/generate",
                    json={"provider": "x" * 99, "api_key": KEY}, headers=auth(s))  # 422
    assert r.status_code == 422 and KEY not in r.text
    monkeypatch.setattr(ai_base, "get_provider",
                        lambda n: FakeProvider(error=ProviderError("Erreur générique.", 502)))
    r = generate(client, s)
    assert KEY not in r.text and KEY not in caplog.text


def test_api_key_secretstr_not_in_repr():
    from app.models import GenerateRequest
    m = GenerateRequest(api_key=KEY)
    assert KEY not in repr(m) and KEY not in str(m) and KEY not in m.model_dump_json()
