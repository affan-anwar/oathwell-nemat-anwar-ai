import { useState } from "react";
import { api } from "../api.js";
import { HIJRI, MONTHS, daysIn, hijriOf, monthCells } from "../hijri.js";
import { useApp } from "../state.jsx";
import { Badge, PageHeader, fmt, useAsync } from "../ui.jsx";

const now = new Date();
const pad = (n) => String(n).padStart(2, "0");
const local = (s) => new Date(s + "Z"); // the API sends UTC without a zone suffix

export default function Calendar() {
  const { ws } = useApp();
  const [y, setY] = useState(now.getFullYear()); const [m, setM] = useState(now.getMonth());
  const step = (n) => { const i = y * 12 + m + n; if (i < 570 * 12 || i > 2099 * 12 + 11) return; setY(Math.floor(i / 12)); setM(i % 12); };
  const start = `${y}-${pad(m + 1)}-01`, end = `${y}-${pad(m + 1)}-${pad(daysIn(y, m))}`;
  const { data, error } = useAsync(() => (y >= 1970 && y <= 2100 ? api(`/workspaces/${ws.id}/calendar?start=${start}&end=${end}`) : Promise.resolve({ scheduled: [], campaigns: [] })), [ws.id, y, m]);
  const cells = monthCells(y, m);
  const a = hijriOf(y, m, 1);
  const byDay = {};
  (data?.scheduled || []).forEach((s) => { const d = local(s.scheduled_at); if (d.getFullYear() === y && d.getMonth() === m) (byDay[d.getDate()] ||= []).push(s); });
  const occ = cells.filter((c) => c?.occasion);
  const isToday = (d) => y === now.getFullYear() && m === now.getMonth() && d === now.getDate();
  return (
    <>
      <PageHeader title="Occasions calendar" sub="Your saved schedules plus Gregorian and Hijri dates, 570 to 2099" />
      {error && <div className="alert bd" role="alert">{error.message}</div>}
      <div className="alert">Times are shown in your browser's time zone. Only schedules saved in your workspace appear. Hijri dates use the tabular calendar and can differ by a day from moon sighting.</div>
      <div className="card">
        <div className="row wrap" style={{ marginBottom: 12 }}>
          <button className="btn" aria-label="Previous month" onClick={() => step(-1)}>‹</button>
          <select aria-label="Month" value={m} onChange={(e) => setM(+e.target.value)}>{MONTHS.map((n, i) => <option key={n} value={i}>{n}</option>)}</select>
          <select aria-label="Year" value={y} onChange={(e) => setY(+e.target.value)}>{Array.from({ length: 1530 }, (_, i) => 570 + i).map((v) => <option key={v}>{v}</option>)}</select>
          <button className="btn" aria-label="Next month" onClick={() => step(1)}>›</button>
          <button className="btn" onClick={() => { setY(now.getFullYear()); setM(now.getMonth()); }}>Today</button>
          <span className="mu">{a ? `${HIJRI[a.m - 1]} ${a.y} AH` : "No Hijri date before 622 CE"}</span>
        </div>
        <div className="cal">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => <div className="wh" key={d}>{d}</div>)}
          {cells.map((c, i) => c ? <div key={i} className={`cd ${isToday(c.d) ? "today" : ""}`}><b>{c.d}</b>{c.h && <small className="mu">{c.h.d === 1 ? HIJRI[c.h.m - 1].split(" ")[0] : c.h.d}</small>}
            {c.occasion && <span className="occ">{c.occasion}</span>}{(byDay[c.d] || []).map((s) => <span key={s.id} className="sched" title={s.title}>{pad(local(s.scheduled_at).getHours())}:{pad(local(s.scheduled_at).getMinutes())} {s.title}</span>)}</div> : <div key={i} />)}</div>
      </div>
      <div className="grid2">
        <div className="card"><h2>Scheduled this month</h2>
          {(data?.scheduled || []).length === 0 ? <p className="mu">Nothing scheduled. Schedule a blog post when you request its approval.</p> :
            data.scheduled.map((s) => <div className="li" key={s.id}><span>{s.title}<small className="mu"> {fmt(s.scheduled_at)} · {s.destination}</small>{s.block_reason && <small className="mu"> Waiting: {s.block_reason}</small>}</span><Badge>{s.execution_status || s.status}</Badge></div>)}</div>
        <div className="card"><h2>Campaigns this month</h2>
          {(data?.campaigns || []).length === 0 ? <p className="mu">No campaign dates fall in this month.</p> :
            data.campaigns.map((c) => <div className="li" key={c.id}><span>{c.name}<small className="mu"> {c.start_date} → {c.end_date || "open"}</small></span><Badge>{c.status}</Badge></div>)}
          {occ.length > 0 && <><h3>Occasions</h3>{occ.map((c) => <div className="li" key={c.d}><span>{c.occasion}</span><span className="mu">{c.d} {MONTHS[m]}</span></div>)}</>}</div>
      </div>
    </>
  );
}
