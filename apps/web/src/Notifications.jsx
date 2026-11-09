import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "./api.js";
import { useApp } from "./state.jsx";
import { fmt } from "./ui.jsx";

export default function Notifications() {
  const { ws } = useApp();
  const nav = useNavigate();
  const [data, setData] = useState({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const load = useCallback(() => api(`/workspaces/${ws.id}/notifications`).then(setData).catch(() => {}), [ws.id]);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);
  const read = async (ids) => { await api(`/workspaces/${ws.id}/notifications/read`, { method: "POST", body: { ids } }).catch(() => {}); load(); };
  return (
    <div className="bell">
      <button className="btn sm" aria-expanded={open} onClick={() => setOpen(!open)}>
        Alerts{data.unread > 0 && <><span className="count" aria-hidden="true">{data.unread}</span><span className="sr-only"> {data.unread} unread</span></>}
      </button>
      {open && <div className="panel" role="region" aria-label="Notifications">
        <div className="row between"><b>Notifications</b><button className="btn sm ghost" disabled={!data.unread} onClick={() => read(null)}>Mark all read</button></div>
        {data.items.length === 0 ? <p className="mu small">Nothing yet.</p> : data.items.map((n) => (
          <button key={n.id} className={`note ${n.read ? "" : "unread"}`} onClick={() => { read([n.id]); setOpen(false); if (n.link) nav(n.link); }}>
            <b>{n.title}</b>{n.body && <span className="small mu">{n.body}</span>}<span className="small mu">{fmt(n.created_at)}</span>
          </button>))}
      </div>}
    </div>
  );
}
