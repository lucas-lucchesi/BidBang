"""Fournisseur Anthropic (SDK officiel). Un seul point d'accès : api.anthropic.com.

La clé n'est qu'un argument de l'appel : elle vit dans une variable locale, passe au
client du SDK le temps de la requête, puis les références sont supprimées.
"""
import asyncio
import os

import anthropic

from .base import ProviderError

DEFAULT_MODEL = "claude-opus-5-5"


class AnthropicProvider:
    name = "anthropic"
    label = "Anthropic (Claude)"

    async def complete(self, *, api_key: str, system: str, prompt: str,
                       max_tokens: int, timeout: float) -> str:
        model = os.environ.get("BIDBANG_AI_MODEL", DEFAULT_MODEL)
        client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=0, timeout=timeout)
        try:
            async with asyncio.timeout(timeout + 5):
                resp = await client.messages.create(
                    model=model, max_tokens=max_tokens, system=system,
                    output_config={"effort": "low"},
                    messages=[{"role": "user", "content": prompt}])
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            raise ProviderError("Le fournisseur a refusé la clé API (clé invalide ou sans droits).", 502) from None
        except anthropic.RateLimitError:
            raise ProviderError("Limite de requêtes du fournisseur atteinte, réessayez plus tard.", 502) from None
        except (anthropic.APITimeoutError, TimeoutError):
            raise ProviderError("Le fournisseur n'a pas répondu à temps.", 504) from None
        except anthropic.APIConnectionError:
            raise ProviderError("Impossible de joindre le fournisseur d'IA.", 502) from None
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Le fournisseur a renvoyé une erreur ({e.status_code}).", 502) from None
        except Exception:
            raise ProviderError("Erreur inattendue du fournisseur d'IA.", 502) from None
        finally:
            await client.close()
            del client, api_key
        if resp.stop_reason == "refusal":
            raise ProviderError("Le fournisseur a refusé de traiter cette demande.", 502)
        return "".join(b.text for b in resp.content if b.type == "text")
