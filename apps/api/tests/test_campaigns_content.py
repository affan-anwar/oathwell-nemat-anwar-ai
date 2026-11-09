def test_campaign_flow(client, owner):
    h, ws = owner
    base = f"/api/v1/workspaces/{ws}/campaigns"
    assert client.post(base, headers=h, json={"name": "X", "timezone": "Mars/Base"}).status_code == 422
    assert client.post(base, headers=h, json={"name": "X", "start_date": "2026-12-02", "end_date": "2026-12-01"}).status_code == 422
    c = client.post(base, headers=h, json={"name": "Diwali", "timezone": "Asia/Kolkata", "channels": ["blog"]}).json()
    assert c["status"] == "DRAFT"
    assert client.post(f"{base}/{c['id']}/transition", headers=h, json={"to": "COMPLETED"}).status_code == 409
    assert client.post(f"{base}/{c['id']}/transition", headers=h, json={"to": "ACTIVE"}).json()["status"] == "ACTIVE"
    assert client.post(f"{base}/{c['id']}/transition", headers=h, json={"to": "PAUSED"}).json()["status"] == "PAUSED"
    client.post(f"{base}/{c['id']}/transition", headers=h, json={"to": "CANCELLED"})
    assert client.patch(f"{base}/{c['id']}", headers=h, json={"name": "new"}).status_code == 409
    client.post(f"{base}/{c['id']}/transition", headers=h, json={"to": "ARCHIVED"})
    assert client.get(base, headers=h).json() == []  # archived hidden by default
    assert len(client.get(base + "?status=ARCHIVED", headers=h).json()) == 1


def test_pagination(client, owner):
    h, ws = owner
    for n in range(5):
        client.post(f"/api/v1/workspaces/{ws}/campaigns", headers=h, json={"name": f"c{n}"})
    assert len(client.get(f"/api/v1/workspaces/{ws}/campaigns?limit=2", headers=h).json()) == 2
    assert len(client.get(f"/api/v1/workspaces/{ws}/campaigns?limit=2&offset=4", headers=h).json()) == 1
    assert client.get(f"/api/v1/workspaces/{ws}/campaigns?limit=1000", headers=h).status_code == 422


def test_content_versions_and_diff(client, owner):
    h, ws = owner
    base = f"/api/v1/workspaces/{ws}/content"
    d = client.post(base, headers=h, json={"kind": "blog", "title": "T", "body": "line one\nline two"}).json()
    assert d["versions"][0]["number"] == 1 and len(d["versions"][0]["content_hash"]) == 64
    v2 = client.post(f"{base}/{d['id']}/versions", headers=h, json={"body": "line one\nline 2"}).json()
    assert v2["number"] == 2 and v2["content_hash"] != d["versions"][0]["content_hash"]
    diff = client.get(f"{base}/{d['id']}/diff?a=1&b=2", headers=h).json()["diff"]
    assert "-line two" in diff and "+line 2" in diff
    assert len(client.get(f"{base}/{d['id']}", headers=h).json()["versions"]) == 2
    assert client.post(base, headers=h, json={"kind": "tweet", "title": "T", "body": "B"}).status_code == 422
    assert client.post(base, headers=h, json={"kind": "blog", "title": "T", "body": "B", "campaign_id": "nope"}).status_code == 404
