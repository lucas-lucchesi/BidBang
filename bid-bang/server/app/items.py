"""Format commun des objets (catalogue, sélection manuelle, génération IA).

Un objet « commun » est un dict JSON :
    {id, name, description, category, icon, price, rarity, stats{5 stats}, tags[], source}
`source` vaut `catalog` ou `ai`. Les objets du catalogue gardent aussi `location_id`.

Tout objet venant de l'extérieur (IA aujourd'hui, bibliothèque communautaire demain)
passe par `AIItem` / `normalize_ai_item` : aucune valeur n'est reprise telle quelle,
et le prix est recalculé par le serveur.
"""
import re
import unicodedata

from pydantic import (BaseModel, ConfigDict, Field, StrictInt, ValidationError,
                      field_validator)

from . import catalog

STAT_KEYS = ("confort", "style", "utilite", "securite", "sante")
STAT_MAX = 5                    # valeur maximale d'une stat (comme le catalogue)
MIN_STAT_SUM = 3
MAX_STAT_SUM_BY_RARITY = (11, 12, 13, 16)  # plafond de la somme des stats par rareté
MAX_TAGS = 4
MAX_NAME = 40
MAX_DESCRIPTION = 140
MAX_CATEGORY = 30
MAX_TAG = 24
DEFAULT_ICON = "box"
ID_RE = re.compile(r"^[a-z0-9_]{1,48}$")


def slugify(text: str) -> str:
    """Identifiant ASCII minuscule : « Générateur d'oxygène » -> generateur_d_oxygene."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", norm.lower()).strip("_")
    return slug[:40]


def compute_price(stats: dict[str, int], rarity: int) -> int:
    """Prix indicatif calculé par le serveur (jamais repris de l'IA)."""
    raw = sum(stats.values()) * 12 + (0, 60, 120, 180)[rarity]
    return max(20, int(round(raw / 10.0)) * 10)


# ------------------------------------------------------------- catalogue
def catalog_item(raw: dict) -> dict:
    """Objet du catalogue au format commun (ajoute category/description/source)."""
    loc = catalog.get_location(raw["location_id"])
    item = dict(raw)
    item["category"] = loc["name"] if loc else raw["location_id"]
    item.setdefault("description", "")
    item["source"] = "catalog"
    return item


def catalog_items() -> list[dict]:
    return [catalog_item(i) for i in catalog.load_catalog()["items"]]


def catalog_item_map() -> dict[str, dict]:
    return {i["id"]: i for i in catalog_items()}


def categories() -> list[str]:
    seen: list[str] = []
    for loc in catalog.load_catalog()["locations"]:
        seen.append(loc["name"])
    return seen


# ------------------------------------------------------------------ IA
def _clean(text: str) -> str:
    """Normalise les espaces et retire les caractères de contrôle."""
    text = "".join(ch for ch in text if ch == " " or not unicodedata.category(ch).startswith("C"))
    return " ".join(text.split())


class AIItem(BaseModel):
    """Objet proposé par l'IA : tout champ hors schéma est ignoré, rien n'est supposé valide."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=MAX_NAME)
    description: str = Field(default="", max_length=MAX_DESCRIPTION)
    category: str = Field(min_length=1, max_length=MAX_CATEGORY)
    rarity: int = Field(ge=0, le=3, strict=True)
    stats: dict[str, StrictInt]
    tags: list[str] = Field(min_length=1, max_length=MAX_TAGS)
    price: object = None  # indicatif ; retenu seulement s'il est dans les bornes

    @field_validator("name", "category")
    @classmethod
    def _required_text(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("vide")
        return v

    @field_validator("description")
    @classmethod
    def _description(cls, v: str) -> str:
        return _clean(v)

    @field_validator("stats")
    @classmethod
    def _stats(cls, v: dict[str, int]) -> dict[str, int]:
        if set(v) != set(STAT_KEYS):
            raise ValueError("stats attendues : " + ", ".join(STAT_KEYS))
        for key, val in v.items():
            if isinstance(val, bool) or not isinstance(val, int) or not 0 <= val <= STAT_MAX:
                raise ValueError(f"stat {key} hors limites")
        return v

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for tag in v:
            slug = slugify(str(tag))[:MAX_TAG]
            if not slug:
                raise ValueError("tag vide")
            if slug not in out:
                out.append(slug)
        return out


MIN_PRICE, MAX_PRICE = 20, 600


def _price(proposed: object, stats: dict[str, int], rarity: int) -> int:
    """Prix proposé (ex. imposé par l'hôte) s'il est entier et borné, sinon calcul serveur."""
    if isinstance(proposed, int) and not isinstance(proposed, bool) \
            and MIN_PRICE <= proposed <= MAX_PRICE:
        return int(round(proposed / 10.0)) * 10
    return compute_price(stats, rarity)


def normalize_ai_item(raw: object, taken_ids: set[str]) -> dict | None:
    """Valide un objet IA et le convertit au format commun, ou renvoie None s'il est rejeté.

    `taken_ids` : identifiants déjà utilisés (catalogue + objets IA) ; l'id est généré par
    le serveur (préfixe `ai_`), jamais repris de l'IA.
    """
    if not isinstance(raw, dict):
        return None
    try:
        item = AIItem.model_validate(raw)
    except ValidationError:
        return None
    total = sum(item.stats.values())
    if total < MIN_STAT_SUM or total > MAX_STAT_SUM_BY_RARITY[item.rarity]:
        return None
    base = "ai_" + (slugify(item.name) or "objet")
    new_id, n = base, 2
    while new_id in taken_ids:
        new_id = f"{base}_{n}"
        n += 1
    taken_ids.add(new_id)
    stats = {k: item.stats[k] for k in STAT_KEYS}
    return {"id": new_id, "name": item.name, "description": item.description,
            "category": item.category, "icon": DEFAULT_ICON,
            "price": _price(item.price, stats, item.rarity), "rarity": item.rarity,
            "stats": stats, "tags": item.tags, "source": "ai"}


def is_valid_item(item: dict) -> bool:
    """Contrôle de cohérence d'un objet au format commun (utile avant de jouer avec)."""
    try:
        return (ID_RE.match(item["id"]) is not None and item["price"] > 0
                and item["rarity"] in (0, 1, 2, 3)
                and set(item["stats"]) == set(STAT_KEYS) and bool(item["tags"]))
    except (KeyError, TypeError):
        return False
