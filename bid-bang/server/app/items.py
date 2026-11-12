"""Format commun des objets (catalogue, sélection manuelle, génération IA).

Un objet « commun » est un dict JSON :
    {id, name, description, category, icon, price, rarity, base_points,
     attributes{critère: 1..5}, image, source}
- `price` : valeur ESTIMÉE (jamais remplacée par le prix d'achat) ;
- `attributes` : ce que l'objet apporte, avec les identifiants de `criteria.py` ; une
  caractéristique absente n'est pas stockée ;
- `base_points` : petit complément de points, indépendant de la situation (0..50) ;
- `image` : chemin d'illustration ou null ; `source` : `catalog` ou `ai`.
Les points d'une partie (`points`) sont ajoutés par `scoring.freeze_items` au lancement.

Une carte venant de l'IA (objet, joueur, métier, personnalité...) passe par `AIItem` /
`normalize_ai_item` : aucune valeur n'est reprise telle quelle, l'identifiant est généré par le
serveur. Elle porte déjà ses `points` (donnés par l'IA, 1 à 100) et n'a pas de caractéristiques.
"""
import re

from pydantic import (BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError,
                      field_validator)

from . import catalog, criteria
from .textutil import clean as _clean
from .textutil import slugify

ATTR_MAX = criteria.ATTR_MAX
BASE_POINTS_MAX = 50
MAX_ATTRIBUTES = 6
MAX_NAME = 40
MAX_DESCRIPTION = 140
MAX_CATEGORY = 30
DEFAULT_ICON = "box"
ID_RE = re.compile(r"^[a-z0-9_]{1,48}$")
MIN_PRICE, MAX_PRICE = 20, 600

__all__ = ["slugify", "_clean"]  # réexportés pour compatibilité


def compute_price(points: int, rarity: int) -> int:
    """Prix estimé de repli, calculé par le serveur quand l'IA n'en donne pas un valide."""
    raw = points * 4 + (0, 60, 120, 180)[rarity]
    return max(MIN_PRICE, min(MAX_PRICE, int(round(raw / 10.0)) * 10))


def category_of(attributes: dict[str, int]) -> str:
    """Caractéristique la plus forte (la première en cas d'égalité), sinon `divers`."""
    return max(attributes, key=lambda k: attributes[k]) if attributes else "divers"


# ------------------------------------------------------------- catalogue
def catalog_item(raw: dict) -> dict:
    """Objet du catalogue au format commun (copie indépendante)."""
    item = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
            for k, v in raw.items()}
    item.setdefault("description", "")
    item.setdefault("image", None)
    item["source"] = "catalog"
    return item


def catalog_items() -> list[dict]:
    return [catalog_item(i) for i in catalog.load_catalog()["items"]]


def catalog_item_map() -> dict[str, dict]:
    return {i["id"]: i for i in catalog_items()}


def locations_summary() -> list[dict]:
    return catalog.list_locations()


# ------------------------------------------------------------------ IA
POINTS_MIN, POINTS_MAX = 1, 100


class AIItem(BaseModel):
    """Carte proposée par l'IA (objet, joueur, métier, personnalité, personnage...) : tout champ
    hors schéma est ignoré, rien n'est supposé valide. L'IA attribue les points elle-même, dans
    les bornes ; le serveur les valide, les fige au lancement et calcule le classement."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=MAX_NAME)
    description: str = Field(default="", max_length=MAX_DESCRIPTION)
    category: str = Field(default="", max_length=MAX_CATEGORY)  # libre : « Gardien », « Métier »...
    entity_type: str = Field(default="", max_length=30)  # type de carte (football_player, job...)
    is_real: StrictBool | None = None  # la carte désigne une personne / un lieu réel (attestation de l'IA)
    rarity: int = Field(ge=0, le=3, strict=True)
    points: StrictInt = Field(ge=POINTS_MIN, le=POINTS_MAX)
    price: object = None  # estimé ; retenu seulement s'il est dans les bornes

    @field_validator("name")
    @classmethod
    def _required_text(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("vide")
        return v

    @field_validator("description", "category")
    @classmethod
    def _text(cls, v: str) -> str:
        return _clean(v)

    @field_validator("entity_type")
    @classmethod
    def _entity_type(cls, v: str) -> str:
        return slugify(v)[:30]


def _price(proposed: object, points: int, rarity: int) -> int:
    """Prix estimé proposé s'il est entier et borné, sinon calcul serveur."""
    if isinstance(proposed, int) and not isinstance(proposed, bool) \
            and MIN_PRICE <= proposed <= MAX_PRICE:
        return int(round(proposed / 10.0)) * 10
    return compute_price(points, rarity)


def normalize_ai_item(raw: object, taken_ids: set[str]) -> dict | None:
    """Valide une carte IA et la convertit au format commun, ou renvoie None si elle est rejetée.

    `taken_ids` : identifiants déjà utilisés ; l'id est généré par le serveur (préfixe `ai_`),
    jamais repris de l'IA.
    """
    if not isinstance(raw, dict):
        return None
    try:
        item = AIItem.model_validate(raw)
    except ValidationError:
        return None
    base = "ai_" + (slugify(item.name) or "carte")
    new_id, n = base, 2
    while new_id in taken_ids:
        new_id = f"{base}_{n}"
        n += 1
    taken_ids.add(new_id)
    return {"id": new_id, "name": item.name, "description": item.description,
            "category": item.category or "Divers", "icon": DEFAULT_ICON,
            "entity_type": item.entity_type, "is_real": item.is_real,
            "price": _price(item.price, item.points, item.rarity), "rarity": item.rarity,
            "base_points": 0, "attributes": {}, "points": item.points, "image": None,
            "source": "ai"}


def is_valid_item(item: dict) -> bool:
    """Contrôle de cohérence d'un objet au format commun (utile avant de jouer avec)."""
    try:
        known = criteria.registry()
        attrs = item["attributes"]
        return (ID_RE.match(item["id"]) is not None and item["price"] > 0
                and item["rarity"] in (0, 1, 2, 3)
                and 0 <= item["base_points"] <= BASE_POINTS_MAX
                and isinstance(attrs, dict) and set(attrs) <= set(known)
                and all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= ATTR_MAX
                        for v in attrs.values()))
    except (KeyError, TypeError):
        return False
