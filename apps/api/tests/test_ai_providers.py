import json

import httpx
import pytest

from app.db.models import AiUsage
from app.services import llm
from tests.conftest import mock_client, signup

GEN = json.dumps({"title": "Hello", "body": "Fresh shoes for you", "meta_title": "m", "meta_description": "d"})
HOSTS = {"api.openai.com": "openai", "api.anthropic.com": "anthropic", "generativelanguage.googleapis.com": "gemini"}


class Mock:
    """MOCK of the three providers' public APIs. It proves our request and parsing logic only, not any real account."""
    def __init__(self):
        self.calls, self.fail = [], {}
        self.models = {"openai": ["gpt-main", "gpt-fast", "gpt-other"], "anthropic": ["claude-main"], "gemini": ["gemini-main"]}
        self.text = GEN

    def __call__(self, req):
        prov = HOSTS[req.url.host]
        body = json.loads(req.content) if req.content else {}
        self.calls.append({"provider": prov, "method": req.method, "path": req.url.path, "headers": dict(req.headers), "body": body, "url": str(req.url)})
        if self.fail.get(prov):
            return httpx.Response(self.fail[prov], json={})
        if req.method == "GET":
            return httpx.Response(200, json={"models": [{"name": f"models/{m}"} for m in self.models[prov]]} if prov == "gemini" else {"data": [{"id": m} for m in self.models[prov]]})
        if prov == "openai":
            return httpx.Response(200, json={"output": [{"type": "message", "content": [{"type": "output_text", "text": self.text}]}], "usage": {"input_tokens": 11, "output_tokens": 7}})
        if prov == "anthropic":
            return httpx.Response(200, json={"content": [{"type": "text", "text": self.text}], "usage": {"input_tokens": 20, "output_tokens": 9}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": self.text}]}}], "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 3}})


@pytest.fixture()
def mock(monkeypatch):
    m = Mock()
    monkeypatch.setattr(llm, "http_client", lambda: mock_client(m))
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    return m


@pytest.fixture()
def people(client, owner):
    oh, ws = owner
    out = {"owner": oh}
    for r in ("admin", "viewer", "super_agent"):
        out[r] = signup(client, f"ai-{r}@example.com")
        client.post(f"/api/v1/workspaces/{ws}/members", headers=oh, json={"email": f"ai-{r}@example.com", "role": r})
    return out


def U(ws, tail):
    return f"/api/v1/workspaces/{ws}/ai/{tail}"


def verify(client, ws, h, monkeypatch, provider="openai", key="sk-test"):
    monkeypatch.setenv({"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}[provider], key)
    return client.post(U(ws, f"providers/{provider}/test"), headers=h).json()


def gen(client, ws, h):
    return client.post(f"/api/v1/workspaces/{ws}/content/generate", headers=h, json={"kind": "blog", "brief": "shoe launch"})


def test_only_the_owner_can_see_or_change_ai_settings(client, owner, people, mock):
    _, ws = owner
    for who in ("admin", "viewer", "super_agent"):
        h = people[who]
        assert client.get(U(ws, "providers"), headers=h).status_code == 403
        assert client.post(U(ws, "providers/openai/test"), headers=h).status_code == 403
        assert client.put(U(ws, "config"), headers=h, json={"provider": "openai", "model": "gpt-main"}).status_code == 403
        assert client.delete(U(ws, "config"), headers=h).status_code == 403
    assert client.get(U(ws, "providers"), headers=people["owner"]).status_code == 200


def test_keys_never_leave_the_server_and_nothing_is_connected_before_a_real_test(client, owner, mock, monkeypatch):
    oh, ws = owner
    monkeypatch.setenv("OPENAI_API_KEY", "sk-SUPER-SECRET-123")
    g = client.get(U(ws, "providers"), headers=oh)
    assert "SUPER-SECRET" not in g.text
    o = [p for p in g.json()["providers"] if p["provider"] == "openai"][0]
    assert o["key_configured"] is True and o["connected"] is False and o["last_ok_at"] is None  # a key alone is not a connection
    t = client.post(U(ws, "providers/openai/test"), headers=oh)
    assert "SUPER-SECRET" not in t.text and t.json()["ok"] is True
    assert [p for p in client.get(U(ws, "providers"), headers=oh).json()["providers"] if p["provider"] == "openai"][0]["connected"] is True
    assert all("SUPER-SECRET" not in c["url"] for c in mock.calls)  # not in any URL either
    assert mock.calls[0]["headers"]["authorization"] == "Bearer sk-SUPER-SECRET-123"
    monkeypatch.delenv("OPENAI_API_KEY")
    assert [p for p in client.get(U(ws, "providers"), headers=oh).json()["providers"] if p["provider"] == "openai"][0]["connected"] is False  # key removed


def test_connection_test_reports_real_errors(client, owner, mock, monkeypatch):
    oh, ws = owner
    r = client.post(U(ws, "providers/openai/test"), headers=oh).json()
    assert r["ok"] is False and "OPENAI_API_KEY" in r["error"] and mock.calls == []  # no key: nothing is called
    monkeypatch.setenv("OPENAI_API_KEY", "sk-bad")
    mock.fail["openai"] = 401
    r = client.post(U(ws, "providers/openai/test"), headers=oh).json()
    assert r["ok"] is False and "rejected the API key" in r["error"]
    mock.fail.clear()
    assert client.post(U(ws, "providers/openai/test"), headers=oh).json()["ok"] is True
    mock.fail["openai"] = 500
    bad = client.post(U(ws, "providers/openai/test"), headers=oh).json()
    p = [x for x in client.get(U(ws, "providers"), headers=oh).json()["providers"] if x["provider"] == "openai"][0]
    assert bad["ok"] is False and p["last_ok_at"] is not None and "HTTP 500" in p["last_error"] and p["connected"] is False
    assert client.post(U(ws, "providers/skynet/test"), headers=oh).status_code == 404


def test_models_must_be_verified_against_the_account_before_selection(client, owner, mock, monkeypatch):
    oh, ws = owner
    body = {"provider": "openai", "model": "gpt-main", "fast_model": "gpt-fast"}
    assert client.put(U(ws, "config"), headers=oh, json=body).status_code == 422  # never tested
    verify(client, ws, oh, monkeypatch)
    assert client.put(U(ws, "config"), headers=oh, json={"provider": "openai", "model": "gpt-6.1-sol"}).status_code == 422  # not in this account's list
    assert client.put(U(ws, "config"), headers=oh, json={**body, "fast_model": "gpt-6-luna"}).status_code == 422
    r = client.put(U(ws, "config"), headers=oh, json=body)
    assert r.status_code == 200 and r.json()["model"] == "gpt-main"
    assert client.get(U(ws, "providers"), headers=oh).json()["config"]["fast_model"] == "gpt-fast"
    assert client.put(U(ws, "config"), headers=oh, json={**body, "fallback_enabled": True}).status_code == 422  # fallback needs a target


def test_generation_goes_through_the_selected_provider_and_usage_is_tracked(client, owner, mock, monkeypatch):
    oh, ws = owner
    verify(client, ws, oh, monkeypatch)
    client.put(U(ws, "config"), headers=oh, json={"provider": "openai", "model": "gpt-main", "fast_model": "gpt-fast"})
    mock.calls.clear()
    r = gen(client, ws, oh)
    assert r.status_code == 201
    call = mock.calls[0]
    assert call["provider"] == "openai" and call["path"] == "/v1/responses" and call["body"]["model"] == "gpt-main"
    v = r.json()["versions"][0]["meta"]
    assert v["provider"] == "openai" and v["model"] == "gpt-main"
    u = client.get(U(ws, "usage").replace("/ai/", "/ai/"), headers=oh).json()
    assert u["by_provider"]["openai"]["requests"] == 1 and u["by_provider"]["openai"]["input_tokens"] == 11 and u["input_tokens"] == 11
    doc = r.json()["id"]
    mock.text = json.dumps({"items": ["A", "B"]})
    mock.calls.clear()
    client.post(f"/api/v1/workspaces/{ws}/content/{doc}/ai", headers=oh, json={"action": "cta"})
    assert mock.calls[0]["body"]["model"] == "gpt-fast"  # quick tasks use the fast model
    mock.text = json.dumps({"body": "Rewritten"})
    mock.calls.clear()
    client.post(f"/api/v1/workspaces/{ws}/content/{doc}/ai", headers=oh, json={"action": "improve"})
    assert mock.calls[0]["body"]["model"] == "gpt-main"


def test_gemini_and_anthropic_are_supported_and_keys_stay_out_of_urls(client, owner, mock, monkeypatch):
    oh, ws = owner
    verify(client, ws, oh, monkeypatch, "gemini", "g-key-777")
    assert client.put(U(ws, "config"), headers=oh, json={"provider": "gemini", "model": "gemini-main"}).status_code == 200
    mock.calls.clear()
    assert gen(client, ws, oh).status_code == 201
    c = mock.calls[0]
    assert c["path"].endswith("gemini-main:generateContent") and c["headers"]["x-goog-api-key"] == "g-key-777" and "g-key-777" not in c["url"]
    verify(client, ws, oh, monkeypatch, "anthropic", "a-key-1")
    client.put(U(ws, "config"), headers=oh, json={"provider": "anthropic", "model": "claude-main"})
    mock.calls.clear()
    assert gen(client, ws, oh).status_code == 201 and mock.calls[0]["headers"]["x-api-key"] == "a-key-1"
    assert {k for k in client.get(U(ws, "usage"), headers=oh).json()["by_provider"]} == {"gemini", "anthropic"}


def test_fallback_happens_only_when_explicitly_configured(client, owner, mock, monkeypatch):
    oh, ws = owner
    verify(client, ws, oh, monkeypatch, "openai")
    verify(client, ws, oh, monkeypatch, "anthropic", "a-key")
    base = {"provider": "openai", "model": "gpt-main"}
    client.put(U(ws, "config"), headers=oh, json=base)  # no fallback
    mock.fail["openai"] = 500
    mock.calls.clear()
    r = gen(client, ws, oh)
    assert r.status_code == 502 and all(c["provider"] == "openai" for c in mock.calls)  # Claude was never tried
    client.put(U(ws, "config"), headers=oh, json={**base, "fallback_enabled": True, "fallback_provider": "anthropic", "fallback_model": "claude-main"})
    r = gen(client, ws, oh)
    assert r.status_code == 201
    meta = r.json()["versions"][0]["meta"]
    assert meta["fallback_used"] is True and meta["provider"] == "anthropic" and "HTTP 500" in meta["primary_error"]  # visible, not silent
    both = client.get(U(ws, "usage"), headers=oh).json()["by_provider"]
    assert both["anthropic"]["requests"] == 1 and both["openai"]["requests"] == 1  # the failed attempt is counted too
    mock.fail["anthropic"] = 500
    assert gen(client, ws, oh).status_code == 502  # both failed: the real error, nothing saved
    assert len(client.get(f"/api/v1/workspaces/{ws}/content", headers=oh).json()) == 1


def test_a_missing_key_gives_a_clear_setup_message_and_reset_returns_to_defaults(client, owner, mock, monkeypatch):
    oh, ws = owner
    verify(client, ws, oh, monkeypatch)
    client.put(U(ws, "config"), headers=oh, json={"provider": "openai", "model": "gpt-main"})
    monkeypatch.delenv("OPENAI_API_KEY")
    r = gen(client, ws, oh)
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]
    assert client.delete(U(ws, "config"), headers=oh).json() == {"saved": False}
    r = gen(client, ws, oh)
    assert r.status_code == 503 and "LLM_PROVIDER=anthropic" in r.json()["detail"]  # back to the server's environment defaults


def test_costs_are_estimates_only_where_prices_are_configured(client, owner, mock, monkeypatch, db_session):
    oh, ws = owner
    verify(client, ws, oh, monkeypatch)
    client.put(U(ws, "config"), headers=oh, json={"provider": "openai", "model": "gpt-main"})
    gen(client, ws, oh)
    u = client.get(U(ws, "usage"), headers=oh).json()
    assert u["estimated_cost"] is None and u["unpriced_requests"] == 1 and "Unavailable" in u["cost_note"]
    monkeypatch.setenv("AI_PRICES", json.dumps({"openai:gpt-main": {"in": 1000000, "out": 2000000}}))
    u = client.get(U(ws, "usage"), headers=oh).json()
    assert u["estimated_cost"] == 11 * 1 + 7 * 2 and u["by_provider"]["openai"]["estimated_cost"] == 25.0 and "not your provider bill" in u["cost_note"]
    monkeypatch.setenv("AI_PRICES", "not json")
    assert client.get(U(ws, "usage"), headers=oh).json()["estimated_cost"] is None  # broken config never invents a number
    assert db_session.query(AiUsage).filter_by(provider="openai").count() == 1
