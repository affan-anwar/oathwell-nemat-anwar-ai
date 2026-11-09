from sqlalchemy import select

from app.db.models import User
from tests.conftest import signup


def test_register_login_me(client, db_session):
    h = signup(client, "a@example.com")
    assert client.get("/api/v1/auth/me", headers=h).json()["email"] == "a@example.com"
    assert db_session.scalar(select(User)).password_hash.startswith("scrypt$")  # never plain text


def test_bad_inputs(client):
    assert client.post("/api/v1/auth/register", json={"email": "x@e.com", "password": "short", "full_name": "A"}).status_code == 422
    assert client.post("/api/v1/auth/register", json={"email": "nope", "password": "long-enough-pw", "full_name": "A"}).status_code == 422
    signup(client, "dup@example.com")
    assert client.post("/api/v1/auth/register", json={"email": "DUP@example.com", "password": "long-enough-pw", "full_name": "A"}).status_code == 409
    assert client.post("/api/v1/auth/login", json={"email": "dup@example.com", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "wrong-password"}).status_code == 401


def test_protected_routes_need_token(client, owner):
    _, ws = owner
    assert client.get(f"/api/v1/workspaces/{ws}/profile").status_code == 401
    assert client.get(f"/api/v1/workspaces/{ws}/profile", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_tenant_isolation(client, owner):
    h, ws = owner
    camp = client.post(f"/api/v1/workspaces/{ws}/campaigns", json={"name": "Secret"}, headers=h).json()["id"]
    doc = client.post(f"/api/v1/workspaces/{ws}/content", json={"kind": "blog", "title": "T", "body": "B"}, headers=h).json()["id"]
    other = signup(client, "other@example.com")
    ws2 = client.post("/api/v1/workspaces", json={"name": "Other"}, headers=other).json()["id"]
    for path in ["profile", "members", "audit", "campaigns", "content", "approvals", "integrations",
                 f"campaigns/{camp}", f"content/{doc}"]:
        assert client.get(f"/api/v1/workspaces/{ws}/{path}", headers=other).status_code == 404, path
    # a resource id from workspace A used inside workspace B must not resolve
    assert client.get(f"/api/v1/workspaces/{ws2}/campaigns/{camp}", headers=other).status_code == 404
    assert client.get(f"/api/v1/workspaces/{ws2}/content/{doc}", headers=other).status_code == 404
    assert client.post(f"/api/v1/workspaces/{ws}/pause", json={"paused": True}, headers=other).status_code == 404
    assert client.get("/api/v1/workspaces", headers=other).json()[0]["id"] == ws2


def test_roles(client, owner):
    h, ws = owner
    viewer, editor = signup(client, "v@example.com"), signup(client, "e@example.com")
    assert client.post(f"/api/v1/workspaces/{ws}/members", json={"email": "v@example.com", "role": "viewer"}, headers=h).status_code == 201
    assert client.post(f"/api/v1/workspaces/{ws}/members", json={"email": "e@example.com", "role": "editor"}, headers=h).status_code == 201
    assert client.get(f"/api/v1/workspaces/{ws}/campaigns", headers=viewer).status_code == 200
    assert client.post(f"/api/v1/workspaces/{ws}/campaigns", json={"name": "x"}, headers=viewer).status_code == 403
    assert client.post(f"/api/v1/workspaces/{ws}/campaigns", json={"name": "x"}, headers=editor).status_code == 201
    assert client.get(f"/api/v1/workspaces/{ws}/audit", headers=editor).status_code == 403
    assert client.post(f"/api/v1/workspaces/{ws}/pause", json={"paused": True}, headers=editor).status_code == 403
    assert client.get(f"/api/v1/workspaces/{ws}/audit", headers=h).status_code == 200


def test_profile_persists(client, owner):
    h, ws = owner
    r = client.put(f"/api/v1/workspaces/{ws}/profile", headers=h, json={
        "description": "We sell shoes", "languages": ["en", "hi"], "budget_limit": 5000.5, "currency": "INR",
        "prohibited_claims": "100% guaranteed"})
    assert r.status_code == 200
    got = client.get(f"/api/v1/workspaces/{ws}/profile", headers=h).json()
    assert got["languages"] == ["en", "hi"] and got["budget_limit"] == 5000.5 and got["prohibited_claims"] == "100% guaranteed"
    assert client.put(f"/api/v1/workspaces/{ws}/profile", headers=h, json={"currency": "RUPEES"}).status_code == 422
