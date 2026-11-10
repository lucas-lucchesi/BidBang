"""API FastAPI : création / entrée de salon (HTTP) et temps réel (WebSocket)."""
import json

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from . import catalog
from .errors import GameError
from .models import CreateRoomRequest, JoinRoomRequest
from .rooms import registry

app = FastAPI(title="BidBang")


@app.exception_handler(GameError)
async def game_error_handler(_request, exc: GameError):
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/locations")
async def locations():
    return {"locations": catalog.list_locations()}


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
