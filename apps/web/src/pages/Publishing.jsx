import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { Badge, Confirm, Empty, ErrorBox, PageHeader, Skeleton, fmt, useAsync } from "../ui.jsx";

const STATES = ["", "pending", "processing", "unclear", "failed", "blocked", "published", "expired"];

export default function Publishing() {
  const { ws, can, toast } = useApp();
  const [state, setState] = useState(""); const [busy, setBusy] = useState(""); const [retry, setRetry] = useState(null);
  const { data, error, loading, reload } = useAsync(() => api(`/workspaces/${ws.id}/jobs${state ? `?state=${state}` : ""}`), [ws.id, state]);
  const [all, setAll] = useState(null);
  useEffect(() => { api(`/workspaces/${ws.id}/jobs`).then(setAll).catch(() => {}); }, [ws.id, data]);
  useEffect(() => { const t = setInterval(reload, 20000); return () => clearInterval(t); }, [reload]);
  const check = async (j) => {
    setBusy(j.approval_id);
    try {
      const r = await api(`/workspaces/${ws.id}/approvals/${j.approval_id}/reconcile`, { method: "POST" });
      toast(r.detail, r.outcome === "published" || r.outcome === "not_found" ? "ok" : "wn");
    } catch (x) { toast(x.message, "bd"); } finally { setBusy(""); reload(); }
  };
  const doRetry = async () => {
    setBusy(retry.approval_id);
    try { const r = await api(`/workspaces/${ws.id}/approvals/${retry.approval_id}/execute`, { method: "POST" }); toast(r.execution.status === "PUBLISHED" ? "Published. The site confirmed it." : `${r.execution.status}: ${r.execution.detail}`, r.execution.status === "PUBLISHED" ? "ok" : "bd"); }
    catch (x) { toast(x.message, "bd"); } finally { setBusy(""); setRetry(null); reload(); }
  };
  const counts = all?.counts || {};
  return (
    <>
      <PageHeader title="Publishing" sub="Every approved post and what happened to it" />
      <div className="tabs" role="tablist">{STATES.map((s) => <button key={s} role="tab" aria-selected={state === s} className={state === s ? "on" : ""} onClick={() => setState(s)}>{s || "all"}{s && counts[s] ? ` (${counts[s]})` : ""}</button>)}</div>
      {loading ? <Skeleton rows={4} /> : error ? <ErrorBox error={error} retry={reload} /> : data.items.length === 0 ?
        <div className="card"><Empty title="No publishing jobs here">Posts appear here after they are approved. Nothing is hidden: published, failed and unclear results all show.</Empty></div> :
        <div className="card flush table-wrap"><table>
          <thead><tr><th>Post</th><th>State</th><th>Last attempt</th><th>What happened</th><th>Next step</th><th /></tr></thead>
          <tbody>{data.items.map((j) => (
            <tr key={j.approval_id}>
              <td><b>{j.title}</b><div className="mu small">{j.destination}{j.scheduled_at ? ` · scheduled ${fmt(j.scheduled_at)}` : ""}</div></td>
              <td><Badge>{j.state}</Badge>{j.trigger && <div className="mu small">by {j.trigger}</div>}</td>
              <td className="small">{fmt(j.last_attempt_at)}</td>
              <td className="small">{j.provider_summary || "—"}{j.external_url && <> <a href={j.external_url} target="_blank" rel="noreferrer">Open post</a></>}</td>
              <td className="small">{j.next_action}</td>
              <td className="actions">
                {can("publish.execute") && j.can_check_site && <button className="btn sm primary" disabled={busy === j.approval_id} onClick={() => check(j)}>{busy === j.approval_id ? "Checking…" : "Check the site"}</button>}
                {can("publish.execute") && j.retry_eligible && <button className="btn sm" disabled={busy === j.approval_id} onClick={() => setRetry(j)}>Retry</button>}
                <Link className="btn sm" to="/approvals">Approval</Link>
              </td>
            </tr>))}</tbody></table></div>}
      {retry && <Confirm title="Retry publishing?" confirmLabel="Retry now" busy={!!busy} onClose={() => setRetry(null)} onConfirm={doRetry}>
        <p>This sends “{retry.title}” to <b>{retry.destination}</b> again. Only retry after the cause of the failure is fixed.</p></Confirm>}
    </>
  );
}
