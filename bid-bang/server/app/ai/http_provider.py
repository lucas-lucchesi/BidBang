"""Appel HTTPS JSON commun aux fournisseurs sans SDK (OpenAI, Gemini).

Garanties : URL fournie par le code du fournisseur (jamais par l'utilisateur ni l'IA),
vérification TLS par défaut, pas de redirection (la clé ne suit jamais un autre hôte),
taille de réponse bornée, et toute erreur devient un `ProviderError` générique (le corps
de la réponse d'erreur, qui peut citer la clé, n'est jamais repris).
"""
import httpx

from .base import ProviderError

MAX_BODY_BYTES = 400_000
TRANSPORT: httpx.AsyncBaseTransport | None = None  # injecté par les tests


async def post_json(url: str, headers: dict[str, str], body: dict, timeout: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                     transport=TRANSPORT) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException:
        raise ProviderError("Le fournisseur n'a pas répondu à temps.", 504) from None
    except httpx.HTTPError:
        raise ProviderError("Impossible de joindre le fournisseur d'IA.", 502) from None
    except Exception:
        raise ProviderError("Erreur inattendue du fournisseur d'IA.", 502) from None
    status = resp.status_code
    if status in (401, 403):
        raise ProviderError("Le fournisseur a refusé la clé API (clé invalide ou sans droits).", 502)
    if status == 429:
        raise ProviderError("Limite de requêtes du fournisseur atteinte, réessayez plus tard.", 502)
    if status != 200:
        raise ProviderError(f"Le fournisseur a renvoyé une erreur ({status}).", 502)
    if len(resp.content) > MAX_BODY_BYTES:
        raise ProviderError("La réponse du fournisseur est trop volumineuse.", 502)
    try:
        data = resp.json()
    except ValueError:
        raise ProviderError("Réponse illisible du fournisseur.", 502) from None
    if not isinstance(data, dict):
        raise ProviderError("Réponse illisible du fournisseur.", 502)
    return data
