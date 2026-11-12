"""Critères de situation : vocabulaire commun aux objets (`attributes`) et aux situations.

Le registre vit dans `data/criteria.json` : ajouter un critère = ajouter une ligne
{id, label} dans ce fichier, sans toucher au moteur. Les identifiants sont en ASCII
minuscule (`decoration`, jamais `décoration`) ; le libellé affiché est dans le registre.

Un critère de situation : {id, necessary: bool, importance: 1..5}. Un critère non
nécessaire a toujours une importance de 0 et ne rapporte rien.
"""
import json
from functools import lru_cache
from pathlib import Path

from .errors import GameError
from .textutil import slugify

CRITERIA_PATH = Path(__file__).resolve().parent.parent / "data" / "criteria.json"
ATTR_MIN, ATTR_MAX = 1, 5            # borne des caractéristiques d'un objet
IMPORTANCE_MIN, IMPORTANCE_MAX = 1, 5  # borne de l'importance d'un critère nécessaire


@lru_cache(maxsize=1)
def _load() -> dict:
    with CRITERIA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def registry() -> dict[str, str]:
    """id -> libellé."""
    return {c["id"]: c["label"] for c in _load()["criteria"]}


def list_criteria() -> list[dict]:
    return [dict(c) for c in _load()["criteria"]]


def label(criterion_id: str) -> str:
    return registry().get(criterion_id, criterion_id)


def templates() -> list[dict]:
    return [json.loads(json.dumps(t)) for t in _load()["templates"]]


def get_template(template_id: str) -> dict | None:
    return next((t for t in templates() if t["id"] == template_id), None)


def normalize_id(raw: object) -> str:
    """`Décoration` -> `decoration`. Renvoie "" si ce n'est pas un texte exploitable."""
    return slugify(raw) if isinstance(raw, str) else ""


def clean_criteria(raw: object, require_necessary: bool = True) -> list[dict]:
    """Valide une liste de critères de situation et la renvoie normalisée.

    Rejette : critère inconnu, doublon, importance hors 1..5 pour un critère nécessaire,
    `necessary` qui n'est pas un booléen, liste vide ou (si `require_necessary`) sans
    aucun critère nécessaire.
    """
    if not isinstance(raw, list) or not all(isinstance(c, dict) for c in raw):
        raise GameError("Critères de situation invalides.")
    known = registry()
    if len(raw) > len(known):
        raise GameError("Trop de critères.")
    out: list[dict] = []
    seen: set[str] = set()
    for entry in raw:
        cid = normalize_id(entry.get("id"))
        if cid not in known:
            raise GameError("Critère inconnu dans la situation.")
        if cid in seen:
            raise GameError("Un critère est présent plusieurs fois.")
        seen.add(cid)
        necessary = entry.get("necessary", False)
        if not isinstance(necessary, bool):
            raise GameError("Critère invalide : « nécessaire » doit être vrai ou faux.")
        if necessary:
            imp = entry.get("importance")
            if isinstance(imp, bool) or not isinstance(imp, int) \
                    or not IMPORTANCE_MIN <= imp <= IMPORTANCE_MAX:
                raise GameError(
                    f"L'importance d'un critère doit être comprise entre {IMPORTANCE_MIN} "
                    f"et {IMPORTANCE_MAX}.")
        else:
            imp = 0
        out.append({"id": cid, "necessary": necessary, "importance": imp})
    if require_necessary and not any(c["necessary"] for c in out):
        raise GameError("Choisissez au moins un critère nécessaire.")
    return out


def with_labels(criteria: list[dict]) -> list[dict]:
    """Critères enrichis du libellé, pour l'affichage."""
    return [{**c, "label": label(c["id"])} for c in criteria]
