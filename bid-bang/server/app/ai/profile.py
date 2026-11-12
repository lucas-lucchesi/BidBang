"""Profil de génération : ce que la situation autorise comme cartes.

L'IA le déduit du scénario (dans la même requête structurée que les cartes) ; le serveur le
valide, puis l'applique à chaque carte. Il n'est pas propre au football : il décrit n'importe
quelle situation (équipe, casting, recrutement, survie, réception...).

    {"goal": "Composer un onze historique",
     "allowed_entity_types": ["football_player"],   # types de cartes admis (identifiants libres)
     "real_entities_only": true,                    # personnes/lieux réels uniquement
     "organization": "Olympique de Marseille",      # club, entreprise, univers... (facultatif)
     "required_roles": ["Gardien", "Défenseur", "Milieu", "Attaquant"],  # rôles à couvrir
     "allow_unrelated_items": false}                # false : aucune carte hors sujet

Limite : le serveur contrôle la cohérence du format, pas la véracité. « real_entities_only »
repose sur l'attestation de l'IA (`is_real`) ; une vérification factuelle stricte demanderait
une source de données externe (ex. base de joueurs), non branchée ici.
"""
from pydantic import (BaseModel, ConfigDict, Field, StrictBool, ValidationError,
                      field_validator)

from ..textutil import clean, slugify

MAX_TYPES = 6
MAX_ROLES = 12


class AIProfile(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    goal: str = Field(min_length=3, max_length=140)
    allowed_entity_types: list[str] = Field(min_length=1, max_length=MAX_TYPES)
    real_entities_only: StrictBool
    organization: str | None = Field(default=None, max_length=60)
    required_roles: list[str] = Field(default_factory=list, max_length=MAX_ROLES)
    allow_unrelated_items: StrictBool = False

    @field_validator("goal")
    @classmethod
    def _goal(cls, v: str) -> str:
        v = clean(v)
        if len(v) < 3:
            raise ValueError("objectif vide")
        return v

    @field_validator("organization")
    @classmethod
    def _org(cls, v: str | None) -> str | None:
        v = clean(v) if isinstance(v, str) else None
        return v or None

    @field_validator("allowed_entity_types")
    @classmethod
    def _types(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            slug = slugify(str(t))[:30]
            if not slug:
                raise ValueError("type vide")
            if slug not in out:
                out.append(slug)
        return out

    @field_validator("required_roles")
    @classmethod
    def _roles(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for r in v:
            r = clean(str(r))[:30]
            if not r:
                raise ValueError("rôle vide")
            if slugify(r) and r.casefold() not in {o.casefold() for o in out}:
                out.append(r)
        return out


def clean_profile(raw: object) -> dict | None:
    """Profil validé (dict) ou None s'il est absent ou invalide."""
    if not isinstance(raw, dict):
        return None
    try:
        return AIProfile.model_validate(raw).model_dump()
    except ValidationError:
        return None


def role_matches(role: str, category: str) -> bool:
    """« Défenseur central » couvre le rôle « Défenseur » (comparaison sans accent ni casse)."""
    a, b = slugify(role), slugify(category)
    return bool(a and b and (a == b or a in b or b in a))


def rejection(profile: dict, card: dict) -> str | None:
    """Raison pour laquelle une carte ne respecte pas le profil, ou None si elle est admissible."""
    if profile["allow_unrelated_items"]:
        return None
    if card.get("entity_type") not in profile["allowed_entity_types"]:
        return "type de carte non admis"
    if profile["real_entities_only"] and card.get("is_real") is not True:
        return "carte non réelle"
    roles = profile["required_roles"]
    if roles and not any(role_matches(r, str(card.get("category", ""))) for r in roles):
        return "rôle non prévu"
    return None


def missing_roles(profile: dict, cards: list[dict]) -> list[str]:
    """Rôles requis sans aucune carte valide."""
    return [r for r in profile["required_roles"]
            if not any(role_matches(r, str(c.get("category", ""))) for c in cards)]
