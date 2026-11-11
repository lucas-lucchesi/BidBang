"""Fournisseur Google Gemini (generateContent). Un seul hôte : generativelanguage.googleapis.com.

La clé passe dans l'en-tête `x-goog-api-key`, jamais dans l'URL.
"""
import os

from . import http_provider
from .base import ProviderError

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiProvider:
    name = "gemini"
    label = "Google Gemini"

    async def complete(self, *, api_key: str, system: str, prompt: str,
                       max_tokens: int, timeout: float) -> str:
        model = os.environ.get("BIDBANG_GEMINI_MODEL", DEFAULT_MODEL)
        if not model.replace("-", "").replace(".", "").replace("_", "").isalnum():
            raise ProviderError("Modèle Gemini invalide (configuration du serveur).", 500)
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens,
                                     "responseMimeType": "application/json"}}
        try:
            data = await http_provider.post_json(
                URL.format(model=model), {"x-goog-api-key": api_key}, body, timeout)
        finally:
            del api_key
        try:
            if data.get("promptFeedback", {}).get("blockReason"):
                raise ProviderError("Le fournisseur a refusé de traiter cette demande.", 502)
            cand = data["candidates"][0]
            if cand.get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
                raise ProviderError("Le fournisseur a refusé de traiter cette demande.", 502)
            parts = cand["content"]["parts"]
            return "".join(p["text"] for p in parts if isinstance(p.get("text"), str))
        except ProviderError:
            raise
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError("Réponse inattendue du fournisseur.", 502) from None
