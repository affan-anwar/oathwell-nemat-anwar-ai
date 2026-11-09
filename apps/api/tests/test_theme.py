import pytest

from app.services import themes
from tests.conftest import signup

OK_DARK = {"primary": "#ff9500", "primaryText": "#000000"}  # orange, readable


def url(ws, tail="theme"):
    return f"/api/v1/workspaces/{ws}/{tail}"


@pytest.fixture()
def people(client, owner):
    oh, ws = owner
    out = {"owner": oh}
    for r in ("admin", "editor", "viewer", "super_agent"):
        out[r] = signup(client, f"t-{r}@example.com")
        client.post(f"/api/v1/workspaces/{ws}/members", headers=oh, json={"email": f"t-{r}@example.com", "role": r})
    return out


def test_defaults_are_premium_black_and_emerald_with_no_blue_purple_or_cyan():
    for mode, toks in themes.DEFAULTS.items():
        assert set(toks) == set(themes.KEYS)
        for k, v in toks.items():
            r, g, b = (int(v[i:i + 2], 16) for i in (1, 3, 5))
            assert not (b > r + 25 and b > g + 25), f"{mode}.{k} {v} is blue or purple"
    clean, problems = themes.validate(themes.DEFAULTS)
    assert problems == [] and clean["dark"]["bg"] == "#030907"


def test_contrast_maths_and_validation_rules():
    assert themes.contrast("#000000", "#ffffff") == 21.0 and themes.contrast("#777777", "#777777") == 1.0
    _, p = themes.validate({"dark": {"text": "#0d1d17"}})  # dark text on a dark card
    assert any(x["key"] == "text" and "contrast" in x["message"] for x in p)
    _, p = themes.validate({"dark": {"primary": "red"}, "light": {"bogus": "#ffffff"}, "sepia": {}})
    assert {x["key"] for x in p} >= {"primary", "bogus", None}
    clean, p = themes.validate({"dark": OK_DARK})
    assert p == [] and clean["dark"]["primary"] == "#ff9500" and clean["light"] == themes.DEFAULTS["light"]  # missing keys come from the defaults


def test_everyone_can_read_the_theme_and_only_the_owner_can_edit_it(client, owner, people):
    _, ws = owner
    for who in people:
        g = client.get(url(ws), headers=people[who]).json()
        assert g["source"] == "default" and g["editable"] is (who == "owner") and g["tokens"]["dark"]["bg"] == "#030907"
    payload = {"scope": "workspace", "tokens": {"dark": OK_DARK}, "default_mode": "dark", "allow_user_mode": True}
    for who in ("admin", "editor", "viewer", "super_agent"):  # even admins cannot restyle the platform
        assert client.put(url(ws), headers=people[who], json=payload).status_code == 403, who
        assert client.post(url(ws, "theme/check"), headers=people[who], json={"tokens": {}}).status_code == 403
        assert client.delete(url(ws) + "?scope=workspace", headers=people[who]).status_code == 403
    assert client.put(url(ws), headers=people["owner"], json=payload).status_code == 200


def test_save_persists_and_reaches_every_member_then_reset_restores_defaults(client, owner, people, db_session):
    _, ws = owner
    payload = {"scope": "workspace", "tokens": {"dark": OK_DARK}, "default_mode": "light", "allow_user_mode": True}
    r = client.put(url(ws), headers=people["owner"], json=payload).json()
    assert r["source"] == "workspace" and r["default_mode"] == "light"
    for who in ("viewer", "admin"):
        g = client.get(url(ws), headers=people[who]).json()
        assert g["source"] == "workspace" and g["tokens"]["dark"]["primary"] == "#ff9500" and g["default_mode"] == "light"
    db_session.expire_all()
    from app.db.models import ThemeSetting
    assert db_session.query(ThemeSetting).count() == 1  # really stored in the database
    back = client.delete(url(ws) + "?scope=workspace", headers=people["owner"]).json()
    assert back["source"] == "default" and back["tokens"]["dark"]["primary"] == themes.DEFAULTS["dark"]["primary"]
    assert db_session.query(ThemeSetting).count() == 0


def test_unsafe_themes_are_refused_with_reasons_and_nothing_is_saved(client, owner, people):
    _, ws = owner
    bad = {"scope": "workspace", "tokens": {"dark": {"text": "#101010"}}, "default_mode": "dark", "allow_user_mode": True}
    r = client.put(url(ws), headers=people["owner"], json=bad)
    assert r.status_code == 422 and r.json()["detail"]["problems"][0]["key"] == "text"
    assert client.get(url(ws), headers=people["viewer"]).json()["source"] == "default"
    chk = client.post(url(ws, "theme/check"), headers=people["owner"], json={"tokens": {"dark": {"text": "#101010"}}}).json()
    assert chk["ok"] is False and chk["problems"]
    assert client.put(url(ws), headers=people["owner"], json={**bad, "scope": "everywhere"}).status_code == 422


def test_global_theme_covers_all_the_owners_workspaces_and_a_workspace_theme_overrides_it(client, owner, people):
    oh, ws = owner
    ws2 = client.post("/api/v1/workspaces", headers=oh, json={"name": "Client B"}).json()["id"]
    client.put(url(ws), headers=oh, json={"scope": "global", "tokens": {"dark": OK_DARK}, "default_mode": "dark", "allow_user_mode": True})
    assert client.get(url(ws2), headers=oh).json()["source"] == "global"
    assert client.get(url(ws), headers=people["viewer"]).json()["tokens"]["dark"]["primary"] == "#ff9500"
    client.put(url(ws2), headers=oh, json={"scope": "workspace", "tokens": {"dark": {"primary": "#a3e635", "primaryText": "#000000"}}, "default_mode": "dark", "allow_user_mode": True})
    assert client.get(url(ws2), headers=oh).json()["tokens"]["dark"]["primary"] == "#a3e635"  # client-specific
    assert client.get(url(ws), headers=oh).json()["tokens"]["dark"]["primary"] == "#ff9500"
    other = signup(client, "other-brand@example.com")
    ws3 = client.post("/api/v1/workspaces", headers=other, json={"name": "Someone else"}).json()["id"]
    assert client.get(url(ws3), headers=other).json()["source"] == "default"  # another owner's global theme never leaks
    assert client.get(url(ws2), headers=other).status_code == 404


def test_each_person_keeps_their_own_mode_without_touching_brand_colours(client, owner, people):
    oh, ws = owner
    client.put(url(ws), headers=oh, json={"scope": "workspace", "tokens": {"dark": OK_DARK}, "default_mode": "dark", "allow_user_mode": True})
    assert client.put(url(ws, "preferences"), headers=people["viewer"], json={"mode": "light"}).json() == {"my_mode": "light"}
    assert client.put(url(ws, "preferences"), headers=people["editor"], json={"mode": "system"}).status_code == 200
    assert client.get(url(ws), headers=people["viewer"]).json()["my_mode"] == "light"
    assert client.get(url(ws), headers=people["editor"]).json()["my_mode"] == "system"
    assert client.get(url(ws), headers=oh).json()["my_mode"] is None  # personal, not shared
    assert client.get(url(ws), headers=people["viewer"]).json()["tokens"]["dark"]["primary"] == "#ff9500"  # brand untouched
    assert client.put(url(ws, "preferences"), headers=people["viewer"], json={"mode": "neon"}).status_code == 422


def test_owner_can_lock_the_display_mode_for_everyone_else(client, owner, people):
    oh, ws = owner
    client.put(url(ws), headers=oh, json={"scope": "workspace", "tokens": {}, "default_mode": "dark", "allow_user_mode": False})
    for who in ("admin", "editor", "viewer", "super_agent"):
        assert client.put(url(ws, "preferences"), headers=people[who], json={"mode": "light"}).status_code == 403
    assert client.put(url(ws, "preferences"), headers=oh, json={"mode": "light"}).status_code == 200  # the Owner still can
    client.put(url(ws), headers=oh, json={"scope": "workspace", "tokens": {}, "default_mode": "dark", "allow_user_mode": True})
    assert client.put(url(ws, "preferences"), headers=people["viewer"], json={"mode": "light"}).status_code == 200


def test_theme_changes_are_audited_and_isolated(client, owner, people):
    oh, ws = owner
    client.put(url(ws), headers=oh, json={"scope": "workspace", "tokens": {"dark": OK_DARK}, "default_mode": "dark", "allow_user_mode": True})
    client.delete(url(ws) + "?scope=workspace", headers=oh)
    acts = [e["action"] for e in client.get(url(ws, "audit"), headers=oh).json()]
    assert "theme.update" in acts and "theme.reset" in acts
    stranger = signup(client, "t-stranger@example.com")
    assert client.get(url(ws), headers=stranger).status_code == 404
    assert client.put(url(ws), headers=stranger, json={"scope": "workspace", "tokens": {}}).status_code == 404
    assert client.put(url(ws, "preferences"), headers=stranger, json={"mode": "light"}).status_code == 404


PRESETS = {  # copied from the Owner Console presets: every one must pass the server's rules
    "Carbon & Amber": {"dark": {"primary": "#f59e0b", "primaryText": "#140c00", "accent": "#fcd34d", "chart1": "#f59e0b"}, "light": {"primary": "#92400e", "primaryText": "#ffffff", "accent": "#78350f", "chart1": "#92400e"}},
    "Obsidian & Lime": {"dark": {"primary": "#a3e635", "primaryText": "#0a1200", "accent": "#d9f99d", "chart1": "#a3e635"}, "light": {"primary": "#3f6212", "primaryText": "#ffffff", "accent": "#365314", "chart1": "#3f6212"}},
    "Graphite & Rose": {"dark": {"primary": "#fb7185", "primaryText": "#1a0509", "accent": "#fda4af", "chart1": "#fb7185"}, "light": {"primary": "#be123c", "primaryText": "#ffffff", "accent": "#9f1239", "chart1": "#be123c"}},
}


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_preset_palette_passes_the_servers_contrast_rules(name):
    _, problems = themes.validate(PRESETS[name])
    assert problems == [], (name, problems)


def test_coloured_text_must_reach_five_to_one_so_it_stays_readable_on_tinted_badges():
    _, p = themes.validate({"light": {"success": "#10a06b"}})  # about 3:1 on white
    assert any(x["key"] == "success" and "5.0:1" in x["message"] for x in p)
    assert themes.validate({"light": {"success": "#047857"}})[1] == []
