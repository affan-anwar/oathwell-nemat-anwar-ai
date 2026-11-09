from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.db.models import ApprovalRequest, Notification, utcnow
from app.services import ssrf
from app.workers.scheduler import run_due
from tests.test_publish_flow import FakeWP, setup  # FakeWP is a MOCK. Real WordPress is not tested.


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(ssrf, "resolve", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])


def when(hours=3.0, tz=timezone.utc):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).astimezone(tz).isoformat()


def utc_of(hours):
    return utcnow() + timedelta(hours=hours)


def request(client, h, b, iid, d, at=None, n=0):
    body = {"version_id": d["versions"][n]["id"], "integration_id": iid, "action": "publish_blog"}
    if at:
        body["scheduled_at"] = at
    return client.post(f"{b}/approvals", headers=h, json=body)


def approve(client, h, b, aid):
    return client.post(f"{b}/approvals/{aid}/decision", headers=h, json={"decision": "approve"})


def scheduled(client, owner, monkeypatch, fake=None, hours=3):
    fake = fake or FakeWP()
    h, b, iid, d = setup(client, owner, monkeypatch, fake)
    a = request(client, h, b, iid, d, when(hours)).json()
    assert approve(client, h, b, a["id"]).json()["status"] == "APPROVED"
    return fake, h, b, iid, d, a["id"]


def test_schedule_validation_and_time_zone(client, owner, monkeypatch):
    h, b, iid, d = setup(client, owner, monkeypatch, FakeWP())
    assert request(client, h, b, iid, d, (datetime.now() + timedelta(hours=3)).isoformat()).status_code == 422  # no offset
    assert request(client, h, b, iid, d, when(-1)).status_code == 422
    assert request(client, h, b, iid, d, when(24 * 400)).status_code == 422
    ist = timezone(timedelta(hours=5, minutes=30))
    r = request(client, h, b, iid, d, when(3, ist))
    assert r.status_code == 201
    stored = datetime.fromisoformat(r.json()["scheduled_at"])
    assert abs((stored - utc_of(3)).total_seconds()) < 5  # IST input stored as UTC


def test_conflict_detection(client, owner, monkeypatch):
    h, b, iid, d = setup(client, owner, monkeypatch, FakeWP())
    d2 = client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "Second", "body": "Other text"}).json()
    d3 = client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "Third", "body": "More text"}).json()
    assert request(client, h, b, iid, d, when(3)).status_code == 201
    assert request(client, h, b, iid, d2, when(3.17)).status_code == 409  # 10 minutes apart
    assert request(client, h, b, iid, d3, when(3.5)).status_code == 201  # 30 minutes apart


def test_manual_publish_blocked_until_due(client, owner, monkeypatch):
    fake, h, b, iid, d, aid = scheduled(client, owner, monkeypatch)
    r = client.post(f"{b}/approvals/{aid}/execute", headers=h)
    assert r.status_code == 409 and "scheduled for" in r.json()["detail"] and fake.calls == 0


def test_scheduler_publishes_once_at_due_time(client, owner, monkeypatch, db_session):
    fake, h, b, iid, d, aid = scheduled(client, owner, monkeypatch)
    assert run_due(db_session, now=utc_of(0)) == [] and fake.calls == 0  # not due yet
    res = run_due(db_session, now=utc_of(3.02))
    assert len(res) == 1 and res[0][1].record.status == "PUBLISHED" and res[0][1].record.trigger == "scheduler"
    assert run_due(db_session, now=utc_of(3.5)) == [] and fake.calls == 1  # never twice
    ev = [e for e in client.get(f"{b}/audit", headers=h).json() if e["action"] == "execution.run"]
    assert ev[0]["actor_id"] is None and ev[0]["detail"]["trigger"] == "scheduler"
    notes = client.get(f"{b}/notifications", headers=h).json()["items"]
    assert "publish_succeeded" in [n["kind"] for n in notes]


def test_paused_workspace_blocks_then_resumes(client, owner, monkeypatch, db_session):
    fake, h, b, iid, d, aid = scheduled(client, owner, monkeypatch)
    client.post(f"{b}/pause", headers=h, json={"paused": True})
    for _ in range(3):
        run_due(db_session, now=utc_of(3.02))
    assert fake.calls == 0
    blocked = [e for e in client.get(f"{b}/audit", headers=h).json() if e["action"] == "execution.blocked"]
    assert len(blocked) == 1 and "paused" in blocked[0]["detail"]["reason"]  # logged once, not every poll
    client.post(f"{b}/pause", headers=h, json={"paused": False})
    assert run_due(db_session, now=utc_of(3.03))[0][1].record.status == "PUBLISHED"


def test_expired_approval_is_marked_and_notified(client, owner, monkeypatch, db_session):
    fake, h, b, iid, d, aid = scheduled(client, owner, monkeypatch)
    a = db_session.get(ApprovalRequest, aid)
    a.expires_at = utc_of(1)
    db_session.commit()
    run_due(db_session, now=utc_of(3.02))
    assert client.get(f"{b}/approvals/{aid}", headers=h).json()["status"] == "EXPIRED" and fake.calls == 0
    assert "approval_expired" in [n["kind"] for n in client.get(f"{b}/notifications", headers=h).json()["items"]]


def test_failed_scheduled_post_is_not_retried_automatically(client, owner, monkeypatch, db_session):
    fake = FakeWP(post=lambda r: httpx.Response(403, json={}))
    fake_, h, b, iid, d, aid = scheduled(client, owner, monkeypatch, fake)
    assert run_due(db_session, now=utc_of(3.02))[0][1].record.status == "FAILED"
    run_due(db_session, now=utc_of(4))
    assert fake.calls == 1
    kinds = [n["kind"] for n in client.get(f"{b}/notifications", headers=h).json()["items"]]
    assert "publish_failed" in kinds


def test_reschedule_rules(client, owner, monkeypatch):
    h, b, iid, d = setup(client, owner, monkeypatch, FakeWP())
    a = request(client, h, b, iid, d, when(3)).json()
    r = client.patch(f"{b}/approvals/{a['id']}/schedule", headers=h, json={"scheduled_at": when(5)})
    assert r.status_code == 200 and r.json()["scheduled_at"] != a["scheduled_at"]
    assert client.patch(f"{b}/approvals/{a['id']}/schedule", headers=h, json={"scheduled_at": None}).json()["scheduled_at"] is None
    approve(client, h, b, a["id"])
    assert client.patch(f"{b}/approvals/{a['id']}/schedule", headers=h, json={"scheduled_at": when(6)}).status_code == 409


def test_cannot_approve_after_scheduled_time_passed(client, owner, monkeypatch, db_session):
    h, b, iid, d = setup(client, owner, monkeypatch, FakeWP())
    a = request(client, h, b, iid, d, when(3)).json()
    row = db_session.get(ApprovalRequest, a["id"])
    row.scheduled_at = utc_of(-1)
    db_session.commit()
    assert approve(client, h, b, a["id"]).status_code == 409


def test_calendar_shows_only_persisted_schedules_and_isolates_tenants(client, owner, monkeypatch):
    fake, h, b, iid, d, aid = scheduled(client, owner, monkeypatch)
    day = utc_of(3).date()
    r = client.get(f"{b}/calendar?start={day - timedelta(days=1)}&end={day + timedelta(days=1)}", headers=h).json()
    assert [i["id"] for i in r["scheduled"]] == [aid] and r["times_are"] == "UTC"
    far = client.get(f"{b}/calendar?start={day + timedelta(days=30)}&end={day + timedelta(days=31)}", headers=h).json()
    assert far["scheduled"] == []
    assert client.get(f"{b}/calendar?start={day}&end={day + timedelta(days=90)}", headers=h).status_code == 422
    from tests.conftest import signup
    other = signup(client, "cal-other@example.com")
    assert client.get(f"{b}/calendar?start={day}&end={day}", headers=other).status_code == 404
