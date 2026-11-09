import json

import httpx
import pytest

from app.services import llm, ssrf
from tests.conftest import mock_client, signup
from tests.test_publish_flow import FakeWP, approved, setup  # FakeWP is a MOCK


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(ssrf, "resolve", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])


def provider(monkeypatch, answer, tokens=(100, 50), status=200):
    calls = {"n": 0}

    def handler(req):  # MOCK provider
        calls["n"] += 1
        if status != 200:
            return httpx.Response(status, json={})
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return httpx.Response(200, json={"content": [{"type": "text", "text": text}], "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]}})

    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm, "http_client", lambda: mock_client(handler))
    return calls


def doc(client, h, ws, body="Our new shoes are comfortable. Visit the shop this week."):
    return client.post(f"/api/v1/workspaces/{ws}/content", headers=h, json={"kind": "blog", "title": "Shoes", "body": body}).json()


def ai(client, h, ws, did, **kw):
    return client.post(f"/api/v1/workspaces/{ws}/content/{did}/ai", headers=h, json=kw)


def test_rewrite_creates_a_new_version_and_never_touches_the_source(client, owner, monkeypatch):
    h, ws = owner
    d = doc(client, h, ws)
    provider(monkeypatch, {"body": "Comfortable new shoes. Drop by this week."})
    r = ai(client, h, ws, d["id"], action="rewrite_tone", tone="friendly")
    assert r.status_code == 200 and r.json()["kind"] == "version" and r.json()["version"]["number"] == 2 and r.json()["version"]["source"] == "ai"
    full = client.get(f"/api/v1/workspaces/{ws}/content/{d['id']}", headers=h).json()
    assert full["versions"][0]["body"] == d["versions"][0]["body"]  # v1 untouched
    assert full["versions"][1]["meta"]["ai_action"] == "rewrite_tone" and full["versions"][1]["meta"]["parent_version"] == 1


def test_ai_change_invalidates_the_old_approval_and_nothing_publishes(client, owner, monkeypatch):
    fake = FakeWP()
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, h, b, iid, d)
    provider(monkeypatch, {"body": "A different text entirely."})
    assert ai(client, h, d and b.split("/")[-1], d["id"], action="improve").status_code == 200
    assert client.get(f"{b}/approvals/{aid}", headers=h).json()["status"] == "INVALIDATED"
    assert client.post(f"{b}/approvals/{aid}/execute", headers=h).status_code == 409 and fake.calls == 0


def test_repurpose_makes_a_new_linked_document(client, owner, monkeypatch):
    h, ws = owner
    d = doc(client, h, ws)
    provider(monkeypatch, {"title": "New shoes!", "body": "Come and see our new shoes this week."})
    r = ai(client, h, ws, d["id"], action="to_linkedin").json()
    assert r["kind"] == "document" and r["document"]["kind"] == "social_post" and r["document"]["id"] != d["id"]
    assert r["document"]["versions"][0]["meta"]["derived_from"]["document_id"] == d["id"]
    assert len(client.get(f"/api/v1/workspaces/{ws}/content/{d['id']}", headers=h).json()["versions"]) == 1  # source unchanged


def test_suggestions_are_returned_but_not_saved(client, owner, monkeypatch):
    h, ws = owner
    d = doc(client, h, ws)
    provider(monkeypatch, {"items": ["One", "Two", "Three"]})
    r = ai(client, h, ws, d["id"], action="headlines").json()
    assert r == {"kind": "suggestions", "action": "headlines", "items": ["One", "Two", "Three"], "saved": False}
    assert len(client.get(f"/api/v1/workspaces/{ws}/content", headers=h).json()) == 1


def test_bad_output_saves_nothing_but_counts_usage(client, owner, monkeypatch):
    h, ws = owner
    d = doc(client, h, ws)
    provider(monkeypatch, "not json at all", tokens=(80, 20))
    assert ai(client, h, ws, d["id"], action="improve").status_code == 502
    assert len(client.get(f"/api/v1/workspaces/{ws}/content/{d['id']}", headers=h).json()["versions"]) == 1
    u = client.get(f"/api/v1/workspaces/{ws}/ai/usage", headers=h).json()
    assert u["requests"] == 1 and u["by_action"] == {"improve": 1}


def test_prohibited_claim_in_ai_output_is_rejected(client, owner, monkeypatch):
    h, ws = owner
    client.put(f"/api/v1/workspaces/{ws}/profile", headers=h, json={"prohibited_claims": "cheapest in town"})
    d = doc(client, h, ws)
    provider(monkeypatch, {"body": "We are the cheapest in town."})
    assert ai(client, h, ws, d["id"], action="improve").status_code == 502


def test_validation_permissions_tenancy_limits_and_errors(client, owner, monkeypatch):
    h, ws = owner
    d = doc(client, h, ws)
    assert ai(client, h, ws, d["id"], action="rewrite_tone").status_code == 422  # tone required
    assert ai(client, h, ws, d["id"], action="delete_everything").status_code == 422
    assert ai(client, h, ws, d["id"], action="improve").status_code == 503  # not configured, honest
    calls = provider(monkeypatch, {"body": "x y"}, status=429)
    r = ai(client, h, ws, d["id"], action="improve")
    assert r.status_code == 502 and "rate limiting" in r.json()["detail"]
    viewer = signup(client, "cv@example.com")
    client.post(f"/api/v1/workspaces/{ws}/members", headers=h, json={"email": "cv@example.com", "role": "viewer"})
    assert ai(client, viewer, ws, d["id"], action="improve").status_code == 403
    assert ai(client, signup(client, "co@example.com"), ws, d["id"], action="improve").status_code == 404
    monkeypatch.setenv("AI_MONTHLY_LIMIT", "1")
    n = calls["n"]
    assert ai(client, h, ws, d["id"], action="improve").status_code == 429 and calls["n"] == n


def test_cost_is_an_estimate_only_when_prices_are_configured(client, owner, monkeypatch):
    h, ws = owner
    d = doc(client, h, ws)
    provider(monkeypatch, {"items": ["A"]}, tokens=(1_000_000, 500_000))
    ai(client, h, ws, d["id"], action="cta")
    u = client.get(f"/api/v1/workspaces/{ws}/ai/usage", headers=h).json()
    assert u["estimated_cost"] is None and "Unavailable" in u["cost_note"]  # never invented
    monkeypatch.setenv("LLM_PRICE_INPUT_PER_MTOK", "3")
    monkeypatch.setenv("LLM_PRICE_OUTPUT_PER_MTOK", "15")
    u = client.get(f"/api/v1/workspaces/{ws}/ai/usage", headers=h).json()
    assert u["estimated_cost"] == 10.5 and "not your provider bill" in u["cost_note"]


def test_claim_heuristics_warn_unless_approved(client, owner):
    h, ws = owner
    b = f"/api/v1/workspaces/{ws}"
    d = client.post(f"{b}/content", headers=h, json={"kind": "social_post", "title": "S", "body": "Guaranteed 50% growth and 3x leads."}).json()
    codes = [i["code"] for i in client.get(f"{b}/content/{d['id']}/check", headers=h).json()["issues"]]
    assert codes.count("unsupported_claim") == 2 and "absolute_claim" in codes
    client.put(f"{b}/profile", headers=h, json={"approved_claims": "50% growth\n3x leads\nguaranteed"})
    codes = [i["code"] for i in client.get(f"{b}/content/{d['id']}/check", headers=h).json()["issues"]]
    assert "unsupported_claim" not in codes and "absolute_claim" not in codes
