from datetime import timedelta

import httpx
import pytest

from app.db.models import ApprovalRequest, ExecutionRecord, utcnow
from app.services import ssrf
from app.services.execution import recover_stuck
from app.workers.scheduler import run_due
from tests.conftest import mock_client
from tests.test_publish_flow import approved, setup


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(ssrf, "resolve", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])


class Site:
    """MOCK WordPress that can lose the response after saving the post. Real WordPress is not tested."""
    def __init__(self, mode="ok", lookup_fails=False):
        self.mode, self.posts, self.calls, self.lookup_fails, self.slugs = mode, [], 0, False, []
        self.lookup_fails = lookup_fails

    def __call__(self, request):
        path = request.url.path
        if path.endswith("/users/me"):
            return httpx.Response(200, json={"name": "bot"})
        if request.method == "GET":  # slug lookup
            if self.lookup_fails:
                return httpx.Response(503)
            slug = request.url.params["slug"]
            return httpx.Response(200, json=[p for p in self.posts if p["slug"] == slug])
        self.calls += 1
        import json
        slug = json.loads(request.content)["slug"]
        self.slugs.append(slug)
        if self.mode == "lost":  # saved on the site, but the answer never arrives
            self.posts.append({"id": 41, "link": "https://blog.example.com/p/41", "status": "publish", "slug": slug})
            return httpx.Response(500)
        if self.mode == "never":  # failed before saving
            return httpx.Response(500)
        self.posts.append({"id": 7, "link": "https://blog.example.com/p/7", "status": "publish", "slug": slug})
        return httpx.Response(201, json={"id": 7, "link": "https://blog.example.com/p/7", "status": "publish"})


def run(client, owner, monkeypatch, site):
    h, b, iid, d = setup(client, owner, monkeypatch, site)
    aid = approved(client, h, b, iid, d)
    r = client.post(f"{b}/approvals/{aid}/execute", headers=h).json()
    return h, b, aid, d, r["execution"]


def test_publish_sends_a_deterministic_slug(client, owner, monkeypatch):
    site = Site()
    h, b, aid, d, ex = run(client, owner, monkeypatch, site)
    assert ex["status"] == "PUBLISHED" and site.slugs[0].startswith("na-") and len(site.slugs[0]) == 15


def test_lost_response_is_reconciled_as_published_without_a_second_post(client, owner, monkeypatch):
    site = Site("lost")
    h, b, aid, d, ex = run(client, owner, monkeypatch, site)
    assert ex["status"] == "UNCLEAR"
    r = client.post(f"{b}/approvals/{aid}/reconcile", headers=h).json()
    assert r["outcome"] == "published" and r["execution"]["status"] == "PUBLISHED" and r["execution"]["external_id"] == "41"
    assert site.calls == 1 and len(site.posts) == 1  # checked, never re-posted
    assert client.get(f"{b}/content/{d['id']}", headers=h).json()["status"] == "published"
    assert client.post(f"{b}/approvals/{aid}/reconcile", headers=h).status_code == 409  # nothing left to check


def test_nothing_on_site_means_failed_and_safe_to_retry(client, owner, monkeypatch):
    site = Site("never")
    h, b, aid, d, ex = run(client, owner, monkeypatch, site)
    assert ex["status"] == "UNCLEAR"
    assert client.post(f"{b}/approvals/{aid}/execute", headers=h).json()["repeated"] is True  # no retry while unclear
    r = client.post(f"{b}/approvals/{aid}/reconcile", headers=h).json()
    assert r["outcome"] == "not_found" and r["execution"]["status"] == "FAILED"
    site.mode = "ok"
    assert client.post(f"{b}/approvals/{aid}/execute", headers=h).json()["execution"]["status"] == "PUBLISHED"
    assert site.calls == 2


def test_failed_lookup_leaves_the_result_unclear(client, owner, monkeypatch):
    site = Site("lost", lookup_fails=True)
    h, b, aid, d, ex = run(client, owner, monkeypatch, site)
    r = client.post(f"{b}/approvals/{aid}/reconcile", headers=h).json()
    assert r["outcome"] == "lookup_failed" and r["execution"]["status"] == "UNCLEAR"


def test_reconcile_permissions_and_tenancy(client, owner, monkeypatch):
    from tests.conftest import signup
    site = Site("lost")
    h, b, aid, d, ex = run(client, owner, monkeypatch, site)
    viewer = signup(client, "v-fc@example.com")
    client.post(f"{b}/members", headers=h, json={"email": "v-fc@example.com", "role": "viewer"})
    assert client.post(f"{b}/approvals/{aid}/reconcile", headers=viewer).status_code == 403
    assert client.post(f"{b}/approvals/{aid}/reconcile", headers=signup(client, "o-fc@example.com")).status_code == 404


def test_stuck_executing_job_becomes_unclear_after_the_lease(client, owner, monkeypatch, db_session):
    site = Site()
    h, b, iid, d = setup(client, owner, monkeypatch, site)
    aid = approved(client, h, b, iid, d)
    a = db_session.get(ApprovalRequest, aid)
    db_session.add(ExecutionRecord(workspace_id=a.workspace_id, approval_id=aid, idempotency_key=f"{aid}:{a.content_hash}", status="EXECUTING"))
    db_session.commit()
    assert recover_stuck(db_session) == 0  # fresh, still within the lease
    # a second call must not start a new publish while another attempt is running
    assert client.post(f"{b}/approvals/{aid}/execute", headers=h).json()["repeated"] is True and site.calls == 0
    rec = db_session.query(ExecutionRecord).one()
    rec.updated_at = utcnow() - timedelta(minutes=6)
    db_session.commit()
    run_due(db_session)
    assert db_session.query(ExecutionRecord).one().status == "UNCLEAR"
    kinds = [n["kind"] for n in client.get(f"{b}/notifications", headers=h).json()["items"]]
    assert "publish_unclear" in kinds


def test_jobs_endpoint_states_and_next_actions(client, owner, monkeypatch):
    site = Site("lost")
    h, b, aid, d, ex = run(client, owner, monkeypatch, site)
    j = client.get(f"{b}/jobs", headers=h).json()
    assert j["counts"] == {"unclear": 1}
    item = j["items"][0]
    assert item["state"] == "unclear" and item["can_check_site"] and not item["retry_eligible"] and "Check the site" in item["next_action"]
    assert client.get(f"{b}/jobs?state=published", headers=h).json()["items"] == []
    assert client.get(f"{b}/jobs?state=bogus", headers=h).status_code == 422
    client.post(f"{b}/approvals/{aid}/reconcile", headers=h)
    assert client.get(f"{b}/jobs", headers=h).json()["counts"] == {"published": 1}


def test_jobs_are_tenant_isolated_and_pending_blocked_shown(client, owner, monkeypatch):
    from tests.conftest import signup
    site = Site()
    h, b, iid, d = setup(client, owner, monkeypatch, site)
    aid = approved(client, h, b, iid, d)
    assert client.get(f"{b}/jobs", headers=h).json()["counts"] == {"pending": 1}
    assert client.get(f"{b}/jobs", headers=signup(client, "j-other@example.com")).status_code == 404
