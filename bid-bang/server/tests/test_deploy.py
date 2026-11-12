"""Déploiement public (Vercel -> Railway) : CORS, origines WebSocket, mode production, limites."""
import subprocess
import sys
import time

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import config, rooms
from app.main import app
from app.rooms import registry

VERCEL = "https://bidbang.vercel.app"
EVIL = "https://evil.example"


@pytest.fixture
def client(monkeypatch):
    registry.rooms.clear()
    monkeypatch.setenv("ALLOWED_ORIGINS", VERCEL)
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def create(client, **headers):
    return client.post("/rooms", json={"pseudo": "Alice", "settings": {}}, headers=headers)


def test_root_and_health_answer(client):
    assert client.get("/").json() == {"service": "BidBang API", "status": "ok"}
    assert client.get("/health").json() == {"status": "ok"}


# -------------------------------------------------------------------- configuration
def test_allowed_origins_parsing(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", f" {VERCEL}/ , https://autre.example:8443,*,not-a-url, ")
    got = config.allowed_origins()
    assert VERCEL in got and "https://autre.example:8443" in got  # espaces et « / » final retirés
    assert "*" not in got and "not-a-url" not in got              # jamais de joker
    assert "http://localhost:8080" in got                          # développement : origines locales
    monkeypatch.setenv("BIDBANG_ENV", "production")
    assert config.allowed_origins() == [VERCEL, "https://autre.example:8443"]  # production : rien de local


def test_origin_allowed_rules(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", VERCEL)
    assert config.origin_allowed(None)                 # application native : pas d'Origin
    assert config.origin_allowed(VERCEL) and config.origin_allowed(VERCEL + "/")
    assert not config.origin_allowed(EVIL) and not config.origin_allowed("null")
    assert not config.origin_allowed("https://bidbang.vercel.app.evil.example")
    assert not config.origin_allowed("http://bidbang.vercel.app")  # le schéma compte
    monkeypatch.setenv("ALLOWED_ORIGIN_REGEX", r"https://bidbang-[a-z0-9]+-lucas\.vercel\.app")
    assert config.origin_allowed("https://bidbang-abc123-lucas.vercel.app")
    assert not config.origin_allowed("https://bidbang-abc123-lucas.vercel.app.evil.example")
    monkeypatch.setenv("ALLOWED_ORIGIN_REGEX", "([")  # motif invalide : ignoré, pas d'erreur
    assert not config.origin_allowed("https://bidbang-abc123-lucas.vercel.app")


# ------------------------------------------------------------------------------ CORS
def test_cors_headers_only_for_allowed_origin(client):
    r = create(client, Origin=VERCEL)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == VERCEL and r.headers["vary"] == "Origin"
    assert "access-control-allow-credentials" not in r.headers  # jetons en en-tête, pas de cookies
    bad = create(client, Origin=EVIL)
    assert bad.status_code == 200 and "access-control-allow-origin" not in bad.headers
    assert "access-control-allow-origin" not in create(client).headers  # sans Origin : rien


def test_preflight_for_post_and_put_with_authorization(client):
    for method in ("POST", "PUT", "GET"):
        r = client.options("/rooms", headers={"Origin": VERCEL, "Access-Control-Request-Method": method,
                                              "Access-Control-Request-Headers": "authorization,content-type"})
        assert r.status_code == 204
        assert r.headers["access-control-allow-origin"] == VERCEL
        assert {"POST", "PUT", "GET"} <= {m.strip() for m in r.headers["access-control-allow-methods"].split(",")}
        allowed = r.headers["access-control-allow-headers"].lower()
        assert "authorization" in allowed and "content-type" in allowed
    refused = client.options("/rooms", headers={"Origin": EVIL, "Access-Control-Request-Method": "POST"})
    assert refused.status_code == 403 and "access-control-allow-origin" not in refused.headers


def test_cors_error_responses_also_carry_headers(client):
    r = client.post("/rooms/ZZZZZZ/join", json={"pseudo": "Bob"}, headers={"Origin": VERCEL})
    assert r.status_code == 400 and r.headers["access-control-allow-origin"] == VERCEL
    r = client.put("/rooms/ZZZZZZ/selection", json={"item_ids": []}, headers={"Origin": VERCEL})
    assert r.status_code == 400 and r.headers["access-control-allow-origin"] == VERCEL


def test_default_dev_origins_allow_the_local_web_test(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    registry.rooms.clear()
    with TestClient(app, base_url="https://testserver") as c:
        r = create(c, Origin="http://localhost:8080")
        assert r.headers["access-control-allow-origin"] == "http://localhost:8080"
        assert "access-control-allow-origin" not in create(c, Origin=VERCEL).headers


# ----------------------------------------------------------------------- WebSocket
def test_websocket_origin_checks(client):
    a = create(client).json()
    url = f"/ws/{a['code']}?token={a['token']}"
    with client.websocket_connect(url) as ws:                      # application native : sans Origin
        assert ws.receive_json()["type"] == "room_state"
    with client.websocket_connect(url, headers={"origin": VERCEL}) as ws:  # navigateur autorisé
        assert ws.receive_json()["type"] == "room_state"
    with pytest.raises(WebSocketDisconnect) as exc:                 # navigateur d'un autre site
        with client.websocket_connect(url, headers={"origin": EVIL}):
            pass
    assert exc.value.code in (4403, 403, 1008)
    with pytest.raises(WebSocketDisconnect):                        # le jeton reste exigé
        with client.websocket_connect(f"/ws/{a['code']}?token=nope", headers={"origin": VERCEL}):
            pass


def test_oversized_websocket_message_is_refused(client):
    a = create(client).json()
    with client.websocket_connect(f"/ws/{a['code']}?token={a['token']}") as ws:
        ws.receive_json()
        ws.send_text("x" * 9000)
        assert "trop long" in ws.receive_json()["message"]
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"  # la connexion reste utilisable


# --------------------------------------------------------------------- production
def test_production_mode_disables_dev_features(monkeypatch):
    monkeypatch.setenv("BIDBANG_ENV", "production")
    monkeypatch.setenv("BIDBANG_MOCK_AI", "1")
    monkeypatch.setenv("BIDBANG_ALLOW_ENV_KEY", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-SECRET-0123456789")
    monkeypatch.setenv("BIDBANG_ALLOW_INSECURE_AI", "1")
    registry.rooms.clear()
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert "mock" not in [p["id"] for p in c.get("/ai/providers").json()["providers"]]
        s = c.post("/rooms", json={"pseudo": "A", "settings": {"creation_type": "ai", "item_count": 6,
                                                               "scenario": {"description": "Un onze."}}}).json()
        h = {"Authorization": f"Bearer {s['token']}"}
        env = c.post(f"/rooms/{s['code']}/ai/generate", json={"provider": "gemini", "use_env_key": True}, headers=h)
        assert env.status_code == 400 and "AIza" not in env.text      # clé d'environnement ignorée
    with TestClient(app, base_url="http://jeu.example.com") as c:     # clé API jamais en HTTP clair
        s = c.post("/rooms", json={"pseudo": "A", "settings": {"creation_type": "ai", "item_count": 6,
                                                               "scenario": {"description": "Un onze."}}}).json()
        r = c.post(f"/rooms/{s['code']}/ai/generate", json={"provider": "gemini", "api_key": "k" * 12},
                   headers={"Authorization": f"Bearer {s['token']}"})
        assert r.status_code == 400 and "HTTPS" in r.json()["detail"]


def test_api_docs_are_off_in_production():
    code = ("import os; os.environ['BIDBANG_ENV']='production'\n"
            "from starlette.testclient import TestClient\nfrom app.main import app\n"
            "c = TestClient(app)\n"
            "print([c.get(p).status_code for p in ('/docs', '/redoc', '/openapi.json', '/health')])")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=".", timeout=60)
    assert out.stdout.strip().endswith("[404, 404, 404, 200]"), out.stdout + out.stderr


# ----------------------------------------------------------------------- limites
def test_server_full_returns_503(client, monkeypatch):
    monkeypatch.setenv("MAX_ROOMS", "2")
    assert create(client).status_code == 200 and create(client).status_code == 200
    r = create(client)
    assert r.status_code == 503 and "plein" in r.json()["detail"]
    registry.rooms.clear()
    assert create(client).status_code == 200


def test_room_creation_is_rate_limited_per_address(client):
    from app.ai import limits
    for _ in range(limits.MAX_ROOM_CREATIONS_PER_MINUTE):
        assert create(client).status_code == 200
    r = create(client)
    assert r.status_code == 429 and "patientez" in r.json()["detail"]


def test_guessing_room_codes_is_rate_limited(client):
    from app.ai import limits
    for _ in range(limits.MAX_FAILURES_PER_MINUTE):
        assert client.post("/rooms/ZZZZZZ/join", json={"pseudo": "Bob"}).status_code == 400
    assert client.post("/rooms/ZZZZZZ/join", json={"pseudo": "Bob"}).status_code == 429
    real = create(client).json()
    assert client.post(f"/rooms/{real['code']}/join", json={"pseudo": "Bob"}).status_code == 429  # même adresse


def test_unused_room_expires(client, monkeypatch):
    monkeypatch.setattr(rooms, "EMPTY_ROOM_TTL", 0.05)
    a = create(client).json()
    assert a["code"] in registry.rooms
    time.sleep(0.4)
    assert a["code"] not in registry.rooms                      # personne ne s'est connecté : supprimé
    b = create(client).json()
    with client.websocket_connect(f"/ws/{b['code']}?token={b['token']}") as ws:
        ws.receive_json()
        time.sleep(0.4)
        assert b["code"] in registry.rooms                      # une connexion garde le salon


def test_startup_command_of_railway_works(tmp_path):
    """La commande de démarrage de railway.json démarre réellement (un seul processus, $PORT)."""
    import json
    import os
    import signal
    import urllib.request
    cfg = json.load(open("railway.json", encoding="utf-8"))
    cmd = cfg["deploy"]["startCommand"]
    assert "$PORT" in cmd and "--workers" not in cmd.replace("--workers 1", "") and cfg["deploy"].get("numReplicas", 1) == 1
    port = 18000 + os.getpid() % 1000
    env = {**os.environ, "PORT": str(port), "BIDBANG_ENV": "production", "ALLOWED_ORIGINS": VERCEL}
    proc = subprocess.Popen(cmd, shell=True, env=env, cwd=".", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True)
    try:
        for _ in range(60):
            try:
                body = urllib.request.urlopen(f"http://127.0.0.1:{port}{cfg['deploy']['healthcheckPath']}").read()
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise AssertionError("le serveur n'a pas démarré")
        assert b"ok" in body
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Origin": VERCEL})
        assert urllib.request.urlopen(req).headers["Access-Control-Allow-Origin"] == VERCEL
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
