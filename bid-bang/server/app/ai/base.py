"""Interface des fournisseurs d'IA externes.

Pour ajouter un fournisseur : écrire une classe avec `name` et `complete(...)`,
puis l'ajouter à `PROVIDERS`. Un fournisseur :
  - n'appelle QUE son propre point d'accès (URL fixée dans le code, jamais choisie
    par l'utilisateur ni par l'IA) ;
  - ne conserve pas la clé après l'appel et ne l'écrit dans aucun log ;
  - convertit toute erreur en `ProviderError` avec un message générique en français
    (jamais le texte brut de l'erreur : il pourrait contenir des informations sensibles).
"""
from typing import Protocol

from ..errors import GameError


class ProviderError(GameError):
    """Erreur du fournisseur, message sûr à montrer à l'hôte."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message, status)


class AIProvider(Protocol):
    name: str
    label: str

    async def complete(self, *, api_key: str, system: str, prompt: str,
                       max_tokens: int, timeout: float) -> str:
        """Renvoie le texte de la réponse. Lève ProviderError."""
        ...


def _registry() -> dict[str, AIProvider]:
    from .anthropic_provider import AnthropicProvider
    from .gemini_provider import GeminiProvider
    from .openai_provider import OpenAIProvider
    return {p.name: p for p in (AnthropicProvider(), OpenAIProvider(), GeminiProvider())}


def get_provider(name: str) -> AIProvider:
    providers = _registry()
    if name not in providers:
        raise GameError("Fournisseur d'IA inconnu.")
    return providers[name]


def provider_names() -> list[dict]:
    return [{"id": p.name, "label": p.label} for p in _registry().values()]
