import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "./api.js";
import { useApp } from "./state.jsx";

export default function TopSearch() {
  const { ws } = useApp();
  const nav = useNavigate();
  const [q, setQ] = useState(""); const [res, setRes] = useState(null); const [err, setErr] = useState("");
  const box = useRef(null);
  useEffect(() => {
    if (q.trim().length < 2) { setRes(null); setErr(""); return undefined; }
    const t = setTimeout(() => api(`/workspaces/${ws.id}/search?q=${encodeURIComponent(q.trim())}`).then((r) => { setRes(r); setErr(""); }).catch((e) => setErr(e.message)), 250);
    return () => clearTimeout(t);
  }, [q, ws.id]);
  useEffect(() => {
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setRes(null); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);
  const go = (to) => { setRes(null); setQ(""); nav(to); };
  const none = res && !res.campaigns.length && !res.content.length;
  return (
    <div className="srch" ref={box}>
      <input id="global-search" type="search" aria-label="Search campaigns and content" placeholder="Search campaigns and content" value={q}
        onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setRes(null)} />
      <span className="kbd" aria-hidden="true">Ctrl K</span>
      {(res || err) && <div className="panel" role="region" aria-label="Search results">
        {err && <p className="small mu">{err}</p>}{none && <p className="small mu">No matches.</p>}
        {res?.campaigns.map((c) => <button key={c.id} className="note" onClick={() => go("/campaigns")}><b>{c.name}</b><span className="small mu">Campaign · {c.status.toLowerCase()}</span></button>)}
        {res?.content.map((d) => <button key={d.id} className="note" onClick={() => go(`/content?doc=${d.id}`)}><b>{d.title}</b><span className="small mu">{d.kind.replaceAll("_", " ")} · {d.status}</span></button>)}
      </div>}
    </div>
  );
}
