"""Fournisseur OpenAI (Chat Completions). Un seul point d'accès : api.openai.com."""
import os

from . import http_provider
from .base import ProviderError

URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider:
    name = "openai"
    label = "OpenAI (GPT)"

    async def complete(self, *, api_key: str, system: str, prompt: str,
                       max_tokens: int, timeout: float) -> str:
        body = {"model": os.environ.get("BIDBANG_OPENAI_MODEL", DEFAULT_MODEL),
                "max_completion_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": prompt}]}
        try:
            data = await http_provider.post_json(
                URL, {"Authorization": f"Bearer {api_key}"}, body, timeout)
        finally:
            del api_key
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") == "content_filter":
                raise ProviderError("Le fournisseur a refusé de traiter cette demande.", 502)
            text = choice["message"]["content"]
        except ProviderError:
            raise
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError("Réponse inattendue du fournisseur.", 502) from None
        if not isinstance(text, str):
            raise ProviderError("Le fournisseur a refusé de traiter cette demande.", 502)
        return text
