"""Thin adapters for the AI providers' official HTTP APIs. API keys come from the server environment only.
Nothing here has been run against a real account: tests use mock servers, and the app shows a provider as connected only after a real test succeeds."""
import os

import httpx

PROVIDERS = {
    "openai": {"label": "OpenAI", "env": "OPENAI_API_KEY", "docs": "https://platform.openai.com/docs/api-reference"},
    "anthropic": {"label": "Anthropic Claude", "env": "ANTHROPIC_API_KEY", "docs": "https://docs.anthropic.com/en/api"},
    "gemini": {"label": "Google Gemini", "env": "GEMINI_API_KEY", "docs": "https://ai.google.dev/api"},
}


class ProviderError(Exception):
    def __init__(self, message: str, usage: dict | None = None):
        super().__init__(message)
        self.usage = usage


def key_for(provider: str) -> str:
    return os.getenv(PROVIDERS[provider]["env"], "")


def _headers(provider: str, key: str) -> dict:
    if provider == "openai":
        return {"Authorization": f"Bearer {key}", "content-type": "application/json"}
    if provider == "anthropic":
        return {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    return {"x-goog-api-key": key, "content-type": "application/json"}  # the key is sent in a header, never in the URL


def _check(r: httpx.Response) -> None:
    if r.status_code == 200:
        return
    if r.status_code in (401, 403):
        raise ProviderError(f"The provider rejected the API key (HTTP {r.status_code})")
    if r.status_code == 404:
        raise ProviderError("The provider does not know this model or endpoint (HTTP 404)")
    if r.status_code == 429:
        raise ProviderError("The AI provider is rate limiting requests. Try again in a minute")
    raise ProviderError(f"AI provider returned HTTP {r.status_code}")


def _send(c: httpx.Client, method: str, url: str, **kw) -> httpx.Response:
    try:
        r = c.request(method, url, **kw)
    except httpx.RequestError as exc:
        raise ProviderError(f"Could not reach the AI provider: {type(exc).__name__}")
    _check(r)
    return r


def list_models(c: httpx.Client, provider: str, key: str) -> list[str]:
    """Asks the provider which models this key can use. This is how a model is verified before it can be selected."""
    url = {"openai": "https://api.openai.com/v1/models", "anthropic": "https://api.anthropic.com/v1/models?limit=1000",
           "gemini": "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"}[provider]
    try:
        data = _send(c, "GET", url, headers=_headers(provider, key)).json()
        if provider == "gemini":
            return [m["name"].removeprefix("models/") for m in data.get("models", [])]
        return [m["id"] for m in data.get("data", [])]
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ProviderError("The provider returned a model list in an unexpected format")


def complete(c: httpx.Client, provider: str, model: str, key: str, system: str, user: str, max_tokens: int = 2000):
    """One request. Returns (text, usage). usage = {'input_tokens': int, 'output_tokens': int}."""
    h = _headers(provider, key)
    if provider == "openai":  # Responses API
        r = _send(c, "POST", "https://api.openai.com/v1/responses", headers=h,
                  json={"model": model, "instructions": system, "input": user, "max_output_tokens": max_tokens})
    elif provider == "anthropic":
        r = _send(c, "POST", "https://api.anthropic.com/v1/messages", headers=h,
                  json={"model": model, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user}]})
    else:
        r = _send(c, "POST", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", headers=h,
                  json={"system_instruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
                        "generationConfig": {"maxOutputTokens": max_tokens}})
    usage = {"input_tokens": 0, "output_tokens": 0}
    try:
        d = r.json()
        if provider == "openai":
            u = d.get("usage") or {}
            usage = {"input_tokens": int(u.get("input_tokens", 0)), "output_tokens": int(u.get("output_tokens", 0))}
            text = "".join(p.get("text", "") for it in d.get("output", []) if it.get("type") == "message" for p in it.get("content", []) if p.get("type") == "output_text")
        elif provider == "anthropic":
            u = d.get("usage") or {}
            usage = {"input_tokens": int(u.get("input_tokens", 0)), "output_tokens": int(u.get("output_tokens", 0))}
            text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        else:
            u = d.get("usageMetadata") or {}
            usage = {"input_tokens": int(u.get("promptTokenCount", 0)), "output_tokens": int(u.get("candidatesTokenCount", 0))}
            text = "".join(p.get("text", "") for p in (d.get("candidates") or [{}])[0].get("content", {}).get("parts", []))
        return text, usage
    except (ValueError, TypeError, AttributeError, IndexError):
        raise ProviderError("AI provider returned an unreadable answer", usage)
