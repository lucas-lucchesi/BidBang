"""Salons : joueurs, connexions WebSocket, chronomètres, diffusion de l'état."""
import asyncio
import random
import secrets
from typing import Any

from .errors import GameError
from .game import Game, validate_settings

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans O/0/I/1
CODE_LENGTH = 6
MAX_PLAYERS = 4
MAX_PSEUDO = 16
EMPTY_ROOM_TTL = 300  # secondes avant suppression d'un salon sans connexion


def clean_pseudo(raw: str) -> str:
    pseudo = " ".join((raw or "").split())[:MAX_PSEUDO]
    if not pseudo:
        raise GameError("Pseudo invalide.")
    return pseudo


class Room:
    def __init__(self, code: str, settings: dict):
        self.code = code
        self.settings = settings
        self.players: dict[str, dict] = {}  # id -> {id, pseudo, token, connected}
        self.sockets: dict[str, Any] = {}   # id -> WebSocket
        self.host_id: str | None = None
        self.status = "lobby"  # lobby | playing | finished
        self.game: Game | None = None
        self._timer: asyncio.Task | None = None
        self._cleanup: asyncio.Task | None = None

    # ---------------------------------------------------------- joueurs
    def add_player(self, pseudo: str) -> dict:
        if self.status != "lobby":
            raise GameError("La partie a déjà commencé.")
        if len(self.players) >= MAX_PLAYERS:
            raise GameError("Le salon est complet.")
        pseudo = clean_pseudo(pseudo)
        if any(p["pseudo"].lower() == pseudo.lower() for p in self.players.values()):
            raise GameError("Ce pseudo est déjà pris dans ce salon.")
        pid = secrets.token_hex(4)
        player = {"id": pid, "pseudo": pseudo, "token": secrets.token_urlsafe(16),
                  "connected": False}
        self.players[pid] = player
        if self.host_id is None:
            self.host_id = pid
        return player

    def player_by_token(self, token: str) -> dict | None:
        for p in self.players.values():
            if secrets.compare_digest(p["token"], token or ""):
                return p
        return None

    def remove_player(self, pid: str) -> None:
        self.players.pop(pid, None)
        self.sockets.pop(pid, None)
        if self.host_id == pid:
            self.host_id = next(iter(self.players), None)

    def room_state(self) -> dict:
        return {"code": self.code, "status": self.status, "host_id": self.host_id,
                "settings": self.settings, "max_players": MAX_PLAYERS,
                "players": [{"id": p["id"], "pseudo": p["pseudo"],
                             "connected": p["connected"]}
                            for p in self.players.values()]}

    # --------------------------------------------------------- diffusion
    async def _send(self, pid: str, message: dict) -> None:
        ws = self.sockets.get(pid)
        if ws is None:
            return
        try:
            await ws.send_json(message)
        except Exception:
            self.sockets.pop(pid, None)
            if pid in self.players:
                self.players[pid]["connected"] = False

    async def broadcast_room(self) -> None:
        msg = {"type": "room_state", "room": self.room_state()}
        for pid in list(self.sockets):
            await self._send(pid, msg)

    async def broadcast_game(self) -> None:
        if self.game is None:
            return
        for pid in list(self.sockets):
            await self._send(pid, {"type": "game_state",
                                   "game": self.game.snapshot(pid)})

    async def send_error(self, pid: str, message: str) -> None:
        await self._send(pid, {"type": "error", "message": message})

    # ------------------------------------------------------ connexions
    async def connect(self, pid: str, ws) -> None:
        old = self.sockets.get(pid)
        self.sockets[pid] = ws
        self.players[pid]["connected"] = True
        if self._cleanup:
            self._cleanup.cancel()
            self._cleanup = None
        if old is not None and old is not ws:
            try:
                await old.close()
            except Exception:
                pass
        await self.broadcast_room()
        if self.game is not None:
            await self._send(pid, {"type": "game_state",
                                   "game": self.game.snapshot(pid)})

    async def disconnect(self, pid: str, ws) -> None:
        if self.sockets.get(pid) is not ws:
            return  # remplacée par une reconnexion
        self.sockets.pop(pid, None)
        if pid in self.players:
            self.players[pid]["connected"] = False
        await self.broadcast_room()
        if not self.sockets:
            self._cleanup = asyncio.create_task(self._expire())

    async def _expire(self) -> None:
        await asyncio.sleep(EMPTY_ROOM_TTL)
        if not self.sockets:
            self.close()
            registry.rooms.pop(self.code, None)

    def close(self) -> None:
        if self._timer:
            self._timer.cancel()
        if self._cleanup:
            self._cleanup.cancel()

    # ----------------------------------------------------------- partie
    async def start_game(self, pid: str) -> None:
        if pid != self.host_id:
            raise GameError("Seul l'hôte peut lancer la partie.")
        if self.status != "lobby":
            raise GameError("La partie a déjà commencé.")
        if len(self.players) < 2:
            raise GameError("Il faut au moins 2 joueurs.")
        self.game = Game([(p["id"], p["pseudo"]) for p in self.players.values()],
                         self.settings)
        self.status = "playing"
        await self.broadcast_room()
        await self.after_change()

    async def after_change(self) -> None:
        """Diffuse l'état, met à jour le statut et reprogramme le chronomètre."""
        if self.game and self.game.phase == "finished" and self.status != "finished":
            self.status = "finished"
            await self.broadcast_room()
        await self.broadcast_game()
        self._schedule_timer()

    def _schedule_timer(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self.game is None:
            return
        deadline = self.game.deadline()
        if deadline is None:
            return
        delay = max(0.0, deadline - self.game.clock())
        self._timer = asyncio.create_task(self._run_timer(self.game.version, delay))

    async def _run_timer(self, version: int, delay: float) -> None:
        await asyncio.sleep(delay + 0.05)
        if self.game and self.game.on_timeout(version):
            await self.after_change()

    async def handle(self, pid: str, data: dict) -> None:
        kind = data.get("type")
        if kind == "ping":
            await self._send(pid, {"type": "pong"})
        elif kind == "start_game":
            await self.start_game(pid)
        elif kind in ("bid", "fold", "vote"):
            if self.game is None:
                raise GameError("La partie n'a pas commencé.")
            if kind == "bid":
                self.game.bid(pid, data.get("amount"))
            elif kind == "fold":
                self.game.fold(pid)
            else:
                self.game.vote(pid, data.get("target"))
            await self.after_change()
        else:
            raise GameError("Commande inconnue.")

    async def leave(self, pid: str) -> None:
        if self.status == "lobby":
            self.remove_player(pid)
            if not self.players:
                self.close()
                registry.rooms.pop(self.code, None)
                return
            await self.broadcast_room()
        # en partie : le joueur reste dans la partie, juste déconnecté


class Registry:
    def __init__(self):
        self.rooms: dict[str, Room] = {}

    def new_code(self) -> str:
        while True:
            code = "".join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))
            if code not in self.rooms:
                return code

    def create(self, pseudo: str, settings: dict | None) -> tuple[Room, dict]:
        settings = validate_settings(settings)
        room = Room(self.new_code(), settings)
        player = room.add_player(pseudo)
        self.rooms[room.code] = room
        return room, player

    def get(self, code: str) -> Room:
        room = self.rooms.get((code or "").strip().upper())
        if room is None:
            raise GameError("Salon introuvable.")
        return room


registry = Registry()
