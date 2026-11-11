"""API FastAPI : création / entrée de salon (HTTP) et temps réel (WebSocket)."""
import json
import os

from fastapi import FastAPI, Header, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import catalog, items, trials
from .ai import base as ai_base
from .ai import limits
from .errors import GameError
from .models import CreateRoomRequest, GenerateRequest, JoinRoomRequest, SelectionRequest
from .rooms import registry

app = FastAPI(title="BidBang")


@app.exception_handler(GameError)
async def game_error_handler(_request, exc: GameError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request, _exc: RequestValidationError):
    # Réponse volontairement sans détail : le format par défaut de FastAPI renvoie la
    # valeur reçue (`input`), ce qui pourrait refléter une clé API.
    return JSONResponse(status_code=422, content={"detail": "Requête invalide."})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/locations")
async def locations():
    return {"locations": catalog.list_locations()}


@app.get("/items")
async def list_items():
    """Objets du catalogue au format commun, pour la sélection d'une partie personnalisée."""
    return {"items": items.catalog_items(), "categories": items.categories(),
            "stats": list(items.STAT_KEYS), "trial_packs": trials.list_packs()}


@app.get("/ai/providers")
async def ai_providers():
    return {"providers": ai_base.provider_names()}


def _session_payload(room, player) -> dict:
    return {"code": room.code, "player_id": player["id"], "token": player["token"],
            "room": room.room_state()}


@app.post("/rooms")
async def create_room(body: CreateRoomRequest):
    room, player = registry.create(body.pseudo, body.settings)
    return _session_payload(room, player)


@app.post("/rooms/{code}/join")
async def join_room(code: str, body: JoinRoomRequest):
    room = registry.get(code)
    player = room.add_player(body.pseudo)
    await room.broadcast_room()
    return _session_payload(room, player)


_LOOPBACK = {"127.0.0.1", "localhost", "::1", "10.0.2.2"}


def _secure_transport(request: Request) -> bool:
    """La clé API ne transite qu'en HTTPS (ou en local pour le développement)."""
    if request.url.scheme == "https" or request.url.hostname in _LOOPBACK:
        return True
    return os.environ.get("BIDBANG_ALLOW_INSECURE_AI") == "1"


def _bearer(authorization: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "?"


def _authenticate(request: Request, code: str, authorization: str | None):
    """Salon existant + jeton de session valide, avec limite des tentatives échouées."""
    who = _client_id(request)
    if limits.failures.blocked(who):
        raise GameError("Trop de tentatives, patientez une minute.", 429)
    try:
        room = registry.get(code)
    except GameError:
        limits.failures.record(who)
        raise
    player = room.player_by_token(_bearer(authorization))
    if player is None:
        limits.failures.record(who)
        raise GameError("Session invalide.", 401)
    return room, player


@app.post("/rooms/{code}/ai/generate")
async def ai_generate(code: str, body: GenerateRequest, request: Request,
                      authorization: str | None = Header(default=None)):
    """Génération IA (hôte seulement). La clé est dans le corps JSON, en HTTPS : jamais
    dans l'URL, jamais stockée ni journalisée, jamais renvoyée."""
    if not _secure_transport(request):
        raise GameError("La clé API ne peut être envoyée qu'en HTTPS.", 400)
    room, player = _authenticate(request, code, authorization)
    provider = ai_base.get_provider(body.provider)
    api_key = body.api_key.get_secret_value()
    try:
        return await room.ai_generate(player["id"], provider, api_key)
    finally:
        del api_key


@app.put("/rooms/{code}/selection")
async def set_selection(code: str, body: SelectionRequest, request: Request,
                        authorization: str | None = Header(default=None)):
    room, player = _authenticate(request, code, authorization)
    await room.set_selection(player["id"], body.item_ids)
    return {"room": room.room_state()}


@app.websocket("/ws/{code}")
async def websocket_endpoint(ws: WebSocket, code: str, token: str = Query("")):
    try:
        room = registry.get(code)
    except GameError:
        await ws.close(code=4404)
        return
    player = room.player_by_token(token)
    if player is None:
        await ws.close(code=4401)
        return
    await ws.accept()
    pid = player["id"]
    await room.connect(pid, ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError
            except ValueError:
                await room.send_error(pid, "Message invalide.")
                continue
            if data.get("type") == "leave":
                await room.leave(pid)
                await ws.close()
                return
            try:
                await room.handle(pid, data)
            except GameError as e:
                await room.send_error(pid, e.message)
    except WebSocketDisconnect:
        pass
    finally:
        if pid in room.players:
            await room.disconnect(pid, ws)
