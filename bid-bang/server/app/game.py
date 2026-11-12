"""Moteur de jeu : toutes les règles vivent ici (le serveur fait autorité).

Le moteur est synchrone et ne connaît ni réseau ni asyncio : la couche salons
programme les chronomètres et appelle `on_timeout(version)`.

Score final = somme des points des objets remportés. Les points de chaque objet sont
calculés une seule fois, au lancement, pour la situation de la partie (scoring.py), puis
figés dans une copie de l'objet : ni les autres joueurs, ni les achats, ni une modification
du catalogue ne les changent. Aucun bonus de rareté, synergie, vote ou épreuve.
"""
import random
import time
from typing import Callable

from . import catalog, creation, criteria as criteria_mod, items as items_mod, scoring
from .errors import GameError

RARITY_NAMES = ["Commun", "Rare", "Épique", "Légendaire"]
OPENING_MIN = 10  # mise d'ouverture libre, à partir de ce minimum

MODES = ("normal", "aveugle")
# Anciens modes (salons et réglages existants) : un seul calcul de victoire pour tous.
LEGACY_MODES = {"construction": "normal", "survie": "normal"}
BUDGETS = (1200, 2200, 3500)
MIN_ITEM_COUNT, MAX_ITEM_COUNT = 6, 20  # nombre de cartes mises aux enchères, au choix de l'hôte
BID_TIMERS = (10, 15, 20, 30)
PLAYER_COUNTS = (2, 3, 4)


def default_settings() -> dict:
    return {"creation_type": "classic", "mode": "normal", "theme_id": "cabane",
            "budget": 2200, "item_count": 8, "bid_timer": 15, "max_players": 4}


def normalize_mode(mode: object) -> str:
    """`construction` et `survie` (anciens modes) deviennent `normal` ; inconnu : erreur."""
    if isinstance(mode, str):
        mode = LEGACY_MODES.get(mode, mode)
        if mode in MODES:
            return mode
    raise GameError("Mode de jeu inconnu.")


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
    s["mode"] = normalize_mode(s["mode"])
    if s["budget"] not in BUDGETS:
        raise GameError("Budget invalide.")
    n = s["item_count"]
    if isinstance(n, bool) or not isinstance(n, int) or not MIN_ITEM_COUNT <= n <= MAX_ITEM_COUNT:
        raise GameError(f"Le nombre de cartes doit être compris entre {MIN_ITEM_COUNT} et {MAX_ITEM_COUNT}.")
    if s["bid_timer"] not in BID_TIMERS:
        raise GameError("Durée de chrono invalide.")
    if s["max_players"] not in PLAYER_COUNTS or isinstance(s["max_players"], bool):
        raise GameError("Nombre de joueurs invalide.")
    if ctype == "classic":
        if catalog.get_location(s["theme_id"]) is None:
            raise GameError("Lieu inconnu.")
        available = len(catalog.get_items(s["theme_id"]))
        if s["item_count"] > available:
            raise GameError(f"Ce lieu propose au plus {available} objets.")
        return s
    # custom / ai : situation (critères) + sélection d'objets
    s["theme_id"] = ctype
    s["scenario"] = creation.clean_scenario(
        raw.get("scenario"), creation.AI_PROMPT_MAX if ctype == "ai" else creation.SCENARIO_MAX,
        ai=ctype == "ai")
    # partie IA : uniquement les cartes générées (leurs points viennent de l'IA)
    known = dict(extra_items or {}) if ctype == "ai" else items_mod.catalog_item_map()
    ids = raw.get("item_ids", [])
    if ctype == "custom" or ids or require_selection:
        s["item_ids"] = creation.check_item_ids(ids, known)
        creation.check_selection_size(s["item_ids"], s["item_count"])
        if ctype == "custom" and not any(c["necessary"] for c in s["scenario"]["criteria"]):
            raise GameError("Choisissez au moins un critère nécessaire.")
        s["ready"] = True
    else:
        s["item_ids"] = []
        s["ready"] = False
    return s


def situation_of(settings: dict) -> dict:
    """Situation d'une partie : {title, description, criteria}. Classique : celle du lieu."""
    if settings["creation_type"] == "classic":
        loc = catalog.get_location(settings["theme_id"])
        sit = loc["situation"]
        return {"title": sit["title"], "description": sit["description"],
                "criteria": criteria_mod.clean_criteria(loc["criteria"])}
    sc = settings["scenario"]
    return {"title": sc["title"], "description": sc["description"],
            "criteria": [dict(c) for c in sc["criteria"]]}


def preview_points(situation_criteria: list[dict], items: list[dict]) -> list[dict]:
    """Objets avec leurs points pour une situation (aperçu avant la partie, sans rien figer)."""
    return scoring.freeze_items(items, situation_criteria)


def preview_ai_cards(cards: list[dict]) -> list[dict]:
    """Cartes d'une partie IA avec les points attribués par l'IA (aperçu, rien n'est figé)."""
    return [scoring.freeze_ai_card(c) for c in cards]


def min_step(price: int) -> int:
    """Pas minimal : 8 % du prix estimé arrondi à la dizaine, 10 minimum."""
    return max(10, int(round(price * 0.08 / 10.0)) * 10)


def purchase_row(purchase: dict) -> dict:
    """Achat enrichi : `item.price` reste l'estimation, `purchase_price` ce qui a été payé,
    `savings` = estimation - prix payé (négatif : surcoût)."""
    return {"item": purchase["item"], "purchase_price": purchase["purchase_price"],
            "savings": purchase["item"]["price"] - purchase["purchase_price"]}


class Game:
    def __init__(self, players: list[tuple[str, str]], settings: dict,
                 rng: random.Random | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 pool: list[dict] | None = None):
        """`pool` : objets hors catalogue (IA) autorisés dans la sélection."""
        if len(players) < 2:
            raise GameError("Il faut au moins 2 joueurs.")
        extra = {i["id"]: i for i in pool or []}
        self.settings = validate_settings(settings, extra_items=extra)
        self.creation_type: str = self.settings["creation_type"]
        self.mode: str = self.settings["mode"]
        self.blind: bool = self.mode == "aveugle"
        self.clock = clock
        self.rng = rng or random.Random()
        self.situation: dict = situation_of(self.settings)
        if self.creation_type == "classic":
            self.location = catalog.get_location(self.settings["theme_id"])
            drawn = [items_mod.catalog_item(i) for i in self.rng.sample(
                catalog.get_items(self.settings["theme_id"]), self.settings["item_count"])]
        else:
            if not self.settings["ready"]:
                raise GameError("La sélection d'objets n'est pas validée.")
            self.location = {"id": self.creation_type, "name": self.situation["title"],
                             "description": self.situation["description"]}
            by_id = extra if self.creation_type == "ai" else {**items_mod.catalog_item_map(), **extra}
            # uniquement la sélection validée, dans un ordre aléatoire
            selected = [by_id[i] for i in self.settings["item_ids"]]
            drawn = self.rng.sample(selected, self.settings["item_count"])
        # Points figés : copies indépendantes, calculées une seule fois pour tout le monde.
        if self.creation_type == "ai":
            self.items = [scoring.freeze_ai_card(c) for c in drawn]  # points donnés par l'IA
        else:
            self.items = scoring.freeze_items(drawn, self.situation["criteria"])
        self.players: dict[str, dict] = {
            pid: {"id": pid, "pseudo": pseudo, "budget": self.settings["budget"],
                  "items": [], "purchases": []}
            for pid, pseudo in players
        }
        self.order = [pid for pid, _ in players]
        self.phase = "auction"  # auction | finished
        self.version = 0
        self.index = -1
        self.auction: dict | None = None
        self.last_result: dict | None = None
        self.results: list[dict] | None = None
        self.bargains: list[dict] | None = None
        self.awards: dict | None = None
        self.next_item()

    # ------------------------------------------------------------ enchères
    def _bump(self) -> None:
        self.version += 1

    def next_item(self) -> None:
        self.index += 1
        if self.index >= len(self.items):
            self.auction = None
            self.finish()
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
            winner["purchases"].append({"item": item, "purchase_price": best})
            self.last_result = {"item": item, "winner_id": best_pid,
                                "winner": winner["pseudo"], "purchase_price": best, "bids": bids}
        else:
            self.last_result = {"item": item, "winner_id": None, "winner": None,
                                "purchase_price": None, "bids": bids}
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
            winner["purchases"].append({"item": item, "purchase_price": a["bid"]})
            self.last_result = {"item": item, "winner_id": a["leader"],
                                "winner": winner["pseudo"],
                                "purchase_price": a["bid"]}
        else:
            self.last_result = {"item": item, "winner_id": None, "winner": None,
                                "purchase_price": None}
        self.next_item()

    def on_timeout(self, version: int) -> bool:
        """Appelé par le chronomètre ; ignoré si la version est périmée."""
        if version != self.version:
            return False
        if self.phase == "auction" and self.auction is not None:
            self._resolve()
            return True
        return False

    # -------------------------------------------------------------- fin de partie
    def finish(self) -> None:
        self.phase = "finished"
        self.auction = None
        self._bump()
        self.results = self.compute_results()
        self.bargains = self.compute_bargains(self.results)
        self.awards = self.compute_awards(self.results)

    # ------------------------------------------------------------- scores
    def compute_results(self) -> list[dict]:
        """Classement : points décroissants, puis budget restant décroissant ; égalité
        parfaite = même rang (co-vainqueurs possibles). Rien d'autre n'entre dans le score."""
        rows = []
        for pid in self.order:
            p = self.players[pid]
            purchases = [purchase_row(pu) for pu in p["purchases"]]
            estimated = sum(pu["item"]["price"] for pu in purchases)
            spent = sum(pu["purchase_price"] for pu in purchases)
            rows.append({"player_id": pid, "pseudo": p["pseudo"], "budget": p["budget"],
                         "score": sum(pu["item"]["points"] for pu in purchases),
                         "items_count": len(purchases), "purchases": purchases,
                         "estimated_value": estimated, "total_spent": spent,
                         "savings": estimated - spent})
        rows.sort(key=lambda r: (-r["score"], -r["budget"]))
        rank, prev = 0, None
        for n, r in enumerate(rows, start=1):
            key = (r["score"], r["budget"])
            if key != prev:
                rank = n
            r["rank"], prev = rank, key
            r["winner"] = rank == 1
        return rows

    @staticmethod
    def compute_bargains(results: list[dict]) -> list[dict]:
        """Classement des bonnes affaires (informatif) : économie totale décroissante.
        Les joueurs sans achat sont en fin de liste. Ne modifie jamais le classement principal."""
        order = sorted(results, key=lambda r: (r["items_count"] == 0, -r["savings"]))
        out, rank, prev = [], 0, None
        for n, r in enumerate(order, start=1):
            key = (r["items_count"] == 0, r["savings"])
            if key != prev:
                rank = n
            prev = key
            out.append({"rank": rank, "player_id": r["player_id"], "pseudo": r["pseudo"],
                        "savings": r["savings"], "items_count": r["items_count"]})
        return out

    @staticmethod
    def compute_awards(results: list[dict]) -> dict:
        """Distinctions informatives (jamais le gagnant). Un joueur sans achat n'en reçoit
        aucune ; en cas d'égalité, le mieux classé au classement principal."""
        buyers = [r for r in results if r["items_count"] > 0]
        awards: dict = {"best_bidder": None, "best_deal": None,
                        "most_valuable": None, "most_useful": None}

        def top(key):
            best = None
            for r in buyers:  # `results` est déjà trié : le premier l'emporte à égalité
                if best is None or key(r) > key(best):
                    best = r
            return best

        b = top(lambda r: r["savings"])
        if b and b["savings"] > 0:
            awards["best_bidder"] = {"player_id": b["player_id"], "pseudo": b["pseudo"],
                                     "value": b["savings"]}
        deal = None
        for r in buyers:
            for pu in r["purchases"]:
                if deal is None or pu["savings"] > deal[1]["savings"]:
                    deal = (r, pu)
        if deal and deal[1]["savings"] > 0:
            r, pu = deal
            awards["best_deal"] = {"player_id": r["player_id"], "pseudo": r["pseudo"],
                                   "value": pu["savings"], "item": pu["item"],
                                   "purchase_price": pu["purchase_price"]}
        v = top(lambda r: r["estimated_value"])
        if v:
            awards["most_valuable"] = {"player_id": v["player_id"], "pseudo": v["pseudo"],
                                       "value": v["estimated_value"]}
        u = top(lambda r: r["score"])
        if u and u["score"] > 0:
            awards["most_useful"] = {"player_id": u["player_id"], "pseudo": u["pseudo"],
                                     "value": u["score"]}
        return awards

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
            auction = {"item": a["item"], "start_price": a["price"],
                       "opening_min": OPENING_MIN, "step": a["step"],
                       "current_bid": a["bid"], "leader_id": a["leader"],
                       "required_bid": self.required_bid(),
                       "folded": sorted(a["folded"]),
                       "seconds_left": self.seconds_left(),
                       "blind": self.blind,
                       "submitted": sorted(a["sealed"]) if self.blind else [],
                       "your_bid": a["sealed"].get(viewer_id) if self.blind else None}
        players = []
        for pid in self.order:
            p = self.players[pid]
            players.append({"id": pid, "pseudo": p["pseudo"], "budget": p["budget"],
                            "items": p["items"],
                            "purchases": [purchase_row(pu) for pu in p["purchases"]],
                            "folded": bool(a and pid in a["folded"])})
        return {"phase": self.phase, "mode": self.mode,
                "creation_type": self.creation_type,
                "situation": {**self.situation,
                              "criteria": criteria_mod.with_labels(self.situation["criteria"])},
                "settings": self.settings,
                "location": {"id": self.location["id"], "name": self.location["name"],
                             "description": self.location["description"]},
                "item_index": min(self.index + 1, len(self.items)),
                "item_total": len(self.items),
                "auction": auction, "players": players,
                "last_result": self.last_result, "results": self.results,
                "bargains": self.bargains, "awards": self.awards,
                "you": viewer_id}
