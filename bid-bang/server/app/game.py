"""Moteur de jeu : toutes les règles vivent ici (le serveur fait autorité).

Le moteur est synchrone et ne connaît ni réseau ni asyncio : la couche salons
programme les chronomètres et appelle `on_timeout(version)`.
"""
import random
import time
from typing import Callable

from . import catalog, creation, items as items_mod, trials as trials_mod
from .errors import GameError

RARITY_BONUS = [0, 2, 4, 7]  # Construction seulement
RARITY_NAMES = ["Commun", "Rare", "Épique", "Légendaire"]
OPENING_MIN = 10  # mise d'ouverture libre, à partir de ce minimum
SYNERGY_POINTS = 3
VOTE_POINTS = 8
TRIAL_SUCCESS_POINTS = 18
TRIAL_PARTIAL_MAX = 9
VOTE_DURATION = 45
BASE_ITEM_COUNT = 6  # les seuils de survie sont donnés pour 6 objets

MODES = ("construction", "survie", "aveugle")
BUILDING_MODES = ("construction", "aveugle")  # mêmes règles de score (rareté, votes)
BUDGETS = (1200, 2200, 3500)
ITEM_COUNTS = (6, 8, 10)
BID_TIMERS = (10, 15, 20, 30)
PLAYER_COUNTS = (2, 3, 4)


def default_settings() -> dict:
    return {"creation_type": "classic", "mode": "construction", "theme_id": "cabane",
            "budget": 2200, "item_count": 8, "bid_timer": 15, "max_players": 4}


def validate_settings(raw: dict | None, extra_items: dict[str, dict] | None = None,
                      require_selection: bool = True) -> dict:
    """Valide les réglages d'une partie.

    `extra_items` : objets hors catalogue (générés par l'IA) autorisés dans la sélection.
    `require_selection` : False à la création d'un salon `ai` (la sélection vient après).
    Sans `creation_type`, la partie est classique (anciennes configurations).
    """
    raw = raw or {}
    ctype = raw.get("creation_type", "classic")
    if ctype not in creation.CREATION_TYPES:
        raise GameError("Type de partie inconnu.")
    s = default_settings()
    s.update({k: v for k, v in raw.items() if k in s})
    s["creation_type"] = ctype
    if s["mode"] not in MODES:
        raise GameError("Mode de jeu inconnu.")
    if s["budget"] not in BUDGETS:
        raise GameError("Budget invalide.")
    if s["item_count"] not in ITEM_COUNTS:
        raise GameError("Nombre d'objets invalide.")
    if s["bid_timer"] not in BID_TIMERS:
        raise GameError("Durée de chrono invalide.")
    if s["max_players"] not in PLAYER_COUNTS or isinstance(s["max_players"], bool):
        raise GameError("Nombre de joueurs invalide.")
    if ctype == "classic":
        if catalog.get_location(s["theme_id"]) is None:
            raise GameError("Lieu inconnu.")
        return s
    # custom / ai : scénario + sélection d'objets
    s["theme_id"] = ctype
    s["scenario"] = creation.clean_scenario(
        raw.get("scenario"), creation.AI_PROMPT_MAX if ctype == "ai" else creation.SCENARIO_MAX)
    pack = raw.get("trial_pack", trials_mod.DEFAULT_PACK)
    if pack not in trials_mod.TRIAL_PACKS:
        raise GameError("Série d'épreuves inconnue.")
    s["trial_pack"] = pack
    known = items_mod.catalog_item_map()
    if ctype == "ai":
        known.update(extra_items or {})
    ids = raw.get("item_ids", [])
    if ctype == "custom" or ids or require_selection:
        s["item_ids"] = creation.check_item_ids(ids, known)
        creation.check_selection_size(s["item_ids"], s["item_count"])
        s["ready"] = True
    else:
        s["item_ids"] = []
        s["ready"] = False
    return s


def min_step(price: int) -> int:
    """Pas minimal : 8 % du prix arrondi à la dizaine, 10 minimum."""
    return max(10, int(round(price * 0.08 / 10.0)) * 10)


def item_points(item: dict, mode: str) -> int:
    total = sum(item["stats"].values())
    if mode in BUILDING_MODES:
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
                 clock: Callable[[], float] = time.monotonic,
                 pool: list[dict] | None = None,
                 trials: list[dict] | None = None):
        """`pool` : objets hors catalogue (IA) ; `trials` : épreuves de Survie validées (IA)."""
        if len(players) < 2:
            raise GameError("Il faut au moins 2 joueurs.")
        extra = {i["id"]: i for i in pool or []}
        self.settings = validate_settings(settings, extra_items=extra)
        self.creation_type: str = self.settings["creation_type"]
        self.mode: str = self.settings["mode"]
        self.blind: bool = self.mode == "aveugle"
        self.clock = clock
        self.rng = rng or random.Random()
        self.situation: dict | None = None
        if self.creation_type == "classic":
            self.location = catalog.get_location(self.settings["theme_id"])
            self.trials = self.location["survival"]["trials"]
            self.survival = self.location["survival"]
            self.items = self.rng.sample(catalog.get_items(self.settings["theme_id"]),
                                         self.settings["item_count"])
        else:
            if not self.settings["ready"]:
                raise GameError("La sélection d'objets n'est pas validée.")
            sc = self.settings["scenario"]
            self.situation = sc
            self.location = {"id": self.creation_type, "name": sc["title"],
                             "description": sc["description"]}
            by_id = {**items_mod.catalog_item_map(), **extra}
            # uniquement la sélection validée, dans un ordre aléatoire
            selected = [by_id[i] for i in self.settings["item_ids"]]
            self.items = self.rng.sample(selected, self.settings["item_count"])
            self.trials = trials or trials_mod.pack_trials(self.settings["trial_pack"])
            self.survival = {"title": sc["title"], "text": sc["description"],
                             "trials": self.trials}
        self.players: dict[str, dict] = {
            pid: {"id": pid, "pseudo": pseudo, "budget": self.settings["budget"],
                  "items": [], "purchases": []}
            for pid, pseudo in players
        }
        self.order = [pid for pid, _ in players]
        self.phase = "auction"  # auction | voting | finished
        self.version = 0
        self.index = -1
        self.auction: dict | None = None
        self.last_result: dict | None = None
        self.results: list[dict] | None = None
        self.votes: dict[str, str] = {}
        self.vote_deadline: float | None = None
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
             "bid": None, "leader": None, "folded": set(), "deadline": None,
             "sealed": {}}  # enchère à l'aveugle : pid -> mise secrète (0 = passe), dans l'ordre d'envoi
        for pid, p in self.players.items():
            if p["budget"] < OPENING_MIN:
                a["folded"].add(pid)  # ne peut pas payer la mise minimale
                if self.blind:
                    a["sealed"][pid] = 0
        self.auction = a
        self._bump()
        if self.blind:
            if len(a["sealed"]) == len(self.players):
                self._resolve()
                return
        elif not self._active_challengers():
            self._resolve()
            return
        a["deadline"] = self.clock() + self.settings["bid_timer"]

    def required_bid(self) -> int:
        a = self.auction
        return OPENING_MIN if a["bid"] is None else a["bid"] + a["step"]

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

    def _reject_if_late(self) -> None:
        """Contrôle basé sur l'horloge du serveur : une action reçue après l'échéance est
        refusée, même si le chronomètre asyncio n'a pas encore tiré. L'enchère est alors
        clôturée sur-le-champ (la couche salon diffuse le nouvel état)."""
        a = self.auction
        if self.phase == "auction" and a is not None and a["deadline"] is not None \
                and self.clock() >= a["deadline"]:
            self._resolve()
            raise GameError("Temps écoulé : l'enchère est terminée.")

    def bid(self, pid: str, amount) -> None:
        a = self._require_auction()
        self._reject_if_late()
        if pid not in self.players:
            raise GameError("Joueur inconnu.")
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise GameError("Montant invalide.")
        if self.blind:
            return self._blind_bid(pid, amount)
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

    # ------------------------------------------------- enchère à l'aveugle
    def _blind_bid(self, pid: str, amount) -> None:
        a = self.auction
        if pid in a["sealed"]:
            raise GameError("Vous avez déjà joué pour cet objet.")
        if amount < OPENING_MIN:
            raise GameError(f"La mise minimale est de {OPENING_MIN} €.")
        if amount > self.players[pid]["budget"]:
            raise GameError("Budget insuffisant.")
        a["sealed"][pid] = amount
        self._after_seal()

    def _blind_pass(self, pid: str) -> None:
        a = self.auction
        if pid in a["sealed"]:
            raise GameError("Vous avez déjà joué pour cet objet.")
        a["sealed"][pid] = 0
        self._after_seal()

    def _after_seal(self) -> None:
        self._bump()
        if len(self.auction["sealed"]) == len(self.players):
            self._resolve()

    def _resolve_blind(self) -> None:
        a = self.auction
        item = a["item"]
        best_pid, best = None, 0
        for pid, amount in a["sealed"].items():  # ordre d'envoi : à égalité, le premier gagne
            if amount > best:
                best_pid, best = pid, amount
        bids = [{"player_id": pid, "pseudo": self.players[pid]["pseudo"],
                 "amount": a["sealed"].get(pid, 0)} for pid in self.order]
        if best_pid is not None:
            winner = self.players[best_pid]
            winner["budget"] -= best
            winner["items"].append(item)
            winner["purchases"].append({"item": item, "price": best})
            self.last_result = {"item": item, "winner_id": best_pid,
                                "winner": winner["pseudo"], "price": best, "bids": bids}
        else:
            self.last_result = {"item": item, "winner_id": None, "winner": None,
                                "price": None, "bids": bids}
        self.next_item()

    def fold(self, pid: str) -> None:
        a = self._require_auction()
        self._reject_if_late()
        if pid not in self.players:
            raise GameError("Joueur inconnu.")
        if self.blind:
            return self._blind_pass(pid)
        if pid == a["leader"]:
            raise GameError("Le meneur ne peut pas se coucher.")
        if pid in a["folded"]:
            raise GameError("Vous êtes déjà couché.")
        a["folded"].add(pid)
        self._bump()
        if not self._active_challengers():
            self._resolve()

    def _resolve(self) -> None:
        if self.blind:
            return self._resolve_blind()
        a = self.auction
        item = a["item"]
        if a["leader"] is not None:
            winner = self.players[a["leader"]]
            winner["budget"] -= a["bid"]
            winner["items"].append(item)
            winner["purchases"].append({"item": item, "price": a["bid"]})
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
        if self.mode in BUILDING_MODES and len(self.players) >= 3:
            self.phase = "voting"
            self.vote_deadline = self.clock() + VOTE_DURATION
            self._bump()
        else:
            self.finish()

    # --------------------------------------------------------------- votes
    def vote(self, pid: str, target) -> None:
        if self.phase != "voting":
            raise GameError("Le vote n'est pas ouvert.")
        if pid not in self.players:
            raise GameError("Joueur inconnu.")
        if self.vote_deadline is not None and self.clock() >= self.vote_deadline:
            self.finish_voting()
            raise GameError("Temps écoulé : le vote est terminé.")
        if target not in self.players:
            raise GameError("Joueur ciblé inconnu.")
        if target == pid:
            raise GameError("Vous ne pouvez pas voter pour vous-même.")
        self.votes[pid] = target
        self._bump()
        if len(self.votes) == len(self.players):
            self.finish_voting()

    def finish_voting(self) -> None:
        self.vote_deadline = None
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
        for t in self.trials:
            threshold = max(1, round(t["threshold"] * scale))
            value = sum(it["stats"][t["stat"]] for it in self.players[pid]["items"])
            ok = value >= threshold
            pts = TRIAL_SUCCESS_POINTS if ok else int(round(TRIAL_PARTIAL_MAX * value / threshold))
            out.append({"id": t["id"], "name": t["name"], "stat": t["stat"],
                        "value": value, "threshold": threshold, "success": ok,
                        "points": pts})
        return out

    def votes_received(self, pid: str) -> int:
        return sum(1 for t in self.votes.values() if t == pid)

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
                         "purchases": p["purchases"],
                         "spent": sum(x["price"] for x in p["purchases"]),
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
        if self.phase == "voting":
            return self.vote_deadline
        return None

    def snapshot(self, viewer_id: str | None = None) -> dict:
        a = self.auction
        auction = None
        if self.phase == "auction" and a:
            auction = {"item": a["item"], "start_price": a["price"],
                       "opening_min": OPENING_MIN, "step": a["step"],
                       "current_bid": a["bid"], "leader_id": a["leader"],
                       "required_bid": self.required_bid(),
                       "folded": sorted(a["folded"]),
                       "seconds_left": self.seconds_left(),
                       "blind": self.blind,
                       "submitted": sorted(a["sealed"]) if self.blind else [],
                       "your_bid": a["sealed"].get(viewer_id) if self.blind else None}
        vote = None
        if self.phase == "voting":
            vote = {"seconds_left": max(0.0, self.vote_deadline - self.clock()),
                    "voted_ids": sorted(self.votes),
                    "your_vote": self.votes.get(viewer_id)}
        players = []
        for pid in self.order:
            p = self.players[pid]
            players.append({"id": pid, "pseudo": p["pseudo"], "budget": p["budget"],
                            "items": p["items"], "purchases": p["purchases"],
                            "folded": bool(a and pid in a["folded"])})
        return {"phase": self.phase, "mode": self.mode,
                "creation_type": self.creation_type, "situation": self.situation,
                "settings": self.settings,
                "location": {"id": self.location["id"], "name": self.location["name"],
                             "description": self.location["description"]},
                "scenario": self.survival if self.mode == "survie" else None,
                "item_index": min(self.index + 1, len(self.items)),
                "item_total": len(self.items),
                "auction": auction, "vote": vote, "players": players,
                "last_result": self.last_result, "results": self.results,
                "you": viewer_id}
