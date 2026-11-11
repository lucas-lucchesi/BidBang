"""Partie générée par IA : validation des réponses, sécurité de la clé, limites. Fournisseur simulé :
aucune vraie clé, aucun appel réseau, aucune dépense."""
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
from app.trials import normalize_ai_trials

KEY = "sk-ant-TESTSECRET-0123456789abcdef"
SCENARIO = "Vous êtes des milliardaires qui doivent construire une base sur Mars."


def good_item(n=0, **over):
    d = {"name": f"Objet martien {n}", "description": "Un objet utile.", "category": "Énergie",
         "rarity": n % 2, "stats": {"confort": 2, "style": 1, "utilite": 3, "securite": 2, "sante": 1},
         "tags": ["energie", "mars"]}
    d.update(over)
    return d


def good_trials():
    return [{"name": "Tempête de poussière", "description": "Survivre.", "stat": "securite", "threshold": 8},
            {"name": "Manque d'oxygène", "description": "Respirer.", "stat": "sante", "threshold": 9},
            {"name": "Panne", "description": "Réparer.", "stat": "utilite", "threshold": 7}]


def response(items=None, trials=None):
    return json.dumps({"items": items if items is not None else [good_item(i) for i in range(12)],
                       "trials": trials if trials is not None else good_trials()})


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
    s = {"creation_type": "ai", "mode": "construction", "item_count": 6,
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


# ------------------------------------------------------ validation des objets
def test_valid_item_converted_and_price_computed_by_server():
    taken: set[str] = set()
    it = normalize_ai_item(good_item(1, price=1, id="catalogue_01", icon="http://evil"), taken)
    assert it["id"] == "ai_objet_martien_1" and it["source"] == "ai"
    assert it["price"] == compute_price(it["stats"], it["rarity"]) != 1  # prix hors bornes : calcul serveur
    assert it["icon"] == "box" and "ai_objet_martien_1" in taken


def test_proposed_price_kept_only_within_bounds():
    ok = normalize_ai_item(good_item(1, price=254), set())
    assert ok["price"] == 250
    for bad in (19, 601, -5, "100", 99.5, True, None):
        it = normalize_ai_item(good_item(1, price=bad), set())
        assert it["price"] == compute_price(it["stats"], it["rarity"])


@pytest.mark.parametrize("over", [
    {"stats": {"confort": 9, "style": 1, "utilite": 3, "securite": 2, "sante": 1}},   # stat > 5
    {"stats": {"confort": -1, "style": 1, "utilite": 3, "securite": 2, "sante": 1}},  # négative
    {"stats": {"confort": 2, "style": 1, "utilite": 3, "securite": 2}},                # stat manquante
    {"stats": {"confort": 2, "style": 1, "utilite": 3, "securite": 2, "sante": 1, "x": 1}},
    {"stats": {"confort": "5", "style": 1, "utilite": 3, "securite": 2, "sante": 1}},
    {"stats": {"confort": 0, "style": 0, "utilite": 0, "securite": 0, "sante": 0}},    # somme nulle
    {"stats": {"confort": 5, "style": 5, "utilite": 5, "securite": 5, "sante": 5}},    # somme trop haute
    {"rarity": 4}, {"rarity": -1}, {"rarity": "rare"}, {"rarity": 1.5}, {"rarity": True},
    {"name": ""}, {"name": "x" * 41}, {"category": ""}, {"description": "d" * 141},
    {"tags": []}, {"tags": ["a"] * 5}, {"tags": [""]}, {"tags": "energie"},
])
def test_invalid_items_rejected(over):
    assert normalize_ai_item(good_item(1, **over), set()) is None


def test_missing_fields_rejected():
    for field in ("name", "category", "rarity", "stats", "tags"):
        d = good_item(1)
        del d[field]
        assert normalize_ai_item(d, set()) is None
    assert normalize_ai_item("pas un objet", set()) is None
    assert normalize_ai_item(None, set()) is None


def test_legendary_may_have_higher_total_but_capped():
    big = {"confort": 5, "style": 5, "utilite": 3, "securite": 1, "sante": 0}  # 14
    assert normalize_ai_item(good_item(1, rarity=3, stats=big), set()) is not None
    assert normalize_ai_item(good_item(1, rarity=1, stats=big), set()) is None


def test_duplicate_ids_get_suffix_and_never_collide_with_catalog():
    taken = {"ai_objet"}
    a = normalize_ai_item(good_item(1, name="Objet"), taken)
    b = normalize_ai_item(good_item(2, name="Objet"), taken)
    assert a["id"] != b["id"] and a["id"] != "ai_objet"


def test_control_chars_removed_from_text():
    it = normalize_ai_item(good_item(1, name="Gén\x00é\x1brateur"), set())
    assert it["name"] == "Générateur"


# ------------------------------------------------------------ parse_response
def test_parse_valid_response_with_code_fence():
    res = generator.parse_response("```json\n" + response() + "\n```", "survie", 6, set())
    assert len(res.items) == 12 and res.trials_source == "ai" and len(res.trials) == 3
    assert [t["id"] for t in res.trials] == ["epreuve_1", "epreuve_2", "epreuve_3"]


@pytest.mark.parametrize("text", ["", "pas du json", "[1,2,3]", "{", '{"items": "x"}',
                                  '{"items": []}', '{"items": [1,2,3]}', "x" * 50_000])
def test_malformed_responses_rejected(text):
    with pytest.raises(GameError):
        generator.parse_response(text, "construction", 6, set())


def test_too_few_valid_items_rejected():
    items = [good_item(i) for i in range(4)] + [good_item(9, rarity=9)] * 10
    with pytest.raises(GameError, match="valide"):
        generator.parse_response(response(items), "construction", 6, set())


def test_duplicate_names_dropped():
    items = [good_item(i) for i in range(7)] + [good_item(0)] * 3  # 3 doublons du nom « Objet martien 0 »
    res = generator.parse_response(response(items), "construction", 6, set())
    assert len(res.items) == 7 and len({i["id"] for i in res.items}) == 7


def test_item_count_capped():
    items = [good_item(i) for i in range(100)]
    res = generator.parse_response(response(items), "construction", 6, set())
    assert len(res.items) <= generator.MAX_RAW_ITEMS


def test_invalid_trials_fall_back_to_generic():
    bad = [{"name": "x", "stat": "confort", "threshold": 99}] * 3
    res = generator.parse_response(response(trials=bad), "survie", 6, set())
    assert res.trials == [] and res.trials_source == "generic"


def test_trials_ignored_outside_survival():
    res = generator.parse_response(response(), "construction", 6, set())
    assert res.trials == [] and res.trials_source == "none"


# ---------------------------------------------------- épreuves de Survie
def test_trial_validation():
    ok = normalize_ai_trials(good_trials())
    assert ok and ok[0]["stat"] == "securite"
    assert normalize_ai_trials(good_trials()[:2]) is None
    for over in ({"threshold": 3}, {"threshold": 13}, {"threshold": "9"}, {"stat": "magie"},
                 {"name": ""}, {"name": "x" * 41}):
        bad = good_trials()
        bad[0] = {**bad[0], **over}
        assert normalize_ai_trials(bad) is None  # il ne reste que 2 épreuves valides
    same = [dict(good_trials()[0]) for _ in range(3)]  # même stat répétée
    assert normalize_ai_trials(same) is None
    assert normalize_ai_trials("x") is None


# ---------------------------------------------------- API : parcours complet
def test_full_ai_flow(client, provider):
    s = new_room(client, mode="survie")
    assert s["room"]["settings"]["ready"] is False
    r = generate(client, s)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["items"]) == 12 and data["trials_source"] == "ai"
    assert data["generations_left"] == limits.MAX_GENERATIONS_PER_ROOM - 1
    # prompt : le scénario est encadré comme donnée, budget de sortie borné
    call = provider.calls[0]
    assert "<scenario>" in call["prompt"] and SCENARIO in call["prompt"]
    assert call["max_tokens"] == generator.MAX_TOKENS and call["timeout"] == generator.TIMEOUT_SECONDS
    # la partie ne peut pas démarrer sans validation de l'hôte
    b = client.post(f"/rooms/{s['code']}/join", json={"pseudo": "Bob"}).json()
    ids = [i["id"] for i in data["items"]][:8]
    with client.websocket_connect(f"/ws/{s['code']}?token={s['token']}") as wa, \
         client.websocket_connect(f"/ws/{s['code']}?token={b['token']}"):
        wa.send_json({"type": "start_game"})
        msg = _wait(wa, "error")
        assert "valider" in msg["message"]
        # validation : mélange d'objets IA et d'objets du catalogue
        sel = client.put(f"/rooms/{s['code']}/selection", headers=auth(s),
                         json={"item_ids": ids[:6] + ["plage_01", "cabane_01"]})
        assert sel.status_code == 200 and sel.json()["room"]["settings"]["ready"] is True
        wa.send_json({"type": "start_game"})
        game = _wait(wa, "game_state")["game"]
        assert game["creation_type"] == "ai" and game["phase"] == "auction"
        assert game["auction"]["item"]["id"] in ids[:6] + ["plage_01", "cabane_01"]
        assert [t["id"] for t in game["scenario"]["trials"]] == ["epreuve_1", "epreuve_2", "epreuve_3"]
        # plus de génération après le lancement
        assert generate(client, s).status_code == 409


def _wait(ws, kind):
    while True:
        m = ws.receive_json()
        if m["type"] == kind:
            return m


def test_selection_rules(client, provider):
    s = new_room(client)
    generate(client, s)
    base = f"/rooms/{s['code']}/selection"
    assert client.put(base, headers=auth(s), json={"item_ids": ["ai_inconnu"] * 2}).status_code == 400
    ids = [i["id"] for i in generate(client, s).json()["items"]]
    assert client.put(base, headers=auth(s), json={"item_ids": ids[:3]}).status_code == 400  # insuffisant
    assert client.put(base, headers=auth(s), json={"item_ids": ids[:6] + ids[:1]}).status_code == 400  # doublon
    # une régénération invalide la sélection précédente
    assert client.put(base, headers=auth(s), json={"item_ids": ids[:6]}).status_code == 200
    r = generate(client, s)
    assert r.status_code == 200
    ready = client.put(base, headers=auth(s), json={"item_ids": ["plage_01"] * 1})
    assert ready.status_code == 400


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
