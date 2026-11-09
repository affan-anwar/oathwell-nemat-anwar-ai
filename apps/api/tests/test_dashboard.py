from datetime import timedelta

import pytest

from app.db.models import Campaign, ContentDocument, utcnow
from app.services import ssrf
from app.workers.scheduler import run_due
from tests.conftest import signup
from tests.test_failure_center import Site, run
from tests.test_publish_flow import FakeWP, approved, setup  # FakeWP and Site are MOCKS
from tests.test_scheduling import scheduled


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(ssrf, "resolve", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])


def dash(client, h, ws, days=7):
    return client.get(f"/api/v1/workspaces/{ws}/dashboard?days={days}", headers=h).json()


def test_empty_workspace_shows_honest_unavailable_states(client, owner):
    h, ws = owner
    d = dash(client, h, ws)
    assert d["agent"]["state"] == "Unavailable" and "not running" in d["agent"]["reason"] and d["agent"]["next_task"] is None
    assert d["kpis"]["engagement_rate"]["state"] == "unavailable"  # never invented
    assert d["kpis"]["campaigns"]["total"] == 0 and d["kpis"]["content_created"] == {"value": 0, "previous": 0}
    assert len(d["series"]) == 7 and all(p["content_created"] == 0 and p["posts_published"] == 0 for p in d["series"])
    assert d["campaigns"] == d["upcoming"] == d["integrations"] == []


def test_agent_state_comes_from_real_signals(client, owner, monkeypatch, db_session):
    h, ws = owner
    assert dash(client, h, ws)["agent"]["state"] == "Unavailable"
    run_due(db_session)  # the worker reports in
    d = dash(client, h, ws)
    assert d["agent"]["state"] == "Running" and d["agent"]["worker_last_seen"]
    client.post(f"/api/v1/workspaces/{ws}/pause", headers=h, json={"paused": True})
    assert dash(client, h, ws)["agent"]["state"] == "Paused"  # paused wins
    client.post(f"/api/v1/workspaces/{ws}/pause", headers=h, json={"paused": False})
    h2, b, aid, doc, ex = run(client, owner, monkeypatch, Site("lost"))
    assert ex["status"] == "UNCLEAR" and dash(client, h, ws)["agent"]["state"] == "Needs attention"


def test_a_stale_heartbeat_is_not_running(client, owner, db_session):
    h, ws = owner
    run_due(db_session, now=utcnow() - timedelta(minutes=10))
    assert dash(client, h, ws)["agent"]["state"] == "Unavailable"


def test_counts_series_and_previous_window(client, owner, monkeypatch, db_session):
    h, ws = owner
    b = f"/api/v1/workspaces/{ws}"
    for t in ("A", "B"):
        client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": t, "body": "text " * 20})
    old = db_session.query(ContentDocument).first()
    old.created_at = utcnow() - timedelta(days=10)
    db_session.commit()
    d = dash(client, h, ws)
    assert d["kpis"]["content_created"] == {"value": 1, "previous": 1}
    assert d["series"][-1]["content_created"] == 1 and sum(p["content_created"] for p in d["series"]) == 1
    fake = FakeWP()
    h, b, iid, doc = setup(client, owner, monkeypatch, fake)
    aid = approved(client, h, b, iid, doc)
    client.post(f"{b}/approvals/{aid}/execute", headers=h)
    d = dash(client, h, ws)
    assert d["kpis"]["posts_published"]["value"] == 1 and d["series"][-1]["posts_published"] == 1
    assert len(dash(client, h, ws, 30)["series"]) == 30
    assert client.get(f"{b}/dashboard?days=0", headers=h).status_code == 422
    assert client.get(f"{b}/dashboard?days=91", headers=h).status_code == 422


def test_campaign_progress_is_published_over_linked_content(client, owner, db_session):
    h, ws = owner
    b = f"/api/v1/workspaces/{ws}"
    c1 = client.post(f"{b}/campaigns", headers=h, json={"name": "With content"}).json()["id"]
    client.post(f"{b}/campaigns", headers=h, json={"name": "Empty one"})
    gone = client.post(f"{b}/campaigns", headers=h, json={"name": "Archived one"}).json()["id"]
    client.post(f"{b}/campaigns/{gone}/transition", headers=h, json={"to": "ARCHIVED"})
    for t in ("p1", "p2"):
        client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": t, "body": "x", "campaign_id": c1})
    db_session.query(ContentDocument).filter_by(title="p1").one().status = "published"
    db_session.commit()
    by = {c["name"]: c for c in dash(client, h, ws)["campaigns"]}
    assert set(by) == {"With content", "Empty one"}  # archived is not active
    assert by["With content"]["progress"] == 0.5 and by["With content"]["content_count"] == 2
    assert by["Empty one"]["progress"] is None  # unknown, not zero


def test_upcoming_and_next_task_and_integrations_without_secrets(client, owner, monkeypatch):
    fake, h, b, iid, d, aid = scheduled(client, owner, monkeypatch)
    ws = b.split("/")[-1]
    out = dash(client, h, ws)
    assert [u["approval_id"] for u in out["upcoming"]] == [aid] and out["agent"]["next_task"]["approval_id"] == aid
    assert out["integrations"][0]["status"] == "connected" and "abcd" not in str(out) and "secret" not in str(out).lower()


def test_dashboard_roles_and_isolation(client, owner):
    h, ws = owner
    v = signup(client, "dv@example.com")
    client.post(f"/api/v1/workspaces/{ws}/members", headers=h, json={"email": "dv@example.com", "role": "viewer"})
    assert client.get(f"/api/v1/workspaces/{ws}/dashboard", headers=v).status_code == 200
    assert client.get(f"/api/v1/workspaces/{ws}/dashboard", headers=signup(client, "do@example.com")).status_code == 404
    assert client.get(f"/api/v1/workspaces/{ws}/dashboard").status_code == 401


def test_activity_feed_is_real_whitelisted_and_shows_reasons(client, owner, monkeypatch):
    h, ws = owner
    b = f"/api/v1/workspaces/{ws}"
    client.post(f"{b}/campaigns", headers=h, json={"name": "Launch"})
    fake, h, b, iid, d, aid = scheduled(client, owner, monkeypatch)
    client.post(f"{b}/pause", headers=h, json={"paused": True})
    client.post(f"{b}/approvals/{aid}/execute", headers=h)  # blocked
    feed = client.get(f"{b}/activity", headers=h).json()
    titles = [e["title"] for e in feed]
    assert "Campaign created" in titles and "Content approved" in titles and "Workspace paused" in titles
    blocked = [e for e in feed if e["title"] == "Publishing blocked"][0]
    assert blocked["outcome"] == "blocked" and "paused" in blocked["reason"]
    assert all(set(e) == {"id", "action", "title", "outcome", "created_at", "reason", "automated"} for e in feed)  # no raw details
    assert client.get(f"{b}/activity?limit=1", headers=h).json().__len__() == 1
    assert client.get(f"{b}/activity", headers=signup(client, "ao@example.com")).status_code == 404


def test_search_matches_escapes_wildcards_and_isolates(client, owner):
    h, ws = owner
    b = f"/api/v1/workspaces/{ws}"
    client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "50% off sale", "body": "x"})
    client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "50x off sale", "body": "x"})
    client.post(f"{b}/campaigns", headers=h, json={"name": "Eid Offers"})
    assert [c["title"] for c in client.get(f"{b}/search?q=50%25", headers=h).json()["content"]] == ["50% off sale"]  # % is not a wildcard
    assert client.get(f"{b}/search?q=__", headers=h).json() == {"campaigns": [], "content": []}  # _ is not a wildcard
    assert client.get(f"{b}/search?q=eid", headers=h).json()["campaigns"][0]["name"] == "Eid Offers"  # case-insensitive
    assert client.get(f"{b}/search?q=e", headers=h).status_code == 422
    other = signup(client, "so@example.com")
    ws2 = client.post("/api/v1/workspaces", headers=other, json={"name": "Other"}).json()["id"]
    client.post(f"/api/v1/workspaces/{ws2}/content", headers=other, json={"kind": "blog", "title": "secret plan", "body": "x"})
    assert client.get(f"{b}/search?q=secret", headers=h).json()["content"] == []
    assert client.get(f"{b}/search?q=secret", headers=other).status_code == 404


def test_quick_stats_and_agent_counts_are_counted_not_invented(client, owner, team_agents, monkeypatch):
    h, ws = owner
    fake = FakeWP()
    h, b, iid, doc = setup(client, owner, monkeypatch, fake)
    d = dash(client, h, ws)
    assert d["agents"] == {"active": 1, "total": 2} and d["quick"] == {"active_campaigns": 0, "content_in_review": 0, "scheduled": 0, "published_today": 0}
    aid = approved(client, h, b, iid, doc)  # approved but not published yet
    assert dash(client, h, ws)["quick"]["published_today"] == 0  # approval alone publishes nothing
    client.post(f"{b}/approvals/{aid}/execute", headers=h)
    q = dash(client, h, ws)["quick"]
    assert q["published_today"] == 1


@pytest.fixture()
def team_agents(client, owner):
    h, ws = owner
    for email, role in (("qa-sa@example.com", "super_agent"), ("qa-ca@example.com", "content_agent")):
        signup(client, email)
        client.post(f"/api/v1/workspaces/{ws}/members", headers=h, json={"email": email, "role": role})
    uid = [m["user_id"] for m in client.get(f"/api/v1/workspaces/{ws}/members", headers=h).json() if m["email"] == "qa-ca@example.com"][0]
    client.patch(f"/api/v1/workspaces/{ws}/members/{uid}", headers=h, json={"suspended": True})  # a suspended agent is not active
