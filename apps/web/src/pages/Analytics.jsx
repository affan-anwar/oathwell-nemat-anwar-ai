import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Chart from "../Chart.jsx";
import { useApp } from "../state.jsx";
import { ErrorBox, PageHeader, Skeleton, fmt, useAsync } from "../ui.jsx";

const UNAVAILABLE = ["Reach", "Impressions", "Clicks", "Engagement rate", "Conversions"];

export default function Analytics() {
  const { ws } = useApp();
  const [days, setDays] = useState(30);
  const { data: d, error, loading, reload } = useAsync(() => api(`/workspaces/${ws.id}/dashboard?days=${days}`), [ws.id, days]);
  const exportCsv = () => {
    const rows = ["date,content_created,posts_published", ...d.series.map((p) => `${p.date},${p.content_created},${p.posts_published}`)];
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([rows.join("\n")], { type: "text/csv" })); a.download = `workflow-activity-${days}d.csv`; a.click();
  };
  return (
    <>
      <PageHeader title="Analytics" sub="Measured results only">
        <select aria-label="Date range" value={days} onChange={(e) => setDays(+e.target.value)}>{[7, 14, 30, 90].map((n) => <option key={n} value={n}>Last {n} days</option>)}</select>
        <button className="btn" disabled={!d} onClick={exportCsv}>Export CSV</button>
      </PageHeader>
      <div className="alert wn" style={{ display: "block" }}><b>No analytics source is connected.</b> Reach, clicks and engagement come from platforms like Google Analytics or Meta. Those connectors are not built yet, so no such numbers are shown. <Link to="/integrations">Open integrations</Link></div>
      {loading && !d ? <Skeleton rows={4} /> : error ? <ErrorBox error={error} retry={reload} /> : <>
        <section className="card"><h2>Publishing activity</h2>
          <p className="sub">Source: this workspace's own records. Computed {fmt(new Date().toISOString().replace("Z", ""))}. Posts count only after the site confirmed them.</p>
          <Chart data={d.series} label={`Content created and posts published, last ${days} days`}
            lines={[{ key: "content_created", label: "Content created", color: "var(--pri)" }, { key: "posts_published", label: "Posts published", color: "var(--ai)" }]} /></section>
        <section className="card"><h2>Metrics from analytics providers</h2>
          {UNAVAILABLE.map((m) => <div className="li" key={m}><span>{m}</span><span className="badge">Unavailable: not connected</span></div>)}</section></>}
    </>
  );
}
