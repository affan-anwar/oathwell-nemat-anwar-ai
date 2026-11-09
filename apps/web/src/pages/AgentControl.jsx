import { useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { Badge, ErrorBox, PageHeader, Skeleton, fmt, useAsync } from "../ui.jsx";

const KIND = { Running: "ok", Paused: "wn", "Needs attention": "bd", Unavailable: "" };

export default function AgentControl() {
  const { ws } = useApp();
  const b = `/workspaces/${ws.id}`;
  const { data, error, loading, reload } = useAsync(async () => {
    const [dash, jobs, usage, act] = await Promise.all([api(`${b}/dashboard?days=7`), api(`${b}/jobs`), api(`${b}/ai/usage`), api(`${b}/activity?limit=15`)]);
    return { dash, jobs, usage, act };
  }, [ws.id]);
  useEffect(() => { const t = setInterval(reload, 20000); return () => clearInterval(t); }, [reload]);
  if (loading && !data) return <><PageHeader title="Agent Control Center" /><Skeleton rows={4} /></>;
  if (error) return <><PageHeader title="Agent Control Center" /><ErrorBox error={error} retry={reload} /></>;
  const { dash, jobs, usage, act } = data, a = dash.agent;
  return (
    <>
      <PageHeader title="Agent Control Center" sub="What the agent is doing and what needs a person" />
      <div className="grid2">
        <section className="card"><h2>Agent status</h2>
          <div className="row wrap"><span className={`pill ${KIND[a.state]}`}>{a.state}</span></div>
          <p className="mu small">{a.reason}</p>
          <div className="li"><span>Scheduler worker last seen</span><b>{a.worker_last_seen ? fmt(a.worker_last_seen) : "never"}</b></div>
          <div className="li"><span>Next scheduled task</span><b>{a.next_task ? `${a.next_task.title} · ${fmt(a.next_task.scheduled_at)}` : "none"}</b></div>
          <p className="small mu">Pause and resume are in the top bar (admins). Failed and unclear jobs are handled on the <Link to="/publishing">Publishing</Link> page.</p></section>
        <section className="card"><h2>Queue</h2>
          {Object.keys(jobs.counts).length === 0 ? <p className="mu">No jobs yet.</p> : Object.entries(jobs.counts).map(([k, v]) => <div className="li" key={k}><span>{k}</span><b>{v}</b></div>)}</section>
        <section className="card"><h2>AI usage this month</h2>
          <div className="li"><span>Requests</span><b>{usage.requests} of {usage.limit}</b></div>
          <div className="li"><span>Input / output tokens</span><b>{usage.input_tokens.toLocaleString()} / {usage.output_tokens.toLocaleString()}</b></div>
          <div className="li"><span>Estimated cost</span><b>{usage.estimated_cost == null ? "Unavailable" : `${usage.estimated_cost} ${usage.currency}`}</b></div>
          <p className="small mu">{usage.cost_note}</p></section>
        <section className="card"><h2>Recent jobs and events</h2>
          {jobs.items.slice(0, 5).map((j) => <div className="li" key={j.approval_id}><span>{j.title}<small className="mu"> {j.provider_summary || j.next_action}</small></span><Badge>{j.state}</Badge></div>)}
          {act.map((e) => <div className="li" key={e.id}><span>{e.title}{e.automated && <small className="mu"> · automated</small>}<small className="mu"> {fmt(e.created_at)}</small></span><Badge kind={e.outcome === "success" ? "ok" : "wn"}>{e.outcome}</Badge></div>)}
          {jobs.items.length === 0 && act.length === 0 && <p className="mu">Nothing has happened yet.</p>}</section>
      </div>
    </>
  );
}
