import json

import pytest

from app.services import llm
from tests.conftest import mock_client

URL = "/api/v1/workspaces/{}/content/generate"


def _ok(request):  # MOCK of the provider
    text = json.dumps({"title": "Hello", "body": "Fresh shoes for you", "meta_title": "m", "meta_description": "d"})
    return __import__("httpx").Response(200, json={"content": [{"type": "text", "text": text}]})


def configure(monkeypatch, handler):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm, "http_client", lambda: mock_client(handler))


def test_not_configured_is_honest(client, owner):
    h, ws = owner
    r = client.post(URL.format(ws), headers=h, json={"kind": "blog", "brief": "shoe launch"})
    assert r.status_code == 503 and "not configured" in r.json()["detail"]
    assert client.get(f"/api/v1/workspaces/{ws}/content", headers=h).json() == []  # nothing fake saved


def test_generate_saves_validated_output(client, owner, monkeypatch):
    h, ws = owner
    client.put(f"/api/v1/workspaces/{ws}/profile", headers=h, json={"industry": "Footwear", "brand_voice": "friendly"})
    configure(monkeypatch, _ok)
    r = client.post(URL.format(ws), headers=h, json={"kind": "blog", "brief": "shoe launch"})
    assert r.status_code == 201
    v = r.json()["versions"][0]
    assert v["source"] == "ai" and v["meta"]["used_profile_fields"] == ["business_name", "industry", "brand_voice"]


@pytest.mark.parametrize("answer", ["not json at all", json.dumps({"title": "", "body": "x"}), "{}"])
def test_invalid_output_rejected_and_not_saved(client, owner, monkeypatch, answer):
    h, ws = owner
    configure(monkeypatch, lambda req: __import__("httpx").Response(200, json={"content": [{"type": "text", "text": answer}]}))
    assert client.post(URL.format(ws), headers=h, json={"kind": "blog", "brief": "shoe launch"}).status_code == 502
    assert client.get(f"/api/v1/workspaces/{ws}/content", headers=h).json() == []


def test_prohibited_claim_and_provider_errors(client, owner, monkeypatch):
    h, ws = owner
    client.put(f"/api/v1/workspaces/{ws}/profile", headers=h, json={"prohibited_claims": "fresh shoes"})
    configure(monkeypatch, _ok)
    r = client.post(URL.format(ws), headers=h, json={"kind": "blog", "brief": "shoe launch"})
    assert r.status_code == 502 and "prohibited" in r.json()["detail"]
    configure(monkeypatch, lambda req: __import__("httpx").Response(429, json={}))
    assert client.post(URL.format(ws), headers=h, json={"kind": "blog", "brief": "shoe launch"}).status_code == 502
