// A tiny FAKE WordPress for tests. It is a mock: passing tests against it do not prove a real site works.
// Modes: ok, lost (saves the post but answers 500, like a lost response). Control: /__mode?m=lost|ok|reset, /__posts
import http from "node:http";

const OK = "Basic " + Buffer.from("bot:abcd efgh ijkl").toString("base64");
let mode = "ok";
let posts = [];
http.createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  const send = (code, obj) => { res.writeHead(code, { "content-type": "application/json" }); res.end(JSON.stringify(obj)); };
  let body = "";
  req.on("data", (d) => (body += d));
  req.on("end", () => {
    if (url.pathname === "/__posts") return send(200, posts);
    if (url.pathname === "/__mode") { mode = url.searchParams.get("m"); if (mode === "reset") { posts = []; mode = "ok"; } return send(200, { mode }); }
    if (req.headers.authorization !== OK) return send(401, {});
    if (url.pathname.endsWith("/users/me")) return send(200, { name: "bot" });
    if (req.method === "GET" && url.pathname.endsWith("/posts")) return send(200, posts.filter((p) => p.slug === url.searchParams.get("slug")));
    if (req.method === "POST" && url.pathname.endsWith("/posts")) {
      const d = JSON.parse(body);
      const p = { id: posts.length + 1, link: `http://127.0.0.1:8099/p/${posts.length + 1}`, status: "publish", slug: d.slug, title: d.title };
      posts.push(p);
      return mode === "lost" ? send(500, {}) : send(201, p);
    }
    send(404, {});
  });
}).listen(8099, "127.0.0.1");
