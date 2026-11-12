"""Fournisseur Google Gemini (SDK officiel `google-genai`, appels asynchrones).

- Modèle : `gemini-3.5-flash-lite` par défaut, modifiable par `BIDBANG_GEMINI_MODEL` (serveur).
- Sorties structurées : le schéma JSON de `generator.response_schema()` est transmis
  (`response_json_schema`) ; la réponse est quand même revalidée par le serveur.
- Aucun outil : pas de recherche Internet (Google Search, URL context...), pas de génération d'images.
- Aucun nouvel essai automatique et aucune bascule vers un autre fournisseur ou une offre payante :
  un quota dépassé (429) est signalé tel quel à l'hôte.
- La clé n'est qu'un argument de l'appel (variable locale, supprimée ensuite) ; les messages
  d'erreur sont génériques, jamais le texte du SDK (il peut citer la clé).
"""
import asyncio
import os

import httpx
from google import genai
from google.genai import errors, types

from .base import ProviderError

DEFAULT_MODEL = "gemini-3.5-flash-lite"
API_VERSION = "v1beta"  # prend en charge les sorties structurées (responseJsonSchema)
TRANSPORT: httpx.AsyncBaseTransport | None = None  # injecté par les tests : aucun appel réseau
QUOTA_MESSAGE = ("Quota gratuit Gemini dépassé (limite de requêtes par minute ou par jour). "
                 "Patientez, ou utilisez une autre clé ; le jeu ne bascule jamais "
                 "automatiquement vers une offre payante.")


def model_name() -> str:
    model = os.environ.get("BIDBANG_GEMINI_MODEL", DEFAULT_MODEL)
    if not model or not model.replace("-", "").replace(".", "").replace("_", "").isalnum():
        raise ProviderError("Modèle Gemini invalide (configuration du serveur).", 500)
    return model


class GeminiProvider:
    name = "gemini"
    label = "Google Gemini (gratuit, test)"
    structured = True  # accepte `json_schema`

    async def complete(self, *, api_key: str, system: str, prompt: str,
                       max_tokens: int, timeout: float,
                       json_schema: dict | None = None) -> str:
        model = model_name()
        config = types.GenerateContentConfig(
            system_instruction=system, max_output_tokens=max_tokens, temperature=0.8,
            response_mime_type="application/json", response_json_schema=json_schema,
            tools=None, http_options=types.HttpOptions(
                timeout=int(timeout * 1000), retry_options=types.HttpRetryOptions(attempts=1)))
        client_options = types.HttpOptions(api_version=API_VERSION)
        if TRANSPORT is not None:
            client_options.httpx_async_client = httpx.AsyncClient(transport=TRANSPORT)
        client = genai.Client(api_key=api_key, http_options=client_options)
        try:
            async with asyncio.timeout(timeout + 5):
                resp = await client.aio.models.generate_content(
                    model=model, contents=prompt, config=config)
        except errors.APIError as e:
            raise _convert(e) from None
        except (TimeoutError, asyncio.TimeoutError):
            raise ProviderError("Le fournisseur n'a pas répondu à temps.", 504) from None
        except Exception:
            raise ProviderError("Impossible de joindre le fournisseur d'IA.", 502) from None
        finally:
            try:
                await client.aio.aclose()
            except Exception:
                pass
            del client, api_key
        return _text(resp)


def _convert(e: errors.APIError) -> ProviderError:
    code = e.code if isinstance(e.code, int) else 0
    if code == 429:
        return ProviderError(QUOTA_MESSAGE, 429)
    if code in (400, 401, 403):  # Gemini répond 400 pour une clé invalide
        return ProviderError("Le fournisseur a refusé la clé API ou la demande "
                             "(clé invalide, sans droits, ou région non prise en charge).", 502)
    if code in (404,):
        return ProviderError("Modèle Gemini introuvable (configuration du serveur).", 502)
    if code in (408, 504):
        return ProviderError("Le fournisseur n'a pas répondu à temps.", 504)
    return ProviderError(f"Le fournisseur a renvoyé une erreur ({code or 'inconnue'}).", 502)


def _text(resp) -> str:
    try:
        feedback = getattr(resp, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            raise ProviderError("Le fournisseur a refusé de traiter cette demande.", 502)
        cand = resp.candidates[0]
        reason = str(getattr(cand, "finish_reason", "") or "")
        if any(r in reason for r in ("SAFETY", "PROHIBITED", "BLOCKLIST", "SPII")):
            raise ProviderError("Le fournisseur a refusé de traiter cette demande.", 502)
        parts = cand.content.parts or []
        text = "".join(p.text for p in parts if isinstance(getattr(p, "text", None), str))
    except ProviderError:
        raise
    except (AttributeError, IndexError, TypeError):
        raise ProviderError("Réponse inattendue du fournisseur.", 502) from None
    if not text:
        raise ProviderError("Réponse inattendue du fournisseur.", 502)
    return text
