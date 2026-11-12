"""Types de création de partie : classic / custom / ai (indépendants du mode de jeu).

- classic : un lieu du catalogue (comportement historique).
- custom  : situation écrite par l'hôte + critères + sélection libre d'objets (tous lieux).
- ai      : situation + critères + objets proposés par une IA externe, puis validés.

Le texte de la situation est de la donnée affichée aux joueurs : il n'influence jamais
les règles de calcul. Seuls les critères structurés (criteria.py) comptent.
"""
import unicodedata

from . import criteria as criteria_mod
from .errors import GameError

CREATION_TYPES = ("classic", "custom", "ai")
SCENARIO_MIN = 5
SCENARIO_MAX = 300
AI_PROMPT_MAX = 600  # partie IA : situation + objets imposés avec leur prix
TITLE_MAX = 60
MAX_SELECTION = 80


def _clean_text(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    kept = "".join(ch for ch in raw
                   if ch in " \n" or not unicodedata.category(ch).startswith("C"))
    return " ".join(kept.split())


def derive_title(description: str) -> str:
    first = description.split(".")[0].split("!")[0].split("?")[0].strip() or description
    if len(first) > 50:
        first = first[:49].rstrip() + "…"
    return first[:TITLE_MAX]


DEFAULT_TEMPLATE = "polyvalent"


def clean_scenario(raw: object, maximum: int = SCENARIO_MAX, ai: bool = False) -> dict:
    """Valide la situation : {title, description, criteria}.

    Une simple chaîne est la description. Critères absents (anciennes configurations) :
    modèle `polyvalent` en partie personnalisée, liste vide en partie IA (les critères
    arrivent avec la génération). Critères présents : validés, au moins un nécessaire
    (sauf liste vide en partie IA, avant génération).
    """
    if isinstance(raw, str):
        raw = {"description": raw}
    if not isinstance(raw, dict):
        raise GameError("Écrivez une situation pour la partie.")
    description = _clean_text(raw.get("description"))
    if len(description) < SCENARIO_MIN:
        raise GameError(f"La situation doit contenir au moins {SCENARIO_MIN} caractères.")
    if len(description) > maximum:
        raise GameError(f"La situation est trop longue ({maximum} caractères maximum).")
    title = _clean_text(raw.get("title"))
    if len(title) > TITLE_MAX:
        raise GameError(f"Le titre est trop long ({TITLE_MAX} caractères maximum).")
    if "criteria" not in raw:
        crit = [] if ai else criteria_mod.get_template(DEFAULT_TEMPLATE)["criteria"]
        crit = criteria_mod.clean_criteria(crit, require_necessary=not ai)
    elif ai and raw["criteria"] == []:
        crit = []
    else:
        crit = criteria_mod.clean_criteria(raw["criteria"])
    return {"title": title or derive_title(description), "description": description,
            "criteria": crit}


def check_item_ids(raw: object, known: dict[str, dict]) -> list[str]:
    """Liste d'identifiants : textes uniques, connus. Ne contrôle pas la taille minimale."""
    if not isinstance(raw, list) or not all(isinstance(i, str) for i in raw):
        raise GameError("Sélection d'objets invalide.")
    if len(raw) > MAX_SELECTION:
        raise GameError(f"Trop d'objets sélectionnés ({MAX_SELECTION} maximum).")
    if len(set(raw)) != len(raw):
        raise GameError("Un objet est sélectionné plusieurs fois.")
    unknown = [i for i in raw if i not in known]
    if unknown:
        raise GameError("Objet inconnu dans la sélection.")
    return list(raw)


def check_selection_size(item_ids: list[str], item_count: int) -> None:
    if len(item_ids) < item_count:
        raise GameError(
            f"Sélection insuffisante : {len(item_ids)} objet(s) choisi(s), "
            f"il en faut au moins {item_count}.")
