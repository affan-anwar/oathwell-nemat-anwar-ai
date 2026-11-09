import pytest
from sqlalchemy.exc import IntegrityError

from app.core.permissions import ADMIN_MANAGEABLE, DELEGABLE, OWNER_ONLY, ROLE_PERMS, ROLES, can_assign, has_perm
from app.db.models import Membership
from app.services import ssrf
from tests.conftest import signup
from tests.test_publish_flow import FakeWP, approved, setup  # FakeWP is a MOCK site

TEAM = [r for r in ROLES if r != "owner"]


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(ssrf, "resolve", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])


@pytest.fixture()
def team(client, owner):
    """One person in every role, all added by the Owner through the real API."""
    oh, ws = owner
    out = {"owner": oh}
    for r in TEAM:
        out[r] = signup(client, f"{r}@example.com")
        assert client.post(f"/api/v1/workspaces/{ws}/members", headers=oh, json={"email": f"{r}@example.com", "role": r}).status_code == 201
    return out


def uid(client, h):
    return client.get("/api/v1/auth/me", headers=h).json()["id"]


ACTIONS = ["read", "campaign.write", "content.write", "brand.write", "member.manage", "automation.pause", "audit.read", "integration.manage", "admin.delegate", "emergency.shutdown"]
ALLOWED = {
    "owner": set(ACTIONS), "admin": set(ACTIONS) - {"admin.delegate", "emergency.shutdown"},
    "super_agent": {"read", "campaign.write", "content.write"}, "editor": {"read", "campaign.write", "content.write", "brand.write"},
    "viewer": {"read"}, "research_agent": {"read"}, "analytics_agent": {"read"}, "content_agent": {"read", "content.write"}, "publishing_agent": {"read"},
}


def attempt(client, ws, h, action):
    b = f"/api/v1/workspaces/{ws}"
    return {
        "read": lambda: client.get(f"{b}/campaigns", headers=h),
        "campaign.write": lambda: client.post(f"{b}/campaigns", headers=h, json={"name": "c"}),
        "content.write": lambda: client.post(f"{b}/content", headers=h, json={"kind": "blog", "title": "t", "body": "b"}),
        "brand.write": lambda: client.put(f"{b}/profile", headers=h, json={"industry": "x"}),
        "member.manage": lambda: client.post(f"{b}/members", headers=h, json={"email": "spare@example.com", "role": "viewer"}),
        "automation.pause": lambda: client.post(f"{b}/pause", headers=h, json={"paused": False}),
        "audit.read": lambda: client.get(f"{b}/audit", headers=h),
        "integration.manage": lambda: client.post(f"{b}/integrations/wordpress", headers=h, json={"label": "l", "site_url": "https://blog.example.com", "username": "u", "app_password": "12345678"}),
        "admin.delegate": lambda: client.put(f"{b}/admin-permissions", headers=h, json={"revoked": []}),
        "emergency.shutdown": lambda: client.post(f"{b}/emergency-shutdown", headers=h),
    }[action]()


@pytest.mark.parametrize("role", ROLES)
def test_role_matrix_is_enforced_by_the_server(client, owner, team, role):
    _, ws = owner
    signup(client, "spare@example.com")
    for action in ACTIONS:
        r = attempt(client, ws, team[role], action)
        if action in ALLOWED[role]:
            assert r.status_code not in (403, 404), f"{role} should be allowed {action}, got {r.status_code} {r.text}"
        else:
            assert r.status_code == 403, f"{role} must be denied {action}, got {r.status_code}"


def test_permission_table_invariants():
    assert all(has_perm("owner", p) for r in ROLE_PERMS.values() for p in r)
    for role in ROLES:
        if role != "owner":
            assert not set(OWNER_ONLY) & ROLE_PERMS[role], role
    for agent in ("research_agent", "analytics_agent", "content_agent", "publishing_agent", "super_agent"):
        assert not ROLE_PERMS[agent] & {"approval.decide", "member.manage", "integration.manage", "brand.write", "admin.delegate"}, agent
    assert "approval.decide" not in ROLE_PERMS["editor"] and not has_perm("nobody", "read")  # deny by default


def test_can_assign_rules():
    assert can_assign("owner", "viewer", "admin") and not can_assign("owner", "owner", "viewer") and not can_assign("owner", "viewer", "owner")
    assert can_assign("admin", None, "editor") and not can_assign("admin", None, "admin") and not can_assign("admin", "admin", "viewer")
    assert not can_assign("admin", "viewer", "editor", ["member.manage"]) and not can_assign("editor", None, "viewer") and not can_assign("super_agent", None, "viewer")
    assert ADMIN_MANAGEABLE.isdisjoint({"admin", "owner", "super_agent"}) and set(DELEGABLE) <= ROLE_PERMS["admin"]


def test_nobody_can_demote_suspend_or_remove_the_owner(client, owner, team):
    oh, ws = owner
    b, oid = f"/api/v1/workspaces/{ws}/members", uid(client, oh)
    for who in ("admin", "owner"):
        assert client.patch(f"{b}/{oid}", headers=team[who], json={"role": "viewer"}).status_code == 403
        assert client.patch(f"{b}/{oid}", headers=team[who], json={"suspended": True}).status_code == 403
        assert client.delete(f"{b}/{oid}", headers=team[who]).status_code == 403
    assert client.get(f"/api/v1/workspaces/{ws}/campaigns", headers=oh).status_code == 200
    assert [m["role"] for m in client.get(b, headers=oh).json() if m["user_id"] == oid] == ["owner"]


def test_ownership_cannot_be_assigned_through_the_api(client, owner, team):
    oh, ws = owner
    b = f"/api/v1/workspaces/{ws}/members"
    assert client.post(b, headers=oh, json={"email": "spare@example.com", "role": "owner"}).status_code == 422
    assert client.patch(f"{b}/{uid(client, team['viewer'])}", headers=oh, json={"role": "owner"}).status_code == 422
    assert client.patch(f"{b}/{uid(client, team['admin'])}", headers=team["admin"], json={"role": "owner"}).status_code in (403, 422)


def test_admin_limits_and_privilege_escalation_attempts(client, owner, team):
    oh, ws = owner
    b = f"/api/v1/workspaces/{ws}/members"
    signup(client, "spare@example.com")
    ah = team["admin"]
    assert client.post(b, headers=ah, json={"email": "spare@example.com", "role": "admin"}).status_code == 403
    assert client.post(b, headers=ah, json={"email": "spare@example.com", "role": "super_agent"}).status_code == 403
    assert client.patch(f"{b}/{uid(client, team['editor'])}", headers=ah, json={"role": "admin"}).status_code == 403
    assert client.patch(f"{b}/{uid(client, team['super_agent'])}", headers=ah, json={"suspended": True}).status_code == 403
    assert client.delete(f"{b}/{uid(client, team['super_agent'])}", headers=ah).status_code == 403
    assert client.patch(f"{b}/{uid(client, ah)}", headers=ah, json={"role": "editor"}).status_code == 403
    assert client.patch(f"{b}/{uid(client, team['viewer'])}", headers=ah, json={"role": "editor"}).status_code == 200
    assert client.patch(f"{b}/{uid(client, team['content_agent'])}", headers=ah, json={"suspended": True}).status_code == 200
    for who in ("editor", "viewer", "super_agent", "content_agent", "publishing_agent"):
        assert client.patch(f"{b}/{uid(client, team['analytics_agent'])}", headers=team[who], json={"role": "admin"}).status_code == 403
        assert client.patch(f"{b}/{uid(client, team[who])}", headers=team[who], json={"role": "admin"}).status_code == 403
    roles = {m["email"]: m["role"] for m in client.get(b, headers=oh).json()}
    assert roles["admin@example.com"] == "admin" and roles["super_agent@example.com"] == "super_agent" and roles["analytics_agent@example.com"] == "analytics_agent"


def test_a_stranger_cannot_join_or_read_anything(client, owner):
    oh, ws = owner
    stranger = signup(client, "stranger@example.com")
    assert client.post(f"/api/v1/workspaces/{ws}/members", headers=stranger, json={"email": "stranger@example.com", "role": "admin"}).status_code == 404
    assert client.get(f"/api/v1/workspaces/{ws}/permissions", headers=stranger).status_code == 404


def test_owner_manages_everyone_and_suspension_locks_a_person_out(client, owner, team):
    oh, ws = owner
    b, v = f"/api/v1/workspaces/{ws}/members", uid(client, team["viewer"])
    assert client.patch(f"{b}/{v}", headers=oh, json={"role": "admin"}).json()["role"] == "admin"
    assert client.get(f"/api/v1/workspaces/{ws}/audit", headers=team["viewer"]).status_code == 200
    assert client.patch(f"{b}/{v}", headers=oh, json={"role": "editor"}).json()["role"] == "editor"
    s = uid(client, team["super_agent"])
    assert client.patch(f"{b}/{s}", headers=oh, json={"suspended": True}).json()["suspended"] is True
    assert client.get(f"/api/v1/workspaces/{ws}/campaigns", headers=team["super_agent"]).status_code == 403
    assert client.post(f"/api/v1/workspaces/{ws}/content", headers=team["super_agent"], json={"kind": "blog", "title": "t", "body": "b"}).status_code == 403
    assert client.get("/api/v1/workspaces", headers=team["super_agent"]).json() == []
    assert client.patch(f"{b}/{s}", headers=oh, json={"suspended": False}).status_code == 200
    assert client.get(f"/api/v1/workspaces/{ws}/campaigns", headers=team["super_agent"]).status_code == 200
    assert client.delete(f"{b}/{s}", headers=oh).status_code == 200
    assert client.get(f"/api/v1/workspaces/{ws}/campaigns", headers=team["super_agent"]).status_code == 404


def test_owner_can_withdraw_delegated_powers_from_admins(client, owner, team):
    oh, ws = owner
    b = f"/api/v1/workspaces/{ws}"
    assert "approval.decide" in client.get(f"{b}/permissions", headers=team["admin"]).json()["permissions"]
    assert client.put(f"{b}/admin-permissions", headers=oh, json={"revoked": ["approval.decide", "integration.manage"]}).status_code == 200
    p = client.get(f"{b}/permissions", headers=team["admin"]).json()
    assert "approval.decide" not in p["permissions"] and "integration.manage" not in p["permissions"] and "content.write" in p["permissions"]
    assert attempt(client, ws, team["admin"], "integration.manage").status_code == 403
    assert "approval.decide" in client.get(f"{b}/permissions", headers=oh).json()["permissions"]
    assert client.put(f"{b}/admin-permissions", headers=oh, json={"revoked": ["theme.write"]}).status_code == 422
    assert client.put(f"{b}/admin-permissions", headers=team["admin"], json={"revoked": []}).status_code == 403
    assert client.put(f"{b}/admin-permissions", headers=oh, json={"revoked": []}).status_code == 200
    assert "approval.decide" in client.get(f"{b}/permissions", headers=team["admin"]).json()["permissions"]


def test_permissions_endpoint_reports_the_real_role(client, owner, team):
    _, ws = owner
    p = client.get(f"/api/v1/workspaces/{ws}/permissions", headers=team["content_agent"]).json()
    assert p["role"] == "content_agent" and p["permissions"] == ["content.write", "read"] and len(p["roles"]) == len(ROLES)


def test_super_agent_can_plan_and_request_but_never_approve_publish_or_widen_itself(client, owner, team, monkeypatch):
    fake = FakeWP()
    oh, b, iid, d = setup(client, owner, monkeypatch, fake)
    sa = team["super_agent"]
    assert client.post(f"{b}/campaigns", headers=sa, json={"name": "Agent plan"}).status_code == 201
    doc = client.post(f"{b}/content", headers=sa, json={"kind": "blog", "title": "Agent draft", "body": "Draft body " * 30}).json()
    ap = client.post(f"{b}/approvals", headers=sa, json={"version_id": doc["versions"][0]["id"], "integration_id": iid, "action": "publish_blog"})
    assert ap.status_code == 201
    aid = ap.json()["id"]
    assert client.post(f"{b}/approvals/{aid}/decision", headers=sa, json={"decision": "approve"}).status_code == 403
    assert client.post(f"{b}/approvals/{aid}/execute", headers=sa).status_code == 403
    assert client.patch(f"{b}/members/{uid(client, sa)}", headers=sa, json={"role": "admin"}).status_code == 403
    assert client.put(f"{b}/admin-permissions", headers=sa, json={"revoked": []}).status_code == 403
    assert client.post(f"{b}/integrations/wordpress", headers=sa, json={"label": "l", "site_url": "https://blog.example.com", "username": "u", "app_password": "12345678"}).status_code == 403
    assert client.get(f"{b}/audit", headers=sa).status_code == 403
    assert client.post(f"{b}/approvals/{aid}/execute", headers=oh).status_code == 409
    assert fake.calls == 0


def test_agents_have_separate_least_privilege_powers(client, owner, team, monkeypatch):
    fake = FakeWP()
    oh, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, oh, b, iid, d)
    pub, cont, res, ana = team["publishing_agent"], team["content_agent"], team["research_agent"], team["analytics_agent"]
    body = {"kind": "blog", "title": "x", "body": "y"}
    assert client.post(f"{b}/content", headers=pub, json=body).status_code == 403
    assert client.post(f"{b}/approvals", headers=pub, json={"version_id": d["versions"][0]["id"], "integration_id": iid, "action": "publish_blog"}).status_code == 403
    assert client.post(f"{b}/approvals/{aid}/decision", headers=pub, json={"decision": "approve"}).status_code == 403
    assert client.post(f"{b}/content", headers=cont, json=body).status_code == 201
    assert client.post(f"{b}/content/{d['id']}/versions", headers=cont, json={"body": "new draft"}).status_code == 201
    assert client.post(f"{b}/approvals/{aid}/execute", headers=cont).status_code == 403
    assert client.put(f"{b}/profile", headers=cont, json={"industry": "x"}).status_code == 403
    for h in (res, ana):
        assert client.post(f"{b}/content", headers=h, json=body).status_code == 403
        assert client.post(f"{b}/approvals/{aid}/execute", headers=h).status_code == 403
        assert client.get(f"{b}/campaigns", headers=h).status_code == 200
    assert client.get(f"{b}/approvals/{aid}", headers=oh).json()["status"] == "INVALIDATED"  # the agent's edit cancelled the human approval
    assert client.post(f"{b}/approvals/{aid}/execute", headers=pub).status_code == 409 and fake.calls == 0


def test_publishing_agent_can_run_only_an_exactly_approved_post(client, owner, team, monkeypatch):
    fake = FakeWP()
    oh, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, oh, b, iid, d)
    r = client.post(f"{b}/approvals/{aid}/execute", headers=team["publishing_agent"])
    assert r.status_code == 200 and r.json()["execution"]["status"] == "PUBLISHED" and fake.calls == 1


def test_roles_do_not_cross_workspaces(client, owner, team):
    oh, ws = owner
    other_owner = signup(client, "other-owner@example.com")
    ws2 = client.post("/api/v1/workspaces", headers=other_owner, json={"name": "Other Co"}).json()["id"]
    camp2 = client.post(f"/api/v1/workspaces/{ws2}/campaigns", headers=other_owner, json={"name": "Secret"}).json()["id"]
    for who in ("owner", "admin", "super_agent", "publishing_agent"):
        h = oh if who == "owner" else team[who]
        assert client.get(f"/api/v1/workspaces/{ws2}/campaigns", headers=h).status_code == 404, who
        assert client.get(f"/api/v1/workspaces/{ws}/campaigns/{camp2}", headers=h).status_code == 404, who
        assert client.post(f"/api/v1/workspaces/{ws2}/emergency-shutdown", headers=h).status_code == 404, who
    assert client.patch(f"/api/v1/workspaces/{ws2}/members/{uid(client, other_owner)}", headers=team["admin"], json={"role": "viewer"}).status_code == 404


def test_sensitive_actions_are_audited_with_actor_and_result(client, owner, team):
    oh, ws = owner
    b = f"/api/v1/workspaces/{ws}"
    v = uid(client, team["viewer"])
    client.patch(f"{b}/members/{v}", headers=oh, json={"role": "editor"})
    client.patch(f"{b}/members/{v}", headers=oh, json={"suspended": True})
    client.put(f"{b}/admin-permissions", headers=oh, json={"revoked": ["audit.read"]})
    client.delete(f"{b}/members/{v}", headers=oh)
    client.post(f"{b}/emergency-shutdown", headers=oh)
    by = {e["action"]: e for e in client.get(f"{b}/audit?limit=100", headers=oh).json()}
    for a in ("member.role_change", "member.suspend", "owner.admin_permissions", "member.remove", "owner.emergency_shutdown"):
        assert a in by and by[a]["actor_id"] == uid(client, oh) and by[a]["outcome"] == "success", a
    assert by["member.role_change"]["detail"] == {"from": "viewer", "to": "editor"}


def test_emergency_shutdown_pauses_and_withdraws_without_deleting(client, owner, team, monkeypatch):
    fake = FakeWP()
    oh, b, iid, d = setup(client, owner, monkeypatch, fake)
    aid = approved(client, oh, b, iid, d)
    assert client.post(f"{b}/emergency-shutdown", headers=team["admin"]).status_code == 403
    assert client.post(f"{b}/emergency-shutdown", headers=oh).json() == {"paused": True, "approvals_revoked": 1}
    assert client.get(f"{b}/approvals/{aid}", headers=oh).json()["status"] == "REVOKED"
    assert client.post(f"{b}/approvals/{aid}/execute", headers=oh).status_code == 409 and fake.calls == 0
    assert client.get(f"{b}/content/{d['id']}", headers=oh).status_code == 200


def test_database_itself_rejects_an_unknown_role(client, owner, db_session):
    _, ws = owner
    other_id = uid(client, signup(client, "dbrole@example.com"))
    db_session.add(Membership(workspace_id=ws, user_id=other_id, role="god"))
    with pytest.raises(IntegrityError):  # the CHECK constraint, not the application, refuses it
        db_session.flush()
    db_session.rollback()
