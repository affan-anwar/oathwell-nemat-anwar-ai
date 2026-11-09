"""WordPress REST API adapter (Application Passwords, HTTP Basic). Only a 201 response with id, link and
status=publish counts as confirmed. Anything unknown is UNCLEAR and must be reconciled, never blindly retried."""
import httpx


class ProviderRejected(Exception):
    """The provider answered with a definite refusal (4xx)."""


class ProviderUnclear(Exception):
    """The result is unknown (timeout, 5xx, malformed answer). The post may or may not exist."""


def http_client() -> httpx.Client:
    return httpx.Client(timeout=20.0, follow_redirects=False)


class WordPressAdapter:
    def __init__(self, site_url: str, username: str, app_password: str, client: httpx.Client | None = None):
        self.base = site_url.rstrip("/") + "/wp-json/wp/v2"
        self.auth = (username, app_password)
        self.client = client or http_client()

    def _call(self, method: str, path: str, **kw):
        try:
            r = self.client.request(method, self.base + path, auth=self.auth, **kw)
        except httpx.RequestError as exc:
            raise ProviderUnclear(f"No answer from the site: {type(exc).__name__}")
        if 400 <= r.status_code < 500:
            raise ProviderRejected(f"Site refused the request (HTTP {r.status_code})")
        if r.status_code >= 500:
            raise ProviderUnclear(f"Site error (HTTP {r.status_code})")
        return r

    def test_connection(self) -> dict:
        r = self._call("GET", "/users/me", params={"context": "edit"})
        try:
            data = r.json()
            return {"user": data["name"]}
        except (ValueError, KeyError):
            raise ProviderUnclear("Unexpected answer from the site")

    def publish_post(self, title: str, content: str, slug: str | None = None) -> dict:
        payload = {"title": title, "content": content, "status": "publish"}
        if slug:
            payload["slug"] = slug  # deterministic, so a lost response can be reconciled by looking the post up
        r = self._call("POST", "/posts", json=payload)
        try:
            d = r.json()
            if r.status_code == 201 and d.get("status") == "publish" and d.get("id") and d.get("link"):
                return {"confirmed": True, "external_id": str(d["id"]), "external_url": d["link"]}
        except ValueError:
            pass
        raise ProviderUnclear("Site answered but did not confirm the post")

    def find_post_by_slug(self, slug: str) -> dict | None:
        """Returns {'id','link','status'} if a post with this slug exists in any status, else None."""
        r = self._call("GET", "/posts", params={"slug": slug, "status": "publish,future,draft,pending,private", "context": "edit"})
        try:
            items = r.json()
        except ValueError:
            raise ProviderUnclear("Unexpected answer from the site")
        if not isinstance(items, list):
            raise ProviderUnclear("Unexpected answer from the site")
        if not items:
            return None
        p = items[0]
        return {"id": str(p.get("id")), "link": p.get("link"), "status": p.get("status")}
