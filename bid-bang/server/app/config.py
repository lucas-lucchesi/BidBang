"""Configuration par variables d'environnement (déploiement Railway ou local).

| Variable | Rôle | Défaut |
|---|---|---|
| `BIDBANG_ENV` | `production` : pas de documentation d'API, pas de fournisseur simulé, pas de clé lue dans l'environnement, pas de HTTP en clair pour les clés API, origines locales non autorisées | développement |
| `ALLOWED_ORIGINS` | origines de navigateur autorisées (CORS et WebSocket), séparées par des virgules, ex. `https://bidbang.vercel.app` | origines locales (développement seulement) |
| `ALLOWED_ORIGIN_REGEX` | motif facultatif pour des domaines variables (ex. déploiements de prévisualisation Vercel) | aucun |
| `MAX_ROOMS` | nombre maximal de salons en mémoire | 200 |

Une application native (Godot Android / iOS / PC) n'envoie pas d'en-tête `Origin` : elle n'est pas
concernée par ces règles. Seuls les navigateurs en envoient un.
"""
import os
import re

DEV_ORIGINS = (
    "http://localhost:8080", "http://127.0.0.1:8080",  # python -m http.server -d web_build 8080
    "http://localhost:8060", "http://127.0.0.1:8060",  # « Exécuter dans le navigateur » de Godot
    "http://localhost:8000", "http://127.0.0.1:8000",
)
DEFAULT_MAX_ROOMS = 200
_ORIGIN_RE = re.compile(r"^https?://[A-Za-z0-9.-]+(:\d{1,5})?$|^https?://\[[0-9a-fA-F:]+\](:\d{1,5})?$")


def is_production() -> bool:
    return os.environ.get("BIDBANG_ENV", "").strip().lower() == "production"


def _normalize(origin: str) -> str:
    return origin.strip().rstrip("/")


def allowed_origins() -> list[str]:
    """Origines exactes autorisées. Un joker `*` n'est jamais accepté."""
    configured = [_normalize(o) for o in os.environ.get("ALLOWED_ORIGINS", "").split(",")]
    valid = [o for o in configured if o and _ORIGIN_RE.match(o)]
    if is_production():
        return valid
    return valid + [o for o in DEV_ORIGINS if o not in valid]


def _origin_regex() -> re.Pattern | None:
    raw = os.environ.get("ALLOWED_ORIGIN_REGEX", "").strip()
    if not raw:
        return None
    try:
        return re.compile(raw)
    except re.error:
        return None


def origin_allowed(origin: str | None) -> bool:
    """Origine d'un navigateur autorisée ? `None` (pas d'en-tête Origin : application native,
    outil en ligne de commande) est accepté : l'authentification par jeton reste exigée."""
    if origin is None:
        return True
    origin = _normalize(origin)
    if origin in allowed_origins():
        return True
    rx = _origin_regex()
    return bool(rx and rx.fullmatch(origin))


def max_rooms() -> int:
    try:
        return max(1, int(os.environ.get("MAX_ROOMS", DEFAULT_MAX_ROOMS)))
    except ValueError:
        return DEFAULT_MAX_ROOMS
