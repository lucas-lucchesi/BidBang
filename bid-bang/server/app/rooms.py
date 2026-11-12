"""Salons : joueurs, connexions WebSocket, chronomètres, diffusion de l'état."""
import asyncio
import random
import secrets
import time
from typing import Any

from .ai import debug, generator, limits
from .ai.base import AIProvider
from .errors import GameError
from . import criteria as criteria_mod
from .game import Game, preview_ai_cards, validate_settings

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans O/0/I/1
CODE_LENGTH = 6
MAX_PLAYERS = 4
MAX_PSEUDO = 16
REMATCH_KEYS = {"mode", "budget", "bid_timer", "item_count"}  # modifiables à la revanche
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
        self.banned: set[str] = set()  # pseudos exclus par l'hôte (en minuscules)
        self.status = "lobby"  # lobby | playing | finished
        self.game: Game | None = None
        # Partie `ai` : objets générés (validés) ; JAMAIS la clé API.
        self.ai_items: dict[str, dict] = {}
        self.ai_profile: dict | None = None  # objectif validé de la dernière génération
        self.ai_busy = False
        self.ai_count = 0
        self.ai_last = 0.0
        self._timer: asyncio.Task | None = None
        self._cleanup: asyncio.Task | None = None

    # ---------------------------------------------------------- joueurs
    def add_player(self, pseudo: str) -> dict:
        if self.status != "lobby":
            raise GameError("La partie a déjà commencé.")
        if len(self.players) >= self.max_players:
            raise GameError("Le salon est complet.")
        pseudo = clean_pseudo(pseudo)
        if pseudo.lower() in self.banned:
            raise GameError("Vous avez été exclu de ce salon.", 403)
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

    @property
    def max_players(self) -> int:
        return int(self.settings.get("max_players", MAX_PLAYERS))

    def is_host(self, pid: str) -> bool:
        return pid == self.host_id

    def room_state(self) -> dict:
        return {"code": self.code, "status": self.status, "host_id": self.host_id,
                "settings": self.settings, "max_players": self.max_players,
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
        if not self.settings.get("ready", True):
            raise GameError("L'hôte doit d'abord valider la sélection d'objets.")
        if self.ai_busy:
            raise GameError("Une génération IA est en cours.")
        # Les points des objets sont calculés et figés ici, à la création de la partie.
        self.game = Game([(p["id"], p["pseudo"]) for p in self.players.values()],
                         self.settings, pool=list(self.ai_items.values()))
        self.status = "playing"
        await self.broadcast_room()
        await self.after_change()

    # ------------------------------------------------------- partie IA
    def _require_ai_lobby(self, pid: str) -> None:
        if not self.is_host(pid):
            raise GameError("Seul l'hôte peut faire cela.", 403)
        if self.settings["creation_type"] != "ai":
            raise GameError("Ce salon n'est pas une partie avec IA.")
        if self.status != "lobby":
            raise GameError("La partie a déjà commencé.", 409)

    async def ai_generate(self, pid: str, provider: AIProvider, api_key: str) -> dict:
        """Génère des objets via le fournisseur. La clé reste dans cet appel (non stockée)."""
        self._require_ai_lobby(pid)
        if self.ai_busy:
            raise GameError("Une génération est déjà en cours.", 429)
        if self.ai_count >= limits.MAX_GENERATIONS_PER_ROOM:
            raise GameError("Nombre maximal de générations atteint pour ce salon.", 429)
        if time.monotonic() - self.ai_last < limits.MIN_INTERVAL_SECONDS:
            raise GameError("Patientez quelques secondes avant de relancer.", 429)
        sem = limits.global_slot()
        if sem.locked():
            raise GameError("Le service de génération est occupé, réessayez.", 429)
        self.ai_busy = True
        self.ai_count += 1
        self.ai_last = time.monotonic()
        try:
            async with sem:
                result = await generator.generate(
                    provider, api_key, self.settings["scenario"], self.settings["mode"],
                    self.settings["item_count"], taken_ids=_catalog_ids(),
                    players=self.max_players)
        finally:
            self.ai_busy = False
        if self.status != "lobby":  # la partie a démarré pendant l'appel
            raise GameError("La partie a déjà commencé.", 409)
        # remplace entièrement les anciennes propositions (jamais de fusion avec une génération précédente)
        self.ai_items = {i["id"]: i for i in result.new_items}
        self.ai_profile = result.profile
        debug.cards("salon : propositions enregistrées", list(self.ai_items.values()))
        # une nouvelle génération invalide l'ancienne sélection : l'hôte doit revalider
        self.settings = validate_settings(
            {**self.settings, "scenario": result.situation, "item_ids": []},
            extra_items=self.ai_items, require_selection=False)
        await self.broadcast_room()
        return {"situation": self._situation_view(), "profile": result.profile,
                "corrected": result.corrected,
                "items": preview_ai_cards(result.items),
                "generations_left": limits.MAX_GENERATIONS_PER_ROOM - self.ai_count}

    def _situation_view(self) -> dict:
        sc = self.settings["scenario"]
        return {**sc, "criteria": criteria_mod.with_labels(sc["criteria"])}

    async def set_selection(self, pid: str, item_ids: Any, new_criteria: Any = None) -> dict:
        """Valide la sélection de cartes (uniquement celles générées par l'IA). Renvoie les cartes
        choisies avec leurs points (attribués par l'IA)."""
        self._require_ai_lobby(pid)
        if self.ai_busy:
            raise GameError("Une génération est en cours.", 409)
        scenario = self.settings["scenario"]
        if new_criteria is not None:
            raise GameError("Une partie avec IA n'a pas de critères : l'IA attribue les points.", 400)
        self.settings = validate_settings(
            {**self.settings, "scenario": scenario, "item_ids": item_ids},
            extra_items=self.ai_items)
        await self.broadcast_room()
        chosen = [self.ai_items[i] for i in self.settings["item_ids"]]
        debug.cards("salon : sélection validée", chosen)
        return {"situation": self._situation_view(),
                "items": preview_ai_cards(chosen)}

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
        elif kind in ("bid", "fold"):
            if self.game is None:
                raise GameError("La partie n'a pas commencé.")
            version = self.game.version
            try:
                if kind == "bid":
                    self.game.bid(pid, data.get("amount"))
                else:
                    self.game.fold(pid)
            except GameError:
                if self.game.version != version:  # action tardive : l'échéance a clos l'étape
                    await self.after_change()
                raise
            await self.after_change()
        elif kind == "kick":
            await self.kick(pid, data.get("target"))
        elif kind == "rematch":
            await self.rematch(pid, data.get("settings"))
        else:
            raise GameError("Commande inconnue.")

    async def rematch(self, pid: str, changes: Any = None) -> None:
        """Revanche : l'hôte relance une partie dans le même salon, avec les mêmes joueurs,
        sans recréer de salon. Possible seulement quand la partie est terminée.

        Les réglages sont conservés ; `changes` peut modifier le mode d'enchères, le budget, le
        chrono et le nombre de cartes (validés comme à la création). Le salon revient à l'état
        d'attente : l'hôte peut encore exclure quelqu'un, puis lance la partie. Une partie
        classique retire de nouvelles cartes au hasard ; en partie personnalisée ou IA, la
        sélection validée est conservée (aucune génération n'est refaite, aucun appel IA).
        """
        if not self.is_host(pid):
            raise GameError("Seul l'hôte peut relancer une partie.", 403)
        if self.status != "finished":
            raise GameError("La partie n'est pas terminée.", 409)
        new_settings = self.settings
        if changes is not None:
            if not isinstance(changes, dict):
                raise GameError("Réglages invalides.")
            unknown = set(changes) - REMATCH_KEYS
            if unknown:
                raise GameError("Seuls le mode, le budget, le chrono et le nombre de cartes peuvent changer.")
            new_settings = validate_settings(
                {**self.settings, **changes}, extra_items=self.ai_items,
                require_selection=bool(self.settings.get("ready", True)))
        self.settings = new_settings
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self.game = None
        self.status = "lobby"
        await self.broadcast_room()
        for p in list(self.sockets):  # les écrans de résultats reviennent au salon d'attente
            await self._send(p, {"type": "rematch"})

    async def kick(self, pid: str, target: Any) -> None:
        """Exclut un joueur du salon d'attente (hôte seulement)."""
        if not self.is_host(pid):
            raise GameError("Seul l'hôte peut exclure un joueur.", 403)
        if self.status != "lobby":
            raise GameError("On ne peut exclure un joueur qu'avant le début de la partie.")
        if not isinstance(target, str) or target not in self.players:
            raise GameError("Joueur inconnu.")
        if target == pid:
            raise GameError("Vous ne pouvez pas vous exclure vous-même.")
        self.banned.add(self.players[target]["pseudo"].lower())
        ws = self.sockets.get(target)
        self.remove_player(target)  # son jeton devient invalide
        if ws is not None:
            try:
                await ws.send_json({"type": "kicked"})
                await ws.close(code=4403)
            except Exception:
                pass
        await self.broadcast_room()

    async def leave(self, pid: str) -> None:
        if self.status == "lobby":
            self.remove_player(pid)
            if not self.players:
                self.close()
                registry.rooms.pop(self.code, None)
                return
            await self.broadcast_room()
        # en partie : le joueur reste dans la partie, juste déconnecté


def _catalog_ids() -> set[str]:
    from .items import catalog_item_map
    return set(catalog_item_map())


class Registry:
    def __init__(self):
        self.rooms: dict[str, Room] = {}

    def new_code(self) -> str:
        while True:
            code = "".join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))
            if code not in self.rooms:
                return code

    def create(self, pseudo: str, settings: dict | None) -> tuple[Room, dict]:
        settings = validate_settings(settings, require_selection=False)
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
