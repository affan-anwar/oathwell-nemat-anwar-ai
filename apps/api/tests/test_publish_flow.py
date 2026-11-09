import httpx
import pytest

from app.integrations import wordpress as wp
from app.services import ssrf
from tests.conftest import mock_client, signup


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(ssrf, "resolve", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])


class FakeWP:
    """MOCK WordPress. Proves our logic only. Real WordPress has NOT been tested."""
    def __init__(self, post=None):
        self.calls, self.post, self.auth_ok = 0, post, True

    def __call__(self, request):
        if request.url.path.endswith("/users/me"):
            return httpx.Response(200 if self.auth_ok else 401, json={"name": "editor-bot"})
        self.calls += 1
        if self.post:
            return self.post(request)
        return httpx.Response(201, json={"id": 77, "link": "https://blog.example.com/p/77", "status": "publish"})


def setup(client, owner, monkeypatch, fake):
    h, ws = owner
    monkeypatch.setattr(wp, "http_client", lambda: mock_client(fake))
    b = f"/api/v1/workspaces/{ws}"
    i = client.post(f"{b}/integrations/wordpress", headers=h, json={
        "label": "Blog", "site_url": "https://blog.example.com", "username": "bot", "app_password": "abcd efgh ijkl"}).json()
    assert "app_password" not in str(i) and "abcd" not in str(i)
    assert client.post(f"{b}/integrations/{i['id']}/test", headers=h).json()["status"] == "connected"
    d = client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "Post", "body": "Hello"}).json()
    return h, b, i["id"], d


def approved(client, h, b, iid, d, n=0):
    a = client.post(f"{b}/approvals", headers=h, json={"version_id": d["versions"][n]["id"], "integration_id": iid,
                                                      "action": "publish_blog"})
    assert a.status_code == 201, a.text
    r = client.post(f"{b}/approvals/{a.json()['id']}/decision", headers=h, json={"decision": "approve"})
    assert r.json()["status"] == "APPROVED"
    return a.json()["id"]


def test_ssrf_blocked(client, owner, monkeypatch):
    h, ws = owner
    url = f"/api/v1/workspaces/{ws}/integrations/wordpress"
    mk = lambda u: client.post(url, headers=h, json={"label": "x", "site_url": u, "username": "u", "app_password": "12345678"})
    monkeypatch.setattr(ssrf, "resolve", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))])
    assert mk("https://localhost").status_code == 422
    for ip in ["10.0.0.5", "169.254.169.254", "192.168.1.1", "::1"]:
        monkeypatch.setattr(ssrf, "resolve", lambda *a, ip=ip, **k: [(2, 1, 6, "", (ip, 443))])
        assert mk("https://internal.example.com").status_code == 422, ip
    assert mk("http://blog.example.com").status_code == 422
    assert mk("https://user:pw@blog.example.com").status_code == 422
    assert mk("ftp://blog.example.com").status_code == 422


def test_no_approval_no_publish(client, owner, monkeypatch):
    fake = FakeWP()
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    a = client.post(f"{b}/approvals", headers=h, json={"version_id": d["versions"][0]["id"], "integration_id": iid, "action": "publish_blog"}).json()
    assert client.post(f"{b}/approvals/{a['id']}/execute", headers=h).status_code == 409  # still pending
    client.post(f"{b}/approvals/{a['id']}/decision", headers=h, json={"decision": "reject"})
    assert client.post(f"{b}/approvals/{a['id']}/execute", headers=h).status_code == 409
    assert fake.calls == 0


def test_full_flow_and_retry_does_not_duplicate(client, owner, monkeypatch):
    fake = FakeWP()
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, h, b, iid, d)
    r1 = client.post(f"{b}/approvals/{aid}/execute", headers=h).json()
    r2 = client.post(f"{b}/approvals/{aid}/execute", headers=h).json()
    assert r1["execution"]["status"] == "PUBLISHED" and r1["execution"]["external_id"] == "77"
    assert r2["repeated"] is True and r2["execution"]["id"] == r1["execution"]["id"]
    assert fake.calls == 1
    assert client.get(f"{b}/content/{d['id']}", headers=h).json()["status"] == "published"
    actions = [e["action"] for e in client.get(f"{b}/audit", headers=h).json()]
    assert "execution.run" in actions and "approval.approve" in actions and "approval.request" in actions


def test_edit_after_approval_invalidates(client, owner, monkeypatch):
    fake = FakeWP()
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, h, b, iid, d)
    client.post(f"{b}/content/{d['id']}/versions", headers=h, json={"body": "Hello, edited"})
    assert client.get(f"{b}/approvals/{aid}", headers=h).json()["status"] == "INVALIDATED"
    assert client.post(f"{b}/approvals/{aid}/execute", headers=h).status_code == 409
    old = client.post(f"{b}/approvals", headers=h, json={"version_id": d["versions"][0]["id"], "integration_id": iid, "action": "publish_blog"})
    assert old.status_code == 409  # only the latest version can be approved
    assert fake.calls == 0


def test_revoke_pause_disconnect_block(client, owner, monkeypatch):
    fake = FakeWP()
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, h, b, iid, d)
    client.post(f"{b}/pause", headers=h, json={"paused": True})
    assert "paused" in client.post(f"{b}/approvals/{aid}/execute", headers=h).json()["detail"]
    client.post(f"{b}/pause", headers=h, json={"paused": False})
    client.delete(f"{b}/integrations/{iid}", headers=h)
    assert "not connected" in client.post(f"{b}/approvals/{aid}/execute", headers=h).json()["detail"]
    assert client.post(f"{b}/integrations/{iid}/test", headers=h).status_code == 409
    client.post(f"{b}/approvals/{aid}/revoke", headers=h)
    assert client.post(f"{b}/approvals/{aid}/execute", headers=h).status_code == 409
    assert fake.calls == 0


def test_editor_cannot_approve_and_other_tenant_cannot_execute(client, owner, monkeypatch):
    fake = FakeWP()
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    editor = signup(client, "ed@example.com")
    client.post(f"{b}/members", headers=h, json={"email": "ed@example.com", "role": "editor"})
    a = client.post(f"{b}/approvals", headers=editor, json={"version_id": d["versions"][0]["id"], "integration_id": iid, "action": "publish_blog"}).json()
    assert client.post(f"{b}/approvals/{a['id']}/decision", headers=editor, json={"decision": "approve"}).status_code == 403
    client.post(f"{b}/approvals/{a['id']}/decision", headers=h, json={"decision": "approve"})
    other = signup(client, "evil@example.com")
    ws2 = client.post("/api/v1/workspaces", headers=other, json={"name": "Evil"}).json()["id"]
    assert client.post(f"{b}/approvals/{a['id']}/execute", headers=other).status_code == 404
    assert client.post(f"/api/v1/workspaces/{ws2}/approvals/{a['id']}/execute", headers=other).status_code == 404
    assert client.post(f"/api/v1/workspaces/{ws2}/approvals/{a['id']}/decision", headers=other, json={"decision": "approve"}).status_code == 404
    assert fake.calls == 0


def test_provider_failure_unclear_and_retry_rules(client, owner, monkeypatch):
    fake = FakeWP(post=lambda r: httpx.Response(500))
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, h, b, iid, d)
    r1 = client.post(f"{b}/approvals/{aid}/execute", headers=h).json()
    assert r1["execution"]["status"] == "UNCLEAR"  # a 5xx never counts as success
    r2 = client.post(f"{b}/approvals/{aid}/execute", headers=h).json()
    assert r2["repeated"] and fake.calls == 1  # unclear is not retried blindly
    assert client.get(f"{b}/content/{d['id']}", headers=h).json()["status"] != "published"


def test_rejected_by_provider_is_failed_and_can_retry(client, owner, monkeypatch):
    state = {"n": 0}

    def post(r):
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(403, json={})
        return httpx.Response(201, json={"id": 5, "link": "https://blog.example.com/p/5", "status": "publish"})

    h, b, iid, d = setup(client, owner, monkeypatch, FakeWP(post=post))
    aid = approved(client, h, b, iid, d)
    assert client.post(f"{b}/approvals/{aid}/execute", headers=h).json()["execution"]["status"] == "FAILED"
    assert client.post(f"{b}/approvals/{aid}/execute", headers=h).json()["execution"]["status"] == "PUBLISHED"


def test_unconfirmed_2xx_is_not_success(client, owner, monkeypatch):
    fake = FakeWP(post=lambda r: httpx.Response(201, json={"id": 9}))  # no link, no status
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, h, b, iid, d)
    assert client.post(f"{b}/approvals/{aid}/execute", headers=h).json()["execution"]["status"] == "UNCLEAR"


def test_failed_connection_test(client, owner, monkeypatch):
    fake = FakeWP()
    fake.auth_ok = False
    h, ws = owner
    monkeypatch.setattr(wp, "http_client", lambda: mock_client(fake))
    b = f"/api/v1/workspaces/{ws}"
    i = client.post(f"{b}/integrations/wordpress", headers=h, json={"label": "B", "site_url": "https://blog.example.com", "username": "u", "app_password": "12345678"}).json()
    assert client.post(f"{b}/integrations/{i['id']}/test", headers=h).json()["status"] == "failed"
