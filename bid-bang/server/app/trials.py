"""Épreuves de Survie pour les parties personnalisées / IA.

Les épreuves sont des données structurées {id, name, description, stat, threshold} :
le texte de l'hôte n'est jamais interprété comme une règle. Le calcul (somme de la stat
des objets achetés contre le seuil, mis à l'échelle du nombre d'objets) reste dans game.py.
Les seuils sont donnés pour 6 objets, comme dans le catalogue.
"""
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, field_validator

from .items import STAT_KEYS, _clean

TRIAL_COUNT = 3
MIN_THRESHOLD = 4
MAX_THRESHOLD = 12
DEFAULT_PACK = "generique"

TRIAL_PACKS: dict[str, dict] = {
    "generique": {"name": "Générique", "trials": [
        {"name": "Épreuve de confort", "description": "Tenir dans de bonnes conditions.", "stat": "confort", "threshold": 9},
        {"name": "Épreuve de sécurité", "description": "Rester à l'abri des dangers.", "stat": "securite", "threshold": 8},
        {"name": "Épreuve d'utilité", "description": "Avoir le bon outil au bon moment.", "stat": "utilite", "threshold": 9},
    ]},
    "catastrophe": {"name": "Catastrophe", "trials": [
        {"name": "Mise à l'abri", "description": "Se protéger de la catastrophe.", "stat": "securite", "threshold": 9},
        {"name": "Soins et santé", "description": "Rester en bonne santé.", "stat": "sante", "threshold": 8},
        {"name": "Ressources", "description": "Tenir sur la durée avec le matériel.", "stat": "utilite", "threshold": 9},
    ]},
    "expedition": {"name": "Expédition", "trials": [
        {"name": "Nuit à la belle étoile", "description": "Dormir malgré les éléments.", "stat": "confort", "threshold": 8},
        {"name": "Forme physique", "description": "Garder la santé du groupe.", "stat": "sante", "threshold": 8},
        {"name": "Débrouillardise", "description": "Se sortir des imprévus.", "stat": "utilite", "threshold": 9},
    ]},
    "reception": {"name": "Réception", "trials": [
        {"name": "Effet « waouh »", "description": "Impressionner les invités.", "stat": "style", "threshold": 10},
        {"name": "Confort des invités", "description": "Que chacun se sente bien.", "stat": "confort", "threshold": 9},
        {"name": "Organisation", "description": "Que tout fonctionne.", "stat": "utilite", "threshold": 8},
    ]},
}


def pack_ids() -> list[str]:
    return list(TRIAL_PACKS)


def list_packs() -> list[dict]:
    return [{"id": k, "name": v["name"],
             "trials": [{"name": t["name"], "stat": t["stat"]} for t in v["trials"]]}
            for k, v in TRIAL_PACKS.items()]


def build_trials(raw_trials: list[dict]) -> list[dict]:
    """Ajoute un identifiant serveur (`epreuve_1`...) à une liste d'épreuves déjà validées."""
    return [{"id": f"epreuve_{n}", "name": t["name"], "description": t.get("description", ""),
             "stat": t["stat"], "threshold": t["threshold"]}
            for n, t in enumerate(raw_trials[:TRIAL_COUNT], start=1)]


def pack_trials(pack_id: str) -> list[dict]:
    return build_trials(TRIAL_PACKS[pack_id]["trials"])


class AITrial(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=140)
    stat: str
    threshold: StrictInt = Field(ge=MIN_THRESHOLD, le=MAX_THRESHOLD)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("vide")
        return v

    @field_validator("description")
    @classmethod
    def _description(cls, v: str) -> str:
        return _clean(v)

    @field_validator("stat")
    @classmethod
    def _stat(cls, v: str) -> str:
        if v not in STAT_KEYS:
            raise ValueError("stat inconnue")
        return v


def normalize_ai_trials(raw: object) -> list[dict] | None:
    """Épreuves IA valides (exactement TRIAL_COUNT, stats distinctes) ou None."""
    if not isinstance(raw, list):
        return None
    valid: list[dict] = []
    used: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            t = AITrial.model_validate(entry)
        except ValidationError:
            continue
        if t.stat in used:
            continue
        used.add(t.stat)
        valid.append({"name": t.name, "description": t.description, "stat": t.stat,
                      "threshold": t.threshold})
    if len(valid) < TRIAL_COUNT:
        return None
    return build_trials(valid)
