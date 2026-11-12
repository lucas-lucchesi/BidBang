"""API FastAPI : création / entrée de salon (HTTP) et temps réel (WebSocket)."""
import json
import os

from fastapi import FastAPI, Header, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from . import catalog, config, criteria, items, scoring
from .ai import base as ai_base
from .ai import limits
from .errors import GameError
from .models import (CreateRoomRequest, GenerateRequest, JoinRoomRequest, PreviewRequest,
                     SelectionRequest)
from .rooms import registry

_DOCS = None if config.is_production() else "/docs"  # pas de documentation d'API sur le serveur public
app = FastAPI(title="BidBang", docs_url=_DOCS, redoc_url=None,
              openapi_url=None if config.is_production() else "/openapi.json")

CORS_METHODS = "GET, POST, PUT, OPTIONS"
CORS_HEADERS = "Authorization, Content-Type"
MAX_WS_MESSAGE = 8192  # caractères : les messages du jeu sont minuscules


@app.middleware("http")
async def cors(request: Request, call_next):
    """CORS pour la version Web (Vercel) : seules les origines de `config.allowed_origins()`
    reçoivent les en-têtes qui permettent au navigateur de lire la réponse. Les jetons passent
    par l'en-tête Authorization, jamais par des cookies : pas de `Allow-Credentials`."""
    origin = request.headers.get("origin")
    allowed = origin is not None and config.origin_allowed(origin)
    if request.method == "OPTIONS" and origin is not None and "access-control-request-method" in request.headers:
        if not allowed:
            return Response(status_code=403)
        return Response(status_code=204, headers={
            "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": CORS_METHODS,
            "Access-Control-Allow-Headers": CORS_HEADERS, "Access-Control-Max-Age": "600",
            "Vary": "Origin"})
    response = await call_next(request)
    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    return response


@app.exception_handler(GameError)
async def game_error_handler(_request, exc: GameError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request, _exc: RequestValidationError):
    # Réponse volontairement sans détail : le format par défaut de FastAPI renvoie la
    # valeur reçue (`input`), ce qui pourrait refléter une clé API.
    return JSONResponse(status_code=422, content={"detail": "Requête invalide."})


@app.get("/")
async def root():
    """Page d'accueil de l'API : évite un « Not Found » déroutant quand on ouvre l'adresse du serveur
    dans un navigateur. Le jeu lui-même est le client Web (Vercel) ou l'application native."""
    return {"service": "BidBang API", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/locations")
async def locations():
    locs = catalog.list_locations()
    for loc in locs:
        loc["criteria"] = criteria.with_labels(loc["criteria"])
    return {"locations": locs}


@app.get("/items")
async def list_items():
    """Objets du catalogue au format commun, pour la sélection d'une partie personnalisée."""
    return {"items": items.catalog_items(), "locations": items.locations_summary(),
            "criteria": criteria.list_criteria(), "templates": criteria.templates()}


@app.post("/scoring/preview")
async def scoring_preview(body: PreviewRequest):
    """Points des objets du catalogue pour des critères donnés (aperçu : rien n'est créé ni figé)."""
    crit = criteria.clean_criteria(body.criteria)
    known = items.catalog_item_map()
    if len(set(body.item_ids)) != len(body.item_ids) or any(i not in known for i in body.item_ids):
        raise GameError("Sélection d'objets invalide.")
    return {"criteria": criteria.with_labels(crit),
            "items": scoring.freeze_items([known[i] for i in body.item_ids], crit)}


@app.get("/ai/providers")
async def ai_providers():
    return {"providers": ai_base.provider_names()}


def _session_payload(room, player) -> dict:
    return {"code": room.code, "player_id": player["id"], "token": player["token"],
            "room": room.room_state()}


@app.post("/rooms")
async def create_room(body: CreateRoomRequest, request: Request):
    who = _client_id(request)
    if limits.creations.blocked(who):
        raise GameError("Trop de salons créés, patientez une minute.", 429)
    room, player = registry.create(body.pseudo, body.settings)
    limits.creations.record(who)
    room.expire_if_unused()  # un salon que personne n'ouvre en WebSocket disparaît au bout de 5 minutes
    return _session_payload(room, player)


@app.post("/rooms/{code}/join")
async def join_room(code: str, body: JoinRoomRequest, request: Request):
    who = _client_id(request)
    if limits.failures.blocked(who):
        raise GameError("Trop de tentatives, patientez une minute.", 429)
    try:
        room = registry.get(code)
    except GameError:
        limits.failures.record(who)  # freine l'essai de codes au hasard
        raise
    player = room.add_player(body.pseudo)
    await room.broadcast_room()
    return _session_payload(room, player)


_LOOPBACK = {"127.0.0.1", "localhost", "::1", "10.0.2.2"}


def _secure_transport(request: Request) -> bool:
    """La clé API ne transite qu'en HTTPS (ou en local pour le développement)."""
    if request.url.scheme == "https" or request.url.hostname in _LOOPBACK:
        return True
    return not config.is_production() and os.environ.get("BIDBANG_ALLOW_INSECURE_AI") == "1"


def _env_key(request: Request, provider: str) -> str:
    """Clé Gemini lue dans GEMINI_API_KEY, pour les essais locaux seulement : il faut
    BIDBANG_ALLOW_ENV_KEY=1 et une requête venant de la machine locale. Ainsi un serveur
    public ne dépense jamais la clé de son propriétaire pour un inconnu."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if provider != "gemini" or config.is_production() or os.environ.get("BIDBANG_ALLOW_ENV_KEY") != "1" \
            or request.url.hostname not in _LOOPBACK or not key:
        raise GameError("Aucune clé serveur utilisable : collez votre clé API.", 400)
    return key


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
    api_key = body.api_key.get_secret_value() if body.api_key is not None \
        else _env_key(request, body.provider)
    try:
        return await room.ai_generate(player["id"], provider, api_key)
    finally:
        del api_key


@app.put("/rooms/{code}/selection")
async def set_selection(code: str, body: SelectionRequest, request: Request,
                        authorization: str | None = Header(default=None)):
    room, player = _authenticate(request, code, authorization)
    preview = await room.set_selection(player["id"], body.item_ids, body.criteria)
    return {"room": room.room_state(), **preview}


@app.websocket("/ws/{code}")
async def websocket_endpoint(ws: WebSocket, code: str, token: str = Query("")):
    # Un navigateur envoie toujours Origin : on refuse les sites non autorisés. Une application
    # native n'en envoie pas. L'authentification par jeton reste exigée dans les deux cas.
    if not config.origin_allowed(ws.headers.get("origin")):
        await ws.close(code=4403)
        return
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
            if len(raw) > MAX_WS_MESSAGE:
                await room.send_error(pid, "Message trop long.")
                continue
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
