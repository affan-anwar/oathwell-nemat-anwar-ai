import json

import httpx
import pytest

from app.services import llm, ssrf
from tests.conftest import mock_client, signup
from tests.test_publish_flow import FakeWP, approved, setup  # FakeWP is a MOCK


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(ssrf, "resolve", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])


GEN = "/api/v1/workspaces/{}/content/generate"


def ai(monkeypatch, text=None, tokens=(120, 340)):
    calls = {"n": 0}
    text = text or json.dumps({"title": "Hello", "body": "Fresh shoes", "meta_title": "m", "meta_description": "d"})

    def handler(req):  # MOCK provider
        calls["n"] += 1
        return httpx.Response(200, json={"content": [{"type": "text", "text": text}], "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]}})

    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm, "http_client", lambda: mock_client(handler))
    return calls


def test_ai_usage_is_recorded_from_provider_tokens(client, owner, monkeypatch):
    h, ws = owner
    ai(monkeypatch)
    for _ in range(2):
        assert client.post(GEN.format(ws), headers=h, json={"kind": "blog", "brief": "shoe launch"}).status_code == 201
    u = client.get(f"/api/v1/workspaces/{ws}/ai/usage", headers=h).json()
    assert (u["requests"], u["input_tokens"], u["output_tokens"]) == (2, 240, 680) and u["remaining"] == u["limit"] - 2


def test_unconfigured_ai_records_no_usage(client, owner):
    h, ws = owner
    assert client.post(GEN.format(ws), headers=h, json={"kind": "blog", "brief": "x y z"}).status_code == 503
    assert client.get(f"/api/v1/workspaces/{ws}/ai/usage", headers=h).json()["requests"] == 0


def test_monthly_ai_limit_stops_calls(client, owner, monkeypatch):
    h, ws = owner
    calls = ai(monkeypatch)
    monkeypatch.setenv("AI_MONTHLY_LIMIT", "2")
    codes = [client.post(GEN.format(ws), headers=h, json={"kind": "blog", "brief": "shoe launch"}).status_code for _ in range(3)]
    assert codes == [201, 201, 429] and calls["n"] == 2  # the provider was not called a third time


def test_rejected_output_still_counts_tokens(client, owner, monkeypatch):
    h, ws = owner
    ai(monkeypatch, text="not json")
    assert client.post(GEN.format(ws), headers=h, json={"kind": "blog", "brief": "shoe launch"}).status_code == 502
    u = client.get(f"/api/v1/workspaces/{ws}/ai/usage", headers=h).json()
    assert u["requests"] == 1 and u["output_tokens"] == 340


def test_notifications_flow_and_privacy(client, owner, monkeypatch):
    h, b, iid, d = setup(client, owner, monkeypatch, FakeWP())
    editor = signup(client, "ed2@example.com")
    client.post(f"{b}/members", headers=h, json={"email": "ed2@example.com", "role": "editor"})
    a = client.post(f"{b}/approvals", headers=editor, json={"version_id": d["versions"][0]["id"], "integration_id": iid, "action": "publish_blog"}).json()
    owner_n = client.get(f"{b}/notifications", headers=h).json()
    assert owner_n["unread"] == 1 and owner_n["items"][0]["kind"] == "approval_requested"
    assert client.get(f"{b}/notifications", headers=editor).json()["unread"] == 0  # requester is not told about their own request
    client.post(f"{b}/approvals/{a['id']}/decision", headers=h, json={"decision": "reject", "comment": "No"})
    ed_n = client.get(f"{b}/notifications", headers=editor).json()
    assert ed_n["items"][0]["kind"] == "approval_decided"
    assert client.post(f"{b}/notifications/read", headers=h, json={"ids": [owner_n["items"][0]["id"]]}).json()["marked"] == 1
    assert client.get(f"{b}/notifications", headers=h).json()["unread"] == 0
    assert client.post(f"{b}/notifications/read", headers=editor, json={"ids": [owner_n["items"][0]["id"]]}).json()["marked"] == 0  # cannot touch others'
    assert client.post(f"{b}/notifications/read", headers=editor, json={}).json()["marked"] == 1
    assert client.get(f"{b}/notifications", headers=signup(client, "x@example.com")).status_code == 404


def test_quality_blocks_forbidden_phrase_before_approval(client, owner, monkeypatch):
    h, b, iid, d = setup(client, owner, monkeypatch, FakeWP())
    client.put(f"{b}/profile", headers=h, json={"prohibited_claims": "guaranteed results"})
    client.post(f"{b}/content/{d['id']}/versions", headers=h, json={"body": "We promise Guaranteed Results every time."})
    chk = client.get(f"{b}/content/{d['id']}/check", headers=h).json()
    assert chk["ok"] is False and chk["issues"][0]["code"] == "prohibited_phrase"
    v = client.get(f"{b}/content/{d['id']}", headers=h).json()["versions"][-1]
    r = client.post(f"{b}/approvals", headers=h, json={"version_id": v["id"], "integration_id": iid, "action": "publish_blog"})
    assert r.status_code == 422 and "Content check failed" in r.json()["detail"]


def test_quality_length_duplicates_and_similarity(client, owner):
    h, ws = owner
    b = f"/api/v1/workspaces/{ws}"
    assert client.get(f"{b}/content/{client.post(f'{b}/content', headers=h, json={'kind': 'social_post', 'title': 'S', 'body': 'x' * 3001}).json()['id']}/check", headers=h).json()["issues"][0]["code"] == "too_long"
    text = " ".join(f"word{i}" for i in range(60))
    a = client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "Original", "body": text}).json()
    dup = client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "Copy", "body": text}).json()
    codes = [i["code"] for i in client.get(f"{b}/content/{dup['id']}/check", headers=h).json()["issues"]]
    assert "duplicate" in codes
    near = client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "Near", "body": text.replace("word30", "changed")}).json()
    issues = client.get(f"{b}/content/{near['id']}/check", headers=h).json()["issues"]
    assert any(i["code"] == "similar" for i in issues)
    assert client.get(f"{b}/content/{a['id']}/check", headers=signup(client, "q@example.com")).status_code == 404


def test_export_markdown_and_escaped_html(client, owner):
    h, ws = owner
    b = f"/api/v1/workspaces/{ws}"
    d = client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "My <post>", "body": "Hi <script>alert(1)</script>\n\nSecond"}).json()
    md = client.get(f"{b}/content/{d['id']}/export?format=md", headers=h)
    assert md.text.startswith("# My <post>") and "attachment" in md.headers["content-disposition"] and md.headers["content-disposition"].endswith('v1.md"')
    html = client.get(f"{b}/content/{d['id']}/export?format=html", headers=h).text
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert client.get(f"{b}/content/{d['id']}/export?format=pdf", headers=h).status_code == 422


def test_operations_metrics_are_measured_and_empty_is_honest(client, owner, monkeypatch):
    h, ws = owner
    empty = client.get(f"/api/v1/workspaces/{ws}/metrics/operations", headers=h).json()
    assert empty["publish_success_rate"] is None and "not marketing performance" in empty["source"]
    fake = FakeWP()
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, h, b, iid, d)
    client.post(f"{b}/approvals/{aid}/execute", headers=h)
    m = client.get(f"{b}/metrics/operations", headers=h).json()
    assert m["executions"] == {"PUBLISHED": 1} and m["publish_success_rate"] == 1.0 and m["approvals"]["APPROVED"] == 1
