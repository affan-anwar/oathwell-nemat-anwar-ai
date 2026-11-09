from tests.conftest import signup

L = "/api/v1/auth/login"


def bad(client, email="rl@example.com"):
    return client.post(L, json={"email": email, "password": "wrong-password-1"})


def test_login_rate_limit_locks_after_repeated_failures(client):
    signup(client, "rl@example.com")
    assert [bad(client).status_code for _ in range(5)] == [401] * 5
    r = client.post(L, json={"email": "rl@example.com", "password": "correct-horse-1"})  # even the right password is refused now
    assert r.status_code == 429 and r.headers["Retry-After"] == "900"
    assert client.post(L, json={"email": "someone-else@example.com", "password": "x"}).status_code == 401  # other accounts unaffected


def test_success_resets_the_counter(client):
    signup(client, "rl2@example.com")
    for _ in range(3):
        bad(client, "rl2@example.com")
    assert client.post(L, json={"email": "rl2@example.com", "password": "correct-horse-1"}).status_code == 200
    assert [bad(client, "rl2@example.com").status_code for _ in range(4)] == [401] * 4


def test_logout_revokes_every_token(client):
    h = signup(client, "lo@example.com")
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401
    assert client.post(L, json={"email": "lo@example.com", "password": "correct-horse-1"}).status_code == 200


def test_change_password(client):
    h = signup(client, "cp@example.com")
    p = "/api/v1/auth/change-password"
    assert client.post(p, headers=h, json={"current_password": "nope-nope-1", "new_password": "brand-new-pass-1"}).status_code == 400
    assert client.post(p, headers=h, json={"current_password": "correct-horse-1", "new_password": "short"}).status_code == 422
    r = client.post(p, headers=h, json={"current_password": "correct-horse-1", "new_password": "brand-new-pass-1"})
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401  # old token dead
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200
    assert client.post(L, json={"email": "cp@example.com", "password": "correct-horse-1"}).status_code == 401
    assert client.post(L, json={"email": "cp@example.com", "password": "brand-new-pass-1"}).status_code == 200


def test_security_headers_and_body_limit(client):
    h = client.get("/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    api = client.get("/api/v1/auth/me").headers
    assert api["cache-control"] == "no-store" and "frame-ancestors 'none'" in api["content-security-policy"]
    big = client.post(L, content=b"x" * 1_000_001, headers={"content-type": "application/json"})
    assert big.status_code == 413
