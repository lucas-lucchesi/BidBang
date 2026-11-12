"""Fournisseur Gemini (SDK officiel google-genai) : réponses simulées par un transport httpx,
aucune clé réelle, aucun accès Internet, aucun quota consommé."""
import json
import logging

import httpx
import pytest
from starlette.testclient import TestClient

from app.ai import base as ai_base
from app.ai import gemini_provider, generator, limits
from app.ai.base import ProviderError
from app.ai.gemini_provider import DEFAULT_MODEL, GeminiProvider
from app.main import app
from app.rooms import registry

KEY = "AIzaSyTESTSECRET-0123456789abcdef"


def gemini_json(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}


PROFILE = {"goal": "Composer un onze", "allowed_entity_types": ["football_player"],
           "real_entities_only": False, "organization": None, "required_roles": [],
           "allow_unrelated_items": False}


def situation_text(n_items=12):
    items = [{"name": f"Légende {i}", "description": "Un joueur.", "category": "Milieu",
              "entity_type": "football_player", "is_real": False,
              "rarity": i % 2, "price": 120, "points": 8 + i * 7} for i in range(n_items)]
    return json.dumps({"title": "Onze de légende", "description": "Les meilleurs joueurs.",
                       "profile": PROFILE, "items": items})


class Sent(list):
    state: dict


@pytest.fixture
def sent(monkeypatch):
    """Installe un faux Gemini ; renvoie la liste des requêtes reçues. `reply` : réponse à servir."""
    seen = Sent()
    state = {"reply": lambda: httpx.Response(200, json=gemini_json(situation_text()))}

    def handler(req):
        seen.append(req)
        return state["reply"]()

    monkeypatch.setattr(gemini_provider, "TRANSPORT", httpx.MockTransport(handler))
    seen.state = state
    return seen


async def call(**kw):
    args = dict(api_key=KEY, system="SYS", prompt="PROMPT", max_tokens=321, timeout=5)
    args.update(kw)
    return await GeminiProvider().complete(**args)


# --------------------------------------------------------------- requête
async def test_request_uses_flash_lite_structured_output_and_no_tools(sent, monkeypatch):
    monkeypatch.delenv("BIDBANG_GEMINI_MODEL", raising=False)
    schema = generator.response_schema()
    assert await call(json_schema=schema) == situation_text()
    assert len(sent) == 1  # aucun nouvel essai automatique
    req = sent[0]
    assert req.url.host == "generativelanguage.googleapis.com"
    assert f"models/{DEFAULT_MODEL}:generateContent" in str(req.url) and DEFAULT_MODEL == "gemini-3.5-flash-lite"
    assert KEY not in str(req.url) and KEY.encode() not in req.content   # clé : en-tête seulement
    assert req.headers["x-goog-api-key"] == KEY
    body = json.loads(req.content)
    cfg = body["generationConfig"]
    assert cfg["responseMimeType"] == "application/json" and cfg["responseJsonSchema"] == schema
    assert cfg["maxOutputTokens"] == 321
    assert "SYS" in json.dumps(body["systemInstruction"]) and "PROMPT" in json.dumps(body["contents"])
    # ni recherche Internet, ni outils, ni image
    assert "tools" not in body and "toolConfig" not in body
    assert "responseModalities" not in cfg and "imageConfig" not in cfg


async def test_model_is_configurable_from_backend(sent, monkeypatch):
    monkeypatch.setenv("BIDBANG_GEMINI_MODEL", "gemini-2.5-flash-lite")
    await call()
    assert "models/gemini-2.5-flash-lite:" in str(sent[0].url)
    for bad in ("x/../../evil?key=1", "", "a b"):
        monkeypatch.setenv("BIDBANG_GEMINI_MODEL", bad)
        with pytest.raises(ProviderError) as e:
            await call()
        assert e.value.status == 500
    assert len(sent) == 1


async def test_schema_is_optional(sent):
    await call()
    assert "responseJsonSchema" not in json.loads(sent[0].content)["generationConfig"]


# ---------------------------------------------------------------- erreurs
@pytest.mark.parametrize("status,fragment,out", [
    (429, "Quota gratuit", 429), (400, "clé", 502), (401, "clé", 502), (403, "clé", 502),
    (404, "introuvable", 502), (500, "(500)", 502), (503, "(503)", 502), (504, "à temps", 504)])
async def test_http_errors_become_generic_french_messages(sent, caplog, status, fragment, out):
    caplog.set_level(logging.DEBUG)
    body = {"error": {"code": status, "message": f"bad key {KEY}", "status": "X"}}
    sent.state["reply"] = lambda: httpx.Response(status, json=body)
    with pytest.raises(ProviderError) as exc:
        await call()
    assert fragment in exc.value.message and exc.value.status == out
    assert KEY not in exc.value.message and KEY not in repr(exc.value) and KEY not in caplog.text
    assert exc.value.__cause__ is None
    assert len(sent) == 1  # un 429 n'est pas réessayé : on ne consomme pas davantage de quota


async def test_quota_message_promises_no_paid_fallback(sent):
    sent.state["reply"] = lambda: httpx.Response(429, json={"error": {"code": 429, "message": "quota"}})
    with pytest.raises(ProviderError) as exc:
        await call()
    assert "automatiquement" in exc.value.message and "payante" in exc.value.message
    assert {r.url.host for r in sent} == {"generativelanguage.googleapis.com"}  # aucun autre hôte


async def test_timeout_and_connection_errors(sent):
    def boom(exc):
        def reply():
            raise exc
        return reply

    sent.state["reply"] = boom(httpx.ReadTimeout(f"secret {KEY}"))
    with pytest.raises(ProviderError) as e1:
        await call(timeout=2)
    assert KEY not in e1.value.message and e1.value.status in (502, 504)
    sent.state["reply"] = boom(httpx.ConnectError(f"secret {KEY}"))
    with pytest.raises(ProviderError) as e2:
        await call(timeout=2)
    assert e2.value.status == 502 and KEY not in e2.value.message


@pytest.mark.parametrize("payload", [
    {"promptFeedback": {"blockReason": "SAFETY"}},
    {"candidates": [{"finishReason": "SAFETY"}]},
    {"candidates": [{"finishReason": "PROHIBITED_CONTENT", "content": {"parts": [{"text": "x"}]}}]},
])
async def test_blocked_content_refused(sent, payload):
    sent.state["reply"] = lambda: httpx.Response(200, json=payload)
    with pytest.raises(ProviderError, match="refusé"):
        await call()


@pytest.mark.parametrize("payload", [{}, {"candidates": []}, {"candidates": [{"content": {"parts": []}}]},
                                     {"candidates": [{"content": {"parts": [{"text": ""}]}}]}])
async def test_empty_or_odd_payload_rejected(sent, payload):
    sent.state["reply"] = lambda: httpx.Response(200, json=payload)
    with pytest.raises(ProviderError):
        await call()


async def test_multipart_text_is_joined(sent):
    sent.state["reply"] = lambda: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{"}, {"text": "}"}]}}]})
    assert await call() == "{}"


# ------------------------------------------------------- schéma structuré
def test_schema_asks_for_points_and_has_no_criteria():
    s = generator.response_schema()
    item = s["properties"]["items"]["items"]
    assert item["properties"]["points"]["maximum"] == 100 and "points" in item["required"]
    assert "criteria" not in s["properties"] and "winner" not in json.dumps(s)
    assert set(s["required"]) == {"title", "description", "profile", "items"}
    json.dumps(s)  # sérialisable


async def test_generator_sends_schema_only_to_structured_providers(sent):
    res = await generator.generate(GeminiProvider(), KEY, {"title": "T", "description": "Une situation."},
                                   "normal", 6, set())
    assert json.loads(sent[0].content)["generationConfig"]["responseJsonSchema"] == generator.response_schema()
    # mêmes validateurs : cartes validées, points de l'IA conservés, aucun critère
    assert res.situation["criteria"] == [] and len(res.items) == 12
    assert [i["points"] for i in res.items][:3] == [8, 15, 22]

    class Plain:  # fournisseur sans sorties structurées : aucun argument supplémentaire
        name, label = "plain", "Plain"

        async def complete(self, *, api_key, system, prompt, max_tokens, timeout):
            return situation_text()

    assert len((await generator.generate(Plain(), KEY, {"title": "T", "description": "Une situation."},
                                         "normal", 6, set())).items) == 12


async def test_invalid_gemini_content_is_rejected_by_existing_validators(sent):
    sent.state["reply"] = lambda: httpx.Response(200, json=gemini_json(json.dumps(
        {"title": "x", "description": "y",
         "items": [{"name": "A", "rarity": 9, "points": 500}] * 8})))
    with pytest.raises(Exception, match="valide"):
        await generator.generate(GeminiProvider(), KEY, {"title": "T", "description": "Une situation."},
                                 "normal", 6, set())


# ------------------------------------------------- API : parcours complet
@pytest.fixture
def client(sent):
    registry.rooms.clear()
    limits.reset()
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    limits.reset()


def _room(client, creation="ai"):
    r = client.post("/rooms", json={"pseudo": "Alice", "settings": {
        "creation_type": creation, "item_count": 6,
        "scenario": {"description": "Une apocalypse zombie en ville."}}})
    assert r.status_code == 200, r.text
    return r.json()


def _gen(client, s, **body):
    body.setdefault("provider", "gemini")
    return client.post(f"/rooms/{s['code']}/ai/generate", json=body,
                       headers={"Authorization": f"Bearer {s['token']}"})


def test_full_gemini_flow_keeps_ai_points(client, sent, monkeypatch):
    monkeypatch.setattr(limits, "MIN_INTERVAL_SECONDS", 0.0)
    s = _room(client)
    r = _gen(client, s, api_key=KEY)
    assert r.status_code == 200, r.text
    data = r.json()
    assert KEY not in r.text
    assert data["situation"]["criteria"] == [] and len(data["items"]) == 12
    assert [i["points"] for i in data["items"]][:2] == [8, 15]  # points attribués par l'IA
    # la clé n'est ni dans l'état du salon ni dans les journaux
    room = registry.get(s["code"])
    assert KEY not in json.dumps(room.room_state()) and KEY not in repr(room.__dict__)
    ids = [i["id"] for i in data["items"]][:6]
    ok = client.put(f"/rooms/{s['code']}/selection", headers={"Authorization": f"Bearer {s['token']}"},
                    json={"item_ids": ids})
    assert ok.status_code == 200 and ok.json()["room"]["settings"]["ready"] is True


def test_quota_exceeded_returns_429_without_fallback(client, sent):
    sent.state["reply"] = lambda: httpx.Response(429, json={"error": {"code": 429, "message": KEY}})
    s = _room(client)
    r = _gen(client, s, api_key=KEY)
    assert r.status_code == 429 and "Quota gratuit" in r.json()["detail"] and KEY not in r.text
    assert len(sent) == 1 and not registry.get(s["code"]).ai_busy
    assert registry.get(s["code"]).ai_items == {}  # rien n'a été créé


def test_gemini_and_openai_both_listed_and_selectable(client):
    ids = {p["id"] for p in client.get("/ai/providers").json()["providers"]}
    assert {"gemini", "openai"} <= ids
    assert ai_base.get_provider("gemini").structured is True
    assert not getattr(ai_base.get_provider("openai"), "structured", False)


# ----------------------------------------------- clé GEMINI_API_KEY (local)
def _env_client(monkeypatch, host="http://127.0.0.1", allow=True, key=KEY):
    registry.rooms.clear()
    limits.reset()
    monkeypatch.setattr(limits, "MIN_INTERVAL_SECONDS", 0.0)
    if key:
        monkeypatch.setenv("GEMINI_API_KEY", key)
    else:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    if allow:
        monkeypatch.setenv("BIDBANG_ALLOW_ENV_KEY", "1")
    else:
        monkeypatch.delenv("BIDBANG_ALLOW_ENV_KEY", raising=False)
    return TestClient(app, base_url=host)


def test_env_key_works_locally_when_enabled(sent, monkeypatch):
    with _env_client(monkeypatch) as c:
        s = _room(c)
        r = _gen(c, s, use_env_key=True)
        assert r.status_code == 200, r.text
        assert sent[0].headers["x-goog-api-key"] == KEY and KEY not in r.text


@pytest.mark.parametrize("kw", [dict(allow=False), dict(key=""), dict(host="https://jeu.example.com")])
def test_env_key_refused_unless_local_and_enabled(sent, monkeypatch, kw):
    with _env_client(monkeypatch, **kw) as c:
        s = _room(c)
        r = _gen(c, s, use_env_key=True)
        assert r.status_code == 400 and "clé" in r.json()["detail"] and not sent
        assert KEY not in r.text


def test_env_key_not_used_for_other_providers_or_by_default(sent, monkeypatch):
    with _env_client(monkeypatch) as c:
        s = _room(c)
        assert _gen(c, s, provider="openai", use_env_key=True).status_code == 400
        assert _gen(c, s).status_code == 422  # ni clé ni use_env_key
        assert not sent


def test_key_never_in_logs_even_on_provider_failure(client, sent, caplog):
    caplog.set_level(logging.DEBUG)
    sent.state["reply"] = lambda: httpx.Response(500, json={"error": {"message": KEY}})
    s = _room(client)
    r = _gen(client, s, api_key=KEY)
    assert r.status_code == 502 and KEY not in r.text and KEY not in caplog.text


def test_all_three_creation_types_still_work_with_gemini_data(sent):
    """Classique et personnalisée : points calculés par le serveur ; IA : points de l'IA."""
    import random

    from app import scoring
    from app.game import Game
    res = generator.parse_response(situation_text(), 6, set(), {"title": "T", "description": "Situation."})
    crit = [{"id": "soins", "necessary": True, "importance": 5}]
    games = [
        Game([("a", "A"), ("b", "B")], {"theme_id": "cabane", "item_count": 6}, rng=random.Random(1)),
        Game([("a", "A"), ("b", "B")], {"creation_type": "custom", "item_count": 6,
             "item_ids": ["villa_10", "cabane_06", "cabane_01", "cabane_02", "plage_01", "plage_02"],
             "scenario": {"description": "Une situation.", "criteria": crit}}, rng=random.Random(1)),
    ]
    for g in games:
        assert all(i["points"] == scoring.item_points(i, g.situation["criteria"]) for i in g.items)
    ids = [i["id"] for i in res.items][:8]
    ai = Game([("a", "A"), ("b", "B")], {"creation_type": "ai", "item_count": 8, "item_ids": ids,
              "scenario": {"description": "Une situation.", "criteria": []}},
              rng=random.Random(1), pool=res.new_items)
    given = {i["id"]: i["points"] for i in res.items}
    assert all(i["points"] == given[i["id"]] for i in ai.items)
