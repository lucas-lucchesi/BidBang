"""Moteur de jeu : toutes les règles vivent ici (le serveur fait autorité).

Le moteur est synchrone et ne connaît ni réseau ni asyncio : la couche salons
programme les chronomètres et appelle `on_timeout(version)`.
"""
import random
import time
from typing import Callable

from . import catalog
from .errors import GameError

RARITY_BONUS = [0, 2, 4, 7]  # Construction seulement
RARITY_NAMES = ["Commun", "Rare", "Épique", "Légendaire"]
SYNERGY_POINTS = 3
VOTE_POINTS = 8
TRIAL_SUCCESS_POINTS = 18
TRIAL_PARTIAL_MAX = 9
VOTE_DURATION = 45
BASE_ITEM_COUNT = 6  # les seuils de survie sont donnés pour 6 objets

MODES = ("construction", "survie")
BUDGETS = (1200, 2200, 3500)
ITEM_COUNTS = (6, 8, 10)
BID_TIMERS = (10, 15, 20, 30)


def default_settings() -> dict:
    return {"mode": "construction", "theme_id": "cabane", "budget": 2200,
            "item_count": 8, "bid_timer": 15}


def validate_settings(raw: dict | None) -> dict:
    s = default_settings()
    s.update({k: v for k, v in (raw or {}).items() if k in s})
    if s["mode"] not in MODES:
        raise GameError("Mode de jeu inconnu.")
    if catalog.get_location(s["theme_id"]) is None:
        raise GameError("Lieu inconnu.")
    if s["budget"] not in BUDGETS:
        raise GameError("Budget invalide.")
    if s["item_count"] not in ITEM_COUNTS:
        raise GameError("Nombre d'objets invalide.")
    if s["bid_timer"] not in BID_TIMERS:
        raise GameError("Durée de chrono invalide.")
    return s


def min_step(price: int) -> int:
    """Pas minimal : 8 % du prix arrondi à la dizaine, 10 minimum."""
    return max(10, int(round(price * 0.08 / 10.0)) * 10)


def item_points(item: dict, mode: str) -> int:
    total = sum(item["stats"].values())
    if mode == "construction":
        total += RARITY_BONUS[item["rarity"]]
    return total


def synergy_points(items: list[dict]) -> int:
    counts: dict[str, int] = {}
    for it in items:
        for tag in set(it["tags"]):
            counts[tag] = counts.get(tag, 0) + 1
    return sum(SYNERGY_POINTS * (n - 1) for n in counts.values() if n > 1)


class Game:
    def __init__(self, players: list[tuple[str, str]], settings: dict,
                 rng: random.Random | None = None,
                 clock: Callable[[], float] = time.monotonic):
        if len(players) < 2:
            raise GameError("Il faut au moins 2 joueurs.")
        self.settings = validate_settings(settings)
        self.mode: str = self.settings["mode"]
        self.clock = clock
        self.rng = rng or random.Random()
        self.location = catalog.get_location(self.settings["theme_id"])
        pool = catalog.get_items(self.settings["theme_id"])
        self.items = self.rng.sample(pool, self.settings["item_count"])
        self.players: dict[str, dict] = {
            pid: {"id": pid, "pseudo": pseudo, "budget": self.settings["budget"],
                  "items": []}
            for pid, pseudo in players
        }
        self.order = [pid for pid, _ in players]
        self.phase = "auction"  # auction | voting | finished
        self.version = 0
        self.index = -1
        self.auction: dict | None = None
        self.last_result: dict | None = None
        self.results: list[dict] | None = None
        self.next_item()

    # ------------------------------------------------------------ enchères
    def _bump(self) -> None:
        self.version += 1

    def next_item(self) -> None:
        self.index += 1
        if self.index >= len(self.items):
            self.auction = None
            self.finish_auctions()
            return
        item = self.items[self.index]
        a = {"item": item, "price": item["price"], "step": min_step(item["price"]),
             "bid": None, "leader": None, "folded": set(), "deadline": None}
        for pid, p in self.players.items():
            if p["budget"] < item["price"]:
                a["folded"].add(pid)  # ne peut pas payer le prix de départ
        self.auction = a
        self._bump()
        if not self._active_challengers():
            self._resolve()
            return
        a["deadline"] = self.clock() + self.settings["bid_timer"]

    def required_bid(self) -> int:
        a = self.auction
        return a["price"] if a["bid"] is None else a["bid"] + a["step"]

    def _active_challengers(self) -> list[str]:
        """Joueurs encore en lice qui pourraient surenchérir (hors meneur)."""
        a = self.auction
        need = self.required_bid()
        return [pid for pid, p in self.players.items()
                if pid != a["leader"] and pid not in a["folded"] and p["budget"] >= need]

    def _require_auction(self) -> dict:
        if self.phase != "auction" or self.auction is None:
            raise GameError("Aucune enchère en cours.")
        return self.auction

    def bid(self, pid: str, amount) -> None:
        a = self._require_auction()
        if pid not in self.players:
            raise GameError("Joueur inconnu.")
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise GameError("Montant invalide.")
        if pid in a["folded"]:
            raise GameError("Vous vous êtes couché pour cet objet.")
        if pid == a["leader"]:
            raise GameError("Vous menez déjà cette enchère.")
        need = self.required_bid()
        if amount < need:
            raise GameError(f"La mise minimale est de {need} €.")
        if amount > self.players[pid]["budget"]:
            raise GameError("Budget insuffisant.")
        a["bid"], a["leader"] = amount, pid
        self._bump()
        if not self._active_challengers():
            self._resolve()
        else:
            a["deadline"] = self.clock() + self.settings["bid_timer"]

    def fold(self, pid: str) -> None:
        a = self._require_auction()
        if pid not in self.players:
            raise GameError("Joueur inconnu.")
        if pid == a["leader"]:
            raise GameError("Le meneur ne peut pas se coucher.")
        if pid in a["folded"]:
            raise GameError("Vous êtes déjà couché.")
        a["folded"].add(pid)
        self._bump()
        if not self._active_challengers():
            self._resolve()

    def _resolve(self) -> None:
        a = self.auction
        item = a["item"]
        if a["leader"] is not None:
            winner = self.players[a["leader"]]
            winner["budget"] -= a["bid"]
            winner["items"].append(item)
            self.last_result = {"item": item, "winner_id": a["leader"],
                                "winner": winner["pseudo"], "price": a["bid"]}
        else:
            self.last_result = {"item": item, "winner_id": None, "winner": None,
                                "price": None}
        self.next_item()

    def on_timeout(self, version: int) -> bool:
        """Appelé par le chronomètre ; ignoré si la version est périmée."""
        if version != self.version:
            return False
        if self.phase == "auction" and self.auction is not None:
            self._resolve()
            return True
        if self.phase == "voting":
            self.finish_voting()
            return True
        return False

    # ------------------------------------------------------- fin d'enchères
    def finish_auctions(self) -> None:
        self.finish()

    def finish(self) -> None:
        self.phase = "finished"
        self.auction = None
        self._bump()
        self.results = self.compute_results()

    # ------------------------------------------------------------- scores
    def trial_results(self, pid: str) -> list[dict]:
        if self.mode != "survie":
            return []
        scale = self.settings["item_count"] / BASE_ITEM_COUNT
        out = []
        for t in self.location["survival"]["trials"]:
            threshold = max(1, round(t["threshold"] * scale))
            value = sum(it["stats"][t["stat"]] for it in self.players[pid]["items"])
            ok = value >= threshold
            pts = TRIAL_SUCCESS_POINTS if ok else int(round(TRIAL_PARTIAL_MAX * value / threshold))
            out.append({"id": t["id"], "name": t["name"], "stat": t["stat"],
                        "value": value, "threshold": threshold, "success": ok,
                        "points": pts})
        return out

    def votes_received(self, pid: str) -> int:
        return 0

    def compute_results(self) -> list[dict]:
        rows = []
        for pid in self.order:
            p = self.players[pid]
            items_pts = sum(item_points(i, self.mode) for i in p["items"])
            syn = synergy_points(p["items"])
            trials = self.trial_results(pid)
            trial_pts = sum(t["points"] for t in trials)
            votes = self.votes_received(pid)
            vote_pts = votes * VOTE_POINTS
            rows.append({"player_id": pid, "pseudo": p["pseudo"], "budget": p["budget"],
                         "items_points": items_pts, "synergy_points": syn,
                         "trials": trials, "trial_points": trial_pts,
                         "votes": votes, "vote_points": vote_pts,
                         "score": items_pts + syn + trial_pts + vote_pts})
        rows.sort(key=lambda r: (-r["score"], -r["budget"]))
        rank, prev = 0, None
        for n, r in enumerate(rows, start=1):
            key = (r["score"], r["budget"])
            if key != prev:
                rank = n
            r["rank"], prev = rank, key
            r["winner"] = rank == 1
        return rows

    # ---------------------------------------------------------------- état
    def seconds_left(self) -> float | None:
        a = self.auction
        if self.phase == "auction" and a and a["deadline"] is not None:
            return max(0.0, a["deadline"] - self.clock())
        return None

    def deadline(self) -> float | None:
        a = self.auction
        if self.phase == "auction" and a:
            return a["deadline"]
        return None

    def snapshot(self, viewer_id: str | None = None) -> dict:
        a = self.auction
        auction = None
        if self.phase == "auction" and a:
            auction = {"item": a["item"], "start_price": a["price"], "step": a["step"],
                       "current_bid": a["bid"], "leader_id": a["leader"],
                       "required_bid": self.required_bid(),
                       "folded": sorted(a["folded"]),
                       "seconds_left": self.seconds_left()}
        players = []
        for pid in self.order:
            p = self.players[pid]
            players.append({"id": pid, "pseudo": p["pseudo"], "budget": p["budget"],
                            "items": p["items"],
                            "folded": bool(a and pid in a["folded"])})
        return {"phase": self.phase, "mode": self.mode,
                "settings": self.settings,
                "location": {"id": self.location["id"], "name": self.location["name"],
                             "description": self.location["description"]},
                "scenario": self.location["survival"] if self.mode == "survie" else None,
                "item_index": min(self.index + 1, len(self.items)),
                "item_total": len(self.items),
                "auction": auction, "players": players,
                "last_result": self.last_result, "results": self.results,
                "you": viewer_id}
