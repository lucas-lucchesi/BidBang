"""Journal de développement de la génération IA (désactivé par défaut).

`BIDBANG_AI_DEBUG=1` affiche, à chaque étape, les identifiants et noms des cartes (tronqués).
Ne reçoit jamais de clé API ni de texte brut de réponse : seulement des noms et des raisons.
"""
import logging
import os

log = logging.getLogger("bidbang.ai.debug")


def enabled() -> bool:
    return os.environ.get("BIDBANG_AI_DEBUG") == "1"


def cards(stage: str, items: list[dict], note: str = "") -> None:
    if not enabled():
        return
    shown = ", ".join(f"{i.get('id', '?')}={str(i.get('name', '?'))[:30]!r}" for i in items[:40])
    log.warning("[ia] %s (%d cartes)%s : %s", stage, len(items), f" {note}" if note else "", shown)


def dropped(stage: str, rejected: list[tuple[str, str]]) -> None:
    if enabled() and rejected:
        log.warning("[ia] %s : %d écartée(s) : %s", stage, len(rejected),
                    "; ".join(f"{n[:30]!r} ({why})" for n, why in rejected[:40]))


def message(stage: str, text: str) -> None:
    if enabled():
        log.warning("[ia] %s : %s", stage, text[:300])
