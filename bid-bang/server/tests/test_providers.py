"""Fournisseurs OpenAI et Gemini : requêtes simulées (httpx.MockTransport), aucune clé réelle."""
import json

import httpx
import pytest

from app.ai import base, http_provider
from app.ai.base import ProviderError
from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider

KEY = "TESTSECRET-0123456789abcdef"
OK_TEXT = '{"items": []}'


def use(monkeypatch, handler):
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(http_provider, "TRANSPORT", httpx.MockTransport(wrapped))
    return seen


def openai_ok(_req):
    return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": OK_TEXT}}]})


def gemini_ok(_req):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": OK_TEXT}]}}]})


CASES = [(OpenAIProvider, openai_ok, "api.openai.com"),
         (GeminiProvider, gemini_ok, "generativelanguage.googleapis.com")]


async def call(provider, timeout=5):
    return await provider.complete(api_key=KEY, system="SYS", prompt="PROMPT", max_tokens=123, timeout=timeout)


def test_registry_lists_three_providers():
    assert {p["id"] for p in base.provider_names()} == {"anthropic", "openai", "gemini"}
    assert base.get_provider("openai").name == "openai"
    with pytest.raises(Exception):
        base.get_provider("inconnu")


@pytest.mark.parametrize("cls,ok,host", CASES)
async def test_success_and_request_shape(monkeypatch, cls, ok, host):
    seen = use(monkeypatch, ok)
    assert await call(cls()) == OK_TEXT
    req = seen[0]
    assert req.url.scheme == "https" and req.url.host == host
    assert KEY not in str(req.url) and KEY not in (req.url.query or b"").decode()
    assert KEY in json.dumps(dict(req.headers))           # la clé est dans un en-tête...
    assert KEY.encode() not in req.content                 # ...jamais dans le corps ni l'URL
    body = json.loads(req.content)
    assert "SYS" in json.dumps(body) and "PROMPT" in json.dumps(body)
    assert "123" in json.dumps(body)                       # plafond de sortie transmis


@pytest.mark.parametrize("cls,ok,host", CASES)
@pytest.mark.parametrize("status,fragment", [(401, "clé"), (403, "clé"), (429, "Limite"),
                                             (500, "(500)"), (400, "(400)")])
async def test_http_errors_leak_nothing(monkeypatch, cls, ok, host, status, fragment):
    use(monkeypatch, lambda r: httpx.Response(status, content=f"bad key {KEY}".encode()))
    with pytest.raises(ProviderError) as exc:
        await call(cls())
    assert fragment in exc.value.message
    assert KEY not in exc.value.message and KEY not in repr(exc.value)
    assert exc.value.__cause__ is None


@pytest.mark.parametrize("cls,ok,host", CASES)
async def test_timeout_connection_and_bad_payload(monkeypatch, cls, ok, host):
    def boom(exc):
        def handler(_req):
            raise exc
        return handler

    use(monkeypatch, boom(httpx.ReadTimeout(f"secret {KEY}")))
    with pytest.raises(ProviderError) as e1:
        await call(cls())
    assert e1.value.status == 504 and KEY not in e1.value.message
    use(monkeypatch, boom(httpx.ConnectError(f"secret {KEY}")))
    with pytest.raises(ProviderError) as e2:
        await call(cls())
    assert e2.value.status == 502 and KEY not in e2.value.message
    for resp in (httpx.Response(200, content=b"pas du json"), httpx.Response(200, json=[1]),
                 httpx.Response(200, json={}), httpx.Response(200, json={"choices": [], "candidates": []})):
        use(monkeypatch, lambda _r, resp=resp: resp)
        with pytest.raises(ProviderError):
            await call(cls())


@pytest.mark.parametrize("cls,ok,host", CASES)
async def test_redirect_not_followed_and_size_capped(monkeypatch, cls, ok, host):
    seen = use(monkeypatch, lambda r: httpx.Response(302, headers={"location": "https://evil.example/x"}))
    with pytest.raises(ProviderError):
        await call(cls())
    assert len(seen) == 1 and seen[0].url.host == host  # aucune requête vers un autre hôte
    use(monkeypatch, lambda r: httpx.Response(200, content=b"x" * (http_provider.MAX_BODY_BYTES + 1)))
    with pytest.raises(ProviderError, match="volumineuse"):
        await call(cls())


async def test_openai_content_filter(monkeypatch):
    use(monkeypatch, lambda r: httpx.Response(200, json={"choices": [{"finish_reason": "content_filter", "message": {"content": None}}]}))
    with pytest.raises(ProviderError, match="refusé"):
        await call(OpenAIProvider())


async def test_gemini_blocked_and_multipart(monkeypatch):
    use(monkeypatch, lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(ProviderError, match="refusé"):
        await call(GeminiProvider())
    use(monkeypatch, lambda r: httpx.Response(200, json={"candidates": [{"finishReason": "SAFETY"}]}))
    with pytest.raises(ProviderError):
        await call(GeminiProvider())
    use(monkeypatch, lambda r: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{"}, {"text": "}"}]}}]}))
    assert await call(GeminiProvider()) == "{}"


async def test_gemini_rejects_odd_model_name(monkeypatch):
    monkeypatch.setenv("BIDBANG_GEMINI_MODEL", "x/../../evil?key=1")
    seen = use(monkeypatch, gemini_ok)
    with pytest.raises(ProviderError):
        await call(GeminiProvider())
    assert not seen


@pytest.mark.parametrize("cls,ok,host", CASES)
async def test_works_end_to_end_with_generator(monkeypatch, cls, ok, host):
    from app.ai import generator
    item = {"name": "Objet", "category": "C", "rarity": 0, "tags": ["a"],
            "stats": {"confort": 2, "style": 1, "utilite": 3, "securite": 2, "sante": 1}}
    text = json.dumps({"items": [{**item, "name": f"Objet {i}"} for i in range(8)]})
    use(monkeypatch, lambda r: httpx.Response(200, json=(
        {"choices": [{"finish_reason": "stop", "message": {"content": text}}]} if cls is OpenAIProvider
        else {"candidates": [{"content": {"parts": [{"text": text}]}}]})))
    res = await generator.generate(cls(), KEY, {"description": "Une situation."}, "construction", 6, set())
    assert len(res.items) == 8
