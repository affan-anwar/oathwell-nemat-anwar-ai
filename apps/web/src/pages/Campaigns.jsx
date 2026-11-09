import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, qs } from "../api.js";
import { useApp } from "../state.jsx";
import { Badge, Confirm, Empty, ErrorBox, Field, Modal, PageHeader, Skeleton, useAsync } from "../ui.jsx";

const NEXT = { DRAFT: ["ACTIVE", "CANCELLED", "ARCHIVED"], ACTIVE: ["PAUSED", "COMPLETED", "CANCELLED"], PAUSED: ["ACTIVE", "CANCELLED"], COMPLETED: ["ARCHIVED"], CANCELLED: ["ARCHIVED"], ARCHIVED: [] };
const ZONES = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : ["UTC", "Asia/Kolkata"];

function CampaignForm({ initial, onSave, onClose }) {
  const [f, setF] = useState({ name: "", objective: "", audience: "", start_date: "", end_date: "", timezone: "UTC", ...initial, channels: (initial?.channels || []).join(", ") });
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      await onSave({ ...f, channels: f.channels.split(",").map((s) => s.trim()).filter(Boolean), start_date: f.start_date || null, end_date: f.end_date || null });
    } catch (x) { setErr(x.message); setBusy(false); }
  };
  return (
    <Modal title={initial ? "Edit campaign" : "New campaign"} onClose={onClose}>
      <form onSubmit={submit} className="form">
        <Field label="Name"><input required maxLength={200} value={f.name} onChange={set("name")} /></Field>
        <Field label="Objective"><textarea value={f.objective || ""} onChange={set("objective")} /></Field>
        <Field label="Audience"><textarea value={f.audience || ""} onChange={set("audience")} /></Field>
        <Field label="Channels" hint="Comma separated, for example blog, linkedin"><input value={f.channels} onChange={set("channels")} /></Field>
        <div className="grid2 tight">
          <Field label="Start date"><input type="date" value={f.start_date || ""} onChange={set("start_date")} /></Field>
          <Field label="End date"><input type="date" value={f.end_date || ""} onChange={set("end_date")} /></Field>
        </div>
        <Field label="Time zone"><select value={f.timezone} onChange={set("timezone")}>{ZONES.map((z) => <option key={z}>{z}</option>)}</select></Field>
        {err && <div className="alert bd" role="alert">{err}</div>}
        <div className="mf"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy}>{busy ? "Saving…" : "Save campaign"}</button></div>
      </form>
    </Modal>
  );
}

export default function Campaigns() {
  const { ws, can, toast } = useApp();
  const [status, setStatus] = useState(""); const [q, setQ] = useState("");
  const [form, setForm] = useState(null); const [confirm, setConfirm] = useState(null);
  const [params] = useSearchParams();
  useEffect(() => { if (params.get("new") && can("campaign.write")) setForm({}); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const base = `/workspaces/${ws.id}/campaigns`;
  const { data, error, loading, reload } = useAsync(() => api(`${base}${qs({ status, limit: 100 })}`), [ws.id, status]);
  const move = async (c, to) => {
    try { await api(`${base}/${c.id}/transition`, { method: "POST", body: { to } }); toast(`Campaign is now ${to.toLowerCase()}`); reload(); }
    catch (x) { toast(x.message, "bd"); }
    setConfirm(null);
  };
  const rows = (data || []).filter((c) => c.name.toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <PageHeader title="Campaigns" sub="Plan and track campaigns">
        {can("campaign.write") && <button className="btn primary" onClick={() => setForm({})}>New campaign</button>}
      </PageHeader>
      <div className="toolbar">
        <input placeholder="Search by name" aria-label="Search campaigns" value={q} onChange={(e) => setQ(e.target.value)} />
        <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All except archived</option>{Object.keys(NEXT).map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>
      {loading ? <Skeleton /> : error ? <ErrorBox error={error} retry={reload} /> : rows.length === 0 ?
        <div className="card"><Empty title="No campaigns yet" action={can("campaign.write") && <button className="btn primary" onClick={() => setForm({})}>Create the first campaign</button>}>Campaigns you create are saved to your workspace.</Empty></div> :
        <div className="card flush table-wrap"><table>
          <thead><tr><th>Name</th><th>Status</th><th>Dates</th><th>Channels</th><th /></tr></thead>
          <tbody>{rows.map((c) => (
            <tr key={c.id}>
              <td><b>{c.name}</b><div className="mu small">{c.objective?.slice(0, 80)}</div></td>
              <td><Badge>{c.status}</Badge></td>
              <td className="small">{c.start_date || "—"} → {c.end_date || "—"}<div className="mu">{c.timezone}</div></td>
              <td className="small">{c.channels.join(", ") || "—"}</td>
              <td className="actions">{can("campaign.write") && <>
                {!["ARCHIVED", "CANCELLED", "COMPLETED"].includes(c.status) && <button className="btn sm" onClick={() => setForm(c)}>Edit</button>}
                {NEXT[c.status].map((to) => <button key={to} className={`btn sm ${to === "CANCELLED" || to === "ARCHIVED" ? "danger-o" : ""}`} onClick={() => (to === "CANCELLED" || to === "ARCHIVED" ? setConfirm({ c, to }) : move(c, to))}>{to.toLowerCase()}</button>)}
              </>}</td>
            </tr>))}</tbody></table></div>}
      {form && <CampaignForm initial={form.id ? form : null} onClose={() => setForm(null)} onSave={async (body) => {
        await api(form.id ? `${base}/${form.id}` : base, { method: form.id ? "PATCH" : "POST", body });
        toast("Campaign saved"); setForm(null); reload();
      }} />}
      {confirm && <Confirm title={`${confirm.to === "CANCELLED" ? "Cancel" : "Archive"} campaign?`} danger confirmLabel={confirm.to === "CANCELLED" ? "Cancel campaign" : "Archive"} onClose={() => setConfirm(null)} onConfirm={() => move(confirm.c, confirm.to)}>
        <p>“{confirm.c.name}” will be {confirm.to.toLowerCase()}. This cannot be undone.</p></Confirm>}
    </>
  );
}
