"""Calcul des points d'un objet pour une situation. Module pur : aucune dépendance réseau.

Les points sont calculés UNE fois, avant les enchères (`freeze_items`), puis figés : ils
sont identiques pour tous les joueurs et ne changent jamais pendant la partie.

Formule
-------
Pour chaque critère *nécessaire* de la situation que l'objet possède :

    contribution = (valeur_objet / 5) * (importance / 5)          # entre 0 et 1

Les critères non nécessaires, inconnus de l'objet ou invalides valent 0. On trie les
contributions par ordre décroissant et on ne garde que les `TOP_N` premières, pondérées
par `WEIGHTS` (1, 0.35, 0.12) :

    pertinence = min(1, somme(poids_k * contribution_k) / somme(WEIGHTS))

    points = MIN_POINTS + RELEVANCE_SPAN * pertinence**GAMMA
                        + BASE_SPAN * base_points / BASE_POINTS_MAX        (borné à 1..100)

Pourquoi cette formule est équitable :
- le prix et la rareté n'entrent nulle part ;
- la pertinence passe avant le nombre : seules les 3 meilleures correspondances comptent,
  et la 2e vaut 35 % de la 1re, la 3e 12 % : un objet très pertinent sur un besoin
  important bat un objet qui touche à tout superficiellement ;
- les caractéristiques hors situation (un jacuzzi en apocalypse) ne rapportent rien ;
- `base_points` n'apporte qu'un petit complément (10 points au maximum) ;
- tout objet garde au moins 1 point (objets inutiles ou humoristiques).
"""
from dataclasses import dataclass

from .criteria import ATTR_MAX, ATTR_MIN, IMPORTANCE_MAX


@dataclass(frozen=True)
class ScoringConfig:
    min_points: int = 1
    max_points: int = 100
    relevance_span: float = 89.0
    base_span: float = 10.0
    base_points_max: int = 50
    gamma: float = 1.15
    weights: tuple[float, ...] = (1.0, 0.35, 0.12)


DEFAULT_CONFIG = ScoringConfig()

# Seuils d'affichage (points -> niveau d'utilité), purement informatifs.
USEFULNESS_LEVELS = ((60, "high"), (30, "medium"), (12, "low"))


def _valid_attributes(attributes: object) -> dict[str, int]:
    """Caractéristiques exploitables : valeurs entières, bornées à 1..5 (le reste est ignoré)."""
    if not isinstance(attributes, dict):
        return {}
    out: dict[str, int] = {}
    for key, val in attributes.items():
        if isinstance(val, bool) or not isinstance(val, int) or val < ATTR_MIN:
            continue
        out[str(key)] = min(val, ATTR_MAX)
    return out


def contributions(item: dict, criteria: list[dict]) -> list[tuple[str, float]]:
    """(critère, contribution) pour les critères nécessaires que l'objet possède, du plus fort au plus faible."""
    attrs = _valid_attributes(item.get("attributes"))
    out: list[tuple[str, float]] = []
    for c in criteria:
        if not c.get("necessary"):
            continue
        imp = c.get("importance")
        if isinstance(imp, bool) or not isinstance(imp, int) or imp <= 0:
            continue
        value = attrs.get(c.get("id"))
        if value is None:
            continue
        imp = min(imp, IMPORTANCE_MAX)
        out.append((c["id"], (value / ATTR_MAX) * (imp / IMPORTANCE_MAX)))
    out.sort(key=lambda t: (-t[1], t[0]))
    return out


def relevance(item: dict, criteria: list[dict], config: ScoringConfig = DEFAULT_CONFIG) -> float:
    contribs = contributions(item, criteria)[:len(config.weights)]
    raw = sum(w * c for w, (_, c) in zip(config.weights, contribs))
    return min(1.0, raw / sum(config.weights))


def item_points(item: dict, criteria: list[dict], config: ScoringConfig = DEFAULT_CONFIG) -> int:
    bp = item.get("base_points", 0)
    bp = 0 if isinstance(bp, bool) or not isinstance(bp, (int, float)) else max(0, min(bp, config.base_points_max))
    raw = (config.min_points + config.relevance_span * relevance(item, criteria, config) ** config.gamma
           + config.base_span * bp / config.base_points_max)
    return max(config.min_points, min(config.max_points, int(round(raw))))


def usefulness(points: int) -> str:
    """high | medium | low | none, selon les points de l'objet."""
    for threshold, level in USEFULNESS_LEVELS:
        if points >= threshold:
            return level
    return "none"


def freeze_item(item: dict, criteria: list[dict],
                config: ScoringConfig = DEFAULT_CONFIG) -> dict:
    """Copie indépendante de l'objet avec ses points définitifs pour cette situation.

    Ajoute `points`, `useful_criteria` (critères nécessaires que l'objet couvre, du plus
    utile au moins utile, 3 au plus) et `usefulness`.
    """
    frozen = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
              for k, v in item.items()}
    points = item_points(item, criteria, config)
    frozen["points"] = points
    frozen["useful_criteria"] = [cid for cid, _ in contributions(item, criteria)[:3]]
    frozen["usefulness"] = usefulness(points)
    return frozen


def freeze_items(items: list[dict], criteria: list[dict],
                 config: ScoringConfig = DEFAULT_CONFIG) -> list[dict]:
    return [freeze_item(i, criteria, config) for i in items]


def freeze_ai_card(card: dict) -> dict:
    """Carte d'une partie IA : les points sont ceux attribués par l'IA (déjà validés, 1 à 100) ;
    on en fait une copie indépendante, sans critère (`useful_criteria` vide)."""
    frozen = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
              for k, v in card.items()}
    points = max(1, min(100, int(frozen.get("points", 1))))
    frozen["points"] = points
    frozen["useful_criteria"] = []
    frozen["usefulness"] = usefulness(points)
    return frozen
