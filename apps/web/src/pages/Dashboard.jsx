import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Chart from "../Chart.jsx";
import { GesturePanel } from "../GestureControl.jsx";
import Icon, { RobotArt } from "../Icons.jsx";
import { useApp } from "../state.jsx";
import { Badge, Empty, ErrorBox, Skeleton, fmt, useAsync } from "../ui.jsx";

const hello = () => { const h = new Date().getHours(); return h < 12 ? "Good Morning" : h < 18 ? "Good Afternoon" : "Good Evening"; };
const delta = (c, p) => (p === 0 ? (c === 0 ? "No change yet" : "New this period") : `${c >= p ? "+" : ""}${Math.round(((c - p) / p) * 100)}% vs previous period`);
const pad = (n) => String(n).padStart(2, "0");
const KINDS = { blog: "Blog post", social_post: "Social post", email: "Email", ad_copy: "Ad copy" };
const TONES = ["Professional", "Friendly", "Persuasive", "Concise"];
const SYS = { Running: ["System healthy", "ok"], Paused: ["Paused", "wn"], "Needs attention": ["Needs attention", "bd"], Unavailable: ["Worker offline", "wn"] };

function Panel({ icon, title, sub, action, children, className = "" }) {
  return <section className={`card ${className}`}><div className="ph2"><span className="tile"><Icon n={icon} /></span><div style={{ flex: 1 }}><h2>{title}</h2>{sub && <p>{sub}</p>}</div>{action}</div>{children}</section>;
}

function CampaignPlanner({ d, can }) {
  const [tab, setTab] = useState("ALL");
  const by = d.kpis.campaigns.by_status;
  const tabs = [["ALL", "All", d.kpis.campaigns.total], ["ACTIVE", "Active", by.ACTIVE || 0], ["DRAFT", "Draft", by.DRAFT || 0], ["COMPLETED", "Completed", by.COMPLETED || 0]];
  const rows = d.campaigns.filter((c) => tab === "ALL" || c.status === tab).slice(0, 5);
  return (
    <Panel icon="megaphone" title="Campaign Planner" sub="Your campaigns and how far their content has got" action={can("campaign.write") && <Link className="btn primary sm" to="/campaigns?new=1"><Icon n="plus" />New Campaign</Link>}>
      <div className="minitabs" role="tablist">{tabs.map(([k, l, n]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l} ({n})</button>)}</div>
      {rows.length === 0 ? <Empty title="No campaigns here">Campaigns you create appear in this table.</Empty> :
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Campaign table, scroll sideways if needed"><table className="table2"><thead><tr><th>Campaign</th><th>Channels</th><th>Status</th><th>Progress</th></tr></thead>
          <tbody>{rows.map((c) => <tr key={c.id}><td><b>{c.name}</b><div className="mu small">{c.objective?.slice(0, 40) || "No objective"}</div></td>
            <td>{c.channels.length ? c.channels.map((x) => <span className="chip2" key={x}>{x}</span>) : <span className="mu small">None</span>}</td><td><Badge>{c.status}</Badge></td>
            <td>{c.progress === null ? <span className="mu small">No content yet</span> : <><div className="prog" role="progressbar" aria-label={`${c.name} progress`} aria-valuenow={Math.round(c.progress * 100)} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${c.progress * 100}%` }} /></div><span className="small mu">{c.published_count}/{c.content_count} published</span></>}</td></tr>)}</tbody></table></div>}
      <Link className="link" to="/campaigns">Open all campaigns</Link>
    </Panel>
  );
}

function ContentStudio({ ws, can, toast }) {
  const [tab, setTab] = useState("write");
  const [f, setF] = useState({ kind: "social_post", tone: "Professional", topic: "" });
  const [busy, setBusy] = useState(false); const [out, setOut] = useState(null); const [err, setErr] = useState("");
  const gen = async (e) => {
    e.preventDefault(); setBusy(true); setErr(""); setOut(null);
    try { setOut(await api(`/workspaces/${ws.id}/content/generate`, { method: "POST", body: { kind: f.kind, brief: `${f.topic}. Tone: ${f.tone.toLowerCase()}.` } })); toast("Draft saved. Review it before use."); }
    catch (x) { setErr(x.status === 503 ? `${x.message} Add the key on the server, then try again.` : x.message); } finally { setBusy(false); }
  };
  const v = out?.versions?.[0];
  return (
    <Panel icon="spark" title="AI Content Studio" sub="Create content with your configured AI provider">
      <div className="minitabs" role="tablist">{[["write", "Write"], ["rewrite", "Rewrite"], ["repurpose", "Repurpose"], ["brand", "Brand Checker"]].map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab !== "write" ? <div><p className="mu small">{tab === "rewrite" ? "Rewrite a document in a new tone" : tab === "repurpose" ? "Turn a blog post into a LinkedIn post, email or caption" : "Check a document against your brand voice"} inside Content Studio, where every result becomes a new version.</p><Link className="btn" to="/content">Open Content Studio</Link></div> :
        <form className="studio" onSubmit={gen}>
          <div className="form">
            <label className="field"><span>Content type</span><select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{Object.entries(KINDS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
            <label className="field"><span>Tone</span><select value={f.tone} onChange={(e) => setF({ ...f, tone: e.target.value })}>{TONES.map((t) => <option key={t}>{t}</option>)}</select></label>
            <label className="field"><span>Topic or keywords</span><textarea required minLength={3} value={f.topic} onChange={(e) => setF({ ...f, topic: e.target.value })} placeholder="Digital marketing, growth, brand" /></label>
            {can("content.write") ? <button className="btn primary block" disabled={busy}>{busy ? "Generating…" : "Generate content"}</button> : <p className="mu small">Your role cannot create content.</p>}
          </div>
          <div className="pv">{err && <div className="alert wn" role="alert" style={{ display: "block" }}>{err}</div>}
            {v ? <><b>{out.title}</b><div className="prev" style={{ margin: 0 }}>{v.body}</div><div className="row wrap"><button type="button" className="btn sm" onClick={() => navigator.clipboard?.writeText(v.body).then(() => toast("Copied"))}>Copy</button><Link className="btn sm" to={`/content?doc=${out.id}`}>Open draft</Link></div>
              <p className="small mu">Saved as draft v1 ({out.versions[0].source === "ai" ? "AI generated" : "written"}). Nothing is published without approval.</p></> :
              !err && <p className="mu small">The generated text appears here and is saved as a draft.</p>}</div>
        </form>}
    </Panel>
  );
}

function MiniCalendar({ ws }) {
  const now = new Date(); const y = now.getFullYear(), m = now.getMonth();
  const last = new Date(y, m + 1, 0).getDate();
  const [tab, setTab] = useState("month");
  const { data, error } = useAsync(() => api(`/workspaces/${ws.id}/calendar?start=${y}-${pad(m + 1)}-01&end=${y}-${pad(m + 1)}-${pad(last)}`), [ws.id]);
  const items = (data?.scheduled || []).map((s) => ({ ...s, at: new Date(s.scheduled_at + "Z") }));
  const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  const weekEnd = new Date(y, m, now.getDate() + 7);
  const list = items.filter((s) => (tab === "today" ? sameDay(s.at, now) : s.at >= new Date(y, m, now.getDate()) && s.at < weekEnd));
  const lead = new Date(y, m, 1).getDay();
  return (
    <Panel icon="cal" title="Content Calendar" sub="Posts you have scheduled">
      <div className="row between"><div className="minitabs">{[["today", "Today"], ["week", "Week"], ["month", "Month"]].map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} aria-pressed={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div><b className="small">{now.toLocaleString("en", { month: "long", year: "numeric" })}</b></div>
      {error ? <ErrorBox error={error} /> : tab === "month" ? <div className="mini">{["S", "M", "T", "W", "T", "F", "S"].map((d, i) => <div className="h" key={i}>{d}</div>)}
        {Array.from({ length: lead }, (_, i) => <div key={`e${i}`} />)}
        {Array.from({ length: last }, (_, i) => { const day = i + 1, its = items.filter((s) => s.at.getFullYear() === y && s.at.getMonth() === m && s.at.getDate() === day);
          return <div key={day} className={`d ${its.length ? "has" : ""} ${day === now.getDate() ? "today" : ""}`}><span>{day}</span>{its.slice(0, 1).map((s) => <i key={s.id} title={s.title}>{s.title}</i>)}</div>; })}</div> :
        list.length === 0 ? <p className="mu small">Nothing scheduled {tab === "today" ? "today" : "in the next 7 days"}.</p> : list.map((s) => <div className="li" key={s.id}><span>{s.title}<small className="mu"> {fmt(s.scheduled_at)}</small></span><Badge>{s.execution_status || s.status}</Badge></div>)}
      <Link className="link" to="/calendar">Open the full calendar</Link>
    </Panel>
  );
}

function Insights({ d, ws, days }) {
  const docs = useAsync(() => api(`/workspaces/${ws.id}/content?limit=100`), [ws.id]);
  const usage = useAsync(() => api(`/workspaces/${ws.id}/ai/usage`), [ws.id]);
  const by = {}; (docs.data || []).forEach((x) => { by[x.status] = (by[x.status] || 0) + 1; });
  const colors = { draft: "var(--mu)", review: "var(--wn)", approved: "var(--ai)", published: "var(--pri)", failed: "var(--bd)" };
  const total = Object.values(by).reduce((a, b) => a + b, 0);
  let acc = 0;
  const stops = Object.entries(by).map(([k, n]) => { const a = acc; acc += (n / total) * 100; return `${colors[k] || "var(--mu)"} ${a}% ${acc}%`; }).join(",");
  return (
    <Panel icon="chart" title="Analytics & Insights" sub={`Measured from this workspace, last ${days} days`}>
      <div className="stat4">
        <div><span>Content created</span><b>{d.kpis.content_created.value}</b></div><div><span>Posts published</span><b>{d.kpis.posts_published.value}</b></div>
        <div><span>AI requests this month</span><b>{usage.data ? `${usage.data.requests}/${usage.data.limit}` : "…"}</b></div><div><span>Reach, clicks, leads</span><b className="mu" style={{ fontSize: 13 }}>Not connected</b></div></div>
      <div className="row" style={{ alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: "2 1 300px", minWidth: 0 }}><Chart data={d.series} label={`Content created and posts published, last ${days} days`} lines={[{ key: "content_created", label: "Content created", color: "var(--c1)" }, { key: "posts_published", label: "Posts published", color: "var(--c2)" }]} /></div>
        <div style={{ flex: "1 1 180px" }}><b className="small">Content by status</b>
          {total === 0 ? <p className="mu small">No content yet.</p> : <div className="row" style={{ marginTop: 8 }}><div className="donut" role="img" aria-label={`${total} documents by status`} style={{ background: `conic-gradient(${stops})` }}><div><b>{total}</b>documents</div></div>
            <div className="legend2">{Object.entries(by).map(([k, n]) => <span key={k}><i style={{ background: colors[k] || "var(--mu)" }} />{k} {n}</span>)}</div></div>}</div></div>
      <p className="small mu" style={{ marginBottom: 0 }}>Reach, engagement and conversions appear only after an analytics account is connected. None is connected.</p>
    </Panel>
  );
}

function OwnerPanel({ can, themeCfg, theme }) {
  const owner = can("theme.write");
  const links = [["Theme Studio", "/owner", "pal"], ["User Management", "/team", "users"], ["API Management", "/integrations", "plug"], ["Automation", "/agent", "bot"], ["System Logs", "/audit", "list"], ["Security", "/settings", "lock"]];
  const t = themeCfg?.tokens?.[theme] || {};
  return (
    <Panel icon="crown" title="Owner Console & Theme Studio" sub="Platform settings, themes and system controls">
      <div className="studio">
        <div>{links.map(([l, to, ic]) => <Link key={l} to={to} className="sw2" style={{ textDecoration: "none", color: "var(--ink)" }}><span className="row"><Icon n={ic} />{l}</span><span className="mu">›</span></Link>)}
          <div className="sw2"><span className="row"><Icon n="file" />Billing</span><span className="mu small">Not available</span></div></div>
        <div className="pv"><b className="small">Current colours ({theme})</b>
          <div className="swatches" aria-label="Current theme colours">{["primary", "surface", "text", "success", "warning", "danger"].map((k) => <i key={k} title={k} style={{ background: t[k] || "transparent" }} />)}</div>
          <p className="small mu">{themeCfg ? `Source: ${themeCfg.source} theme.` : "Loading theme…"}</p>
          {owner ? <Link className="btn primary sm" to="/owner">Open Theme Studio</Link> : <p className="small mu"><Icon n="lock" /> Only the Owner can change platform colours.</p>}</div>
      </div>
    </Panel>
  );
}

export default function Dashboard() {
  const { ws, user, can, toast, themeCfg, theme, themeMode, setThemeMode } = useApp();
  const days = 7;
  const { data: d, error, loading, reload } = useAsync(() => api(`/workspaces/${ws.id}/dashboard?days=${days}`), [ws.id]);
  if (loading && !d) return <><h1 className="sr-only">Dashboard</h1><Skeleton rows={6} /></>;
  if (error) return <><h1>Dashboard</h1><ErrorBox error={error} retry={reload} /></>;
  const k = d.kpis, a = d.agent, [sysTitle, sysKind] = SYS[a.state];
  const wp = d.integrations.filter((i) => i.provider === "wordpress");
  return (
    <>
      <div className="dash">
        <div className="col">
          <section className="hero" aria-label="Welcome">
            <div className="txt"><h1>{hello()}, {user.full_name}</h1><p style={{ color: "var(--ink)" }}>Your Autonomous Marketing Command Center</p>
              <p>Plan, create, review and publish campaigns with AI agents. Every post waits for your approval.</p>
              <div className="btnrow">{can("campaign.write") && <Link className="btn primary" to="/campaigns?new=1">Create New Campaign</Link>}<Link className="btn" to="/agent"><Icon n="bot" />Open Control Center</Link></div></div>
            <div className="art"><RobotArt /><span className="tag" aria-hidden="true">AI AGENTS<br />WORKING FOR YOUR<br />GROWTH</span></div>
          </section>
          <div className="kpis">
            <div className="card kpi2"><span className="tile"><Icon n="megaphone" /></span><div className="t"><span>Total Campaigns</span><b>{k.campaigns.total}</b><small>{k.campaigns.by_status.ACTIVE || 0} active</small></div></div>
            <div className="card kpi2"><span className="tile"><Icon n="send" /></span><div className="t"><span>Published Posts</span><b>{k.posts_published.value}</b><small>{delta(k.posts_published.value, k.posts_published.previous)}</small></div></div>
            <Link to="/analytics" className="card kpi2" style={{ textDecoration: "none", color: "inherit" }} title={k.engagement_rate.reason}><span className="tile"><Icon n="chart" /></span><div className="t"><span>Engagement Rate</span><b style={{ fontSize: 17 }} className="mu">Not connected</b><small>Needs an analytics account</small></div></Link>
            <div className="card kpi2"><span className="tile"><Icon n="bot" /></span><div className="t"><span>Active Agents</span><b>{d.agents.active}/{d.agents.total}</b><small>{d.agents.total ? "Agents added to this workspace" : "No agents added yet"}</small></div></div>
          </div>
        </div>
        <aside className="col" aria-label="System status">
          <section className="card"><div className="ph2"><span className="tile"><Icon n="shield" /></span><div><h2>{sysTitle}</h2><p>{a.reason}</p></div></div>
            <span className={`pill ${sysKind}`}>Agent: {a.state}</span>
            <div className="sidecard" style={{ marginTop: 12 }}><h4>Quick stats</h4>
              {[["Active campaigns", d.quick.active_campaigns], ["Content in review", d.quick.content_in_review], ["Scheduled posts", d.quick.scheduled], ["Published today", d.quick.published_today]].map(([l, n]) => <div className="li" key={l}><span>{l}</span><b>{n}</b></div>)}</div>
            <div className="sidecard"><h4>Connected integrations</h4>
              {wp.length ? wp.map((i) => <div className="li" key={i.id}><span>{i.label}<small className="mu"> WordPress</small></span><Badge>{i.status}</Badge></div>) : <div className="li"><span>WordPress</span><span className="badge">Not connected</span></div>}
              {["Instagram", "LinkedIn", "Facebook"].map((n) => <div className="li" key={n}><span>{n}</span><span className="badge">Not available yet</span></div>)}</div>
          </section>
        </aside>
      </div>
      <div className="trio" style={{ marginTop: 16 }}><CampaignPlanner d={d} can={can} /><ContentStudio ws={ws} can={can} toast={toast} /><MiniCalendar ws={ws} /></div>
      <div className="trio" style={{ marginTop: 16, gridTemplateColumns: "minmax(0,1.3fr) minmax(0,1fr) minmax(0,.8fr)" }}>
        <Insights d={d} ws={ws} days={days} /><OwnerPanel can={can} themeCfg={themeCfg} theme={theme} />
        <section className="card"><div className="ph2"><span className="tile"><Icon n="pal" /></span><div><h2>Theme & Appearance</h2></div></div>
          <div className="seg2" role="group" aria-label="Display mode"><button className={themeMode === "dark" ? "on" : ""} aria-pressed={theme === "dark" && themeMode !== "system"} onClick={() => setThemeMode("dark")}>Dark mode</button><button className={themeMode === "light" ? "on" : ""} aria-pressed={theme === "light" && themeMode !== "system"} onClick={() => setThemeMode("light")}>Light mode</button></div>
          <div className="ph2" style={{ marginTop: 14 }}><span className="tile"><Icon n="hand" /></span><div><h2>Gesture Controls</h2></div></div>
          <GesturePanel /></section>
      </div>
    </>
  );
}
