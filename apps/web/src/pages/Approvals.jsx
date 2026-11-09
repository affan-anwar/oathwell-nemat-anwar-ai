import { useState } from "react";
import { api, qs } from "../api.js";
import { useApp } from "../state.jsx";
import { Badge, Confirm, Empty, ErrorBox, PageHeader, Skeleton, fmt, useAsync } from "../ui.jsx";

const TABS = ["", "PENDING", "APPROVED", "REJECTED", "EXPIRED", "INVALIDATED"];

function Detail({ id, ws, can, toast, onChanged }) {
  const base = `/workspaces/${ws.id}/approvals/${id}`;
  const { data: a, error, loading, reload } = useAsync(() => api(base), [id]);
  const [comment, setComment] = useState(""); const [confirm, setConfirm] = useState(null); const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  if (loading) return <Skeleton rows={5} />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  const act = async (fn) => { setBusy(true); try { await fn(); } catch (x) { toast(x.message, "bd"); } finally { setBusy(false); setConfirm(null); reload(); onChanged(); } };
  const decide = (decision) => act(async () => { await api(`${base}/decision`, { method: "POST", body: { decision, comment: comment || null } }); toast(`Decision saved: ${decision.replace("_", " ")}`); });
  const run = () => act(async () => {
    const r = await api(`${base}/execute`, { method: "POST" }); setResult(r.execution);
    toast(r.execution.status === "PUBLISHED" ? "Published. The site confirmed it." : r.execution.status === "UNCLEAR" ? "Result unclear. Check the site before retrying." : "Publishing failed.", r.execution.status === "PUBLISHED" ? "ok" : "bd");
  });
  return (
    <div className="card">
      <div className="row between"><h2>{a.preview.title}</h2><Badge>{a.status}</Badge></div>
      <div className="meta">
        <div><span className="mu">Action</span>Publish blog post</div><div><span className="mu">Destination</span>{a.preview.destination}</div>
        <div><span className="mu">Version</span>v{a.preview.version_number} · {a.preview.source}</div><div><span className="mu">Content hash</span><code>{a.content_hash.slice(0, 12)}</code></div>
        <div><span className="mu">Scheduled</span>{a.scheduled_at ? fmt(a.scheduled_at) : "Not scheduled"}</div><div><span className="mu">Risk</span>{a.preview.risk}</div><div><span className="mu">Expires</span>{fmt(a.expires_at)}</div>
      </div>
      <div className="prev">{a.preview.body}</div>
      {a.block_reason && <div className="alert wn">Waiting: {a.block_reason}</div>}
      {a.comment && <p className="small"><span className="mu">Reviewer comment:</span> {a.comment}</p>}
      {a.status === "PENDING" && can("approval.decide") && <>
        <textarea aria-label="Comment" placeholder="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
        <div className="row wrap"><button className="btn primary" disabled={busy} onClick={() => decide("approve")}>Approve this version</button>
          <button className="btn" disabled={busy} onClick={() => decide("request_changes")}>Request changes</button><button className="btn danger-o" disabled={busy} onClick={() => decide("reject")}>Reject</button></div></>}
      {a.status === "PENDING" && !can("approval.decide") && <p className="mu">An admin or owner must decide on this request.</p>}
      {a.status === "APPROVED" && <div className="row wrap">
        {a.scheduled_at && new Date(a.scheduled_at + "Z") > new Date() ? <span className="mu">Publishes automatically at {fmt(a.scheduled_at)}. The scheduler worker must be running.</span> :
          can("publish.execute") && <button className="btn primary" disabled={busy} onClick={() => setConfirm("run")}>Publish now</button>}
        {can("approval.decide") && <button className="btn danger-o" disabled={busy} onClick={() => setConfirm("revoke")}>Revoke approval</button>}</div>}
      {result && <div className={`alert ${result.status === "PUBLISHED" ? "ok" : "wn"}`}>{result.status}: {result.detail} {result.external_url && <a href={result.external_url} target="_blank" rel="noreferrer">Open post</a>}</div>}
      {confirm === "run" && <Confirm title="Publish live?" confirmLabel="Publish now" busy={busy} onClose={() => setConfirm(null)} onConfirm={run}>
        <p>This publishes “{a.preview.title}” to <b>{a.preview.destination}</b>. It becomes public immediately.</p></Confirm>}
      {confirm === "revoke" && <Confirm title="Revoke approval?" danger confirmLabel="Revoke" busy={busy} onClose={() => setConfirm(null)} onConfirm={() => act(async () => { await api(`${base}/revoke`, { method: "POST" }); toast("Approval revoked"); })}>
        <p>The content will not be publishable until it is approved again.</p></Confirm>}
    </div>
  );
}

export default function Approvals() {
  const { ws, can, toast } = useApp();
  const [tab, setTab] = useState("PENDING"); const [sel, setSel] = useState(null);
  const { data, error, loading, reload } = useAsync(() => api(`/workspaces/${ws.id}/approvals${qs({ status: tab, limit: 100 })}`), [ws.id, tab]);
  return (
    <>
      <PageHeader title="Approval inbox" sub="Content is published only after the exact version is approved" />
      <div className="tabs" role="tablist">{TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => { setTab(t); setSel(null); }}>{t || "ALL"}</button>)}</div>
      <div className="split">
        <div>{loading ? <Skeleton /> : error ? <ErrorBox error={error} retry={reload} /> : data.length === 0 ? <div className="card"><Empty title="Nothing here">No approval requests with this status.</Empty></div> :
          data.map((a) => <button key={a.id} className={`item ${sel === a.id ? "sel" : ""}`} onClick={() => setSel(a.id)}><span className="row between"><Badge>{a.status}</Badge><small className="mu">{fmt(a.created_at)}</small></span><b>{a.action.replace("_", " ")}</b><small className="mu">v hash {a.content_hash.slice(0, 8)}</small></button>)}</div>
        <div>{sel ? <Detail key={sel} id={sel} ws={ws} can={can} toast={toast} onChanged={reload} /> : <div className="card"><Empty title="Select a request">You will see the exact content, destination and risk before deciding.</Empty></div>}</div>
      </div>
    </>
  );
}
