import { useState } from "react";
import { api, qs } from "../api.js";
import { useApp } from "../state.jsx";
import { Badge, Empty, ErrorBox, PageHeader, Skeleton, fmt, useAsync } from "../ui.jsx";

export default function Audit() {
  const { ws, can } = useApp();
  const [page, setPage] = useState(0); const size = 25;
  const { data, error, loading, reload } = useAsync(() => (can("audit.read") ? api(`/workspaces/${ws.id}/audit${qs({ limit: size, offset: page * size })}`) : Promise.resolve(null)), [ws.id, page]);
  if (!can("audit.read")) return <><PageHeader title="Audit Log" /><div className="card"><Empty title="Admins only">Your role cannot view the audit log.</Empty></div></>;
  return (
    <>
      <PageHeader title="Audit Log" sub="Who did what, and the outcome" />
      {loading ? <Skeleton rows={6} /> : error ? <ErrorBox error={error} retry={reload} /> : data.length === 0 ? <div className="card"><Empty title="No events">Nothing recorded on this page.</Empty></div> :
        <div className="card flush table-wrap"><table><thead><tr><th>Time</th><th>Action</th><th>Target</th><th>Outcome</th><th>Details</th></tr></thead>
          <tbody>{data.map((e) => <tr key={e.id}><td className="small">{fmt(e.created_at)}</td><td>{e.action}</td><td className="small">{e.target_type}</td><td><Badge kind={e.outcome === "success" ? "ok" : "wn"}>{e.outcome}</Badge></td><td className="small mu">{Object.keys(e.detail || {}).length ? JSON.stringify(e.detail) : "—"}</td></tr>)}</tbody></table></div>}
      <div className="row" style={{ marginTop: 12 }}><button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button><span className="mu">Page {page + 1}</span><button className="btn" disabled={!data || data.length < size} onClick={() => setPage(page + 1)}>Next</button></div>
    </>
  );
}
