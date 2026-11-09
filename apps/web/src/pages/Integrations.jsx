import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { Badge, Confirm, Empty, ErrorBox, Field, Modal, PageHeader, Skeleton, fmt, useAsync } from "../ui.jsx";

export default function Integrations() {
  const { ws, can, toast } = useApp();
  const base = `/workspaces/${ws.id}/integrations`;
  const { data, error, loading, reload } = useAsync(() => api(base), [ws.id]);
  const [form, setForm] = useState(false); const [drop, setDrop] = useState(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState("");
  const [params] = useSearchParams();
  useEffect(() => { if (params.get("connect") === "wordpress" && can("integration.manage")) setForm(true); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const test = async (i) => {
    setBusy(i.id);
    try { const r = await api(`${base}/${i.id}/test`, { method: "POST" }); toast(r.status === "connected" ? "Connection verified" : r.status_detail, r.status === "connected" ? "ok" : "bd"); }
    catch (x) { toast(x.message, "bd"); } finally { setBusy(""); reload(); }
  };
  const connect = async (e) => {
    e.preventDefault(); setErr("");
    try { await api(`${base}/wordpress`, { method: "POST", body: Object.fromEntries(new FormData(e.target)) }); toast("Saved. Run the connection test to verify it."); setForm(false); reload(); }
    catch (x) { setErr(x.message); }
  };
  return (
    <>
      <PageHeader title="Integrations" sub="A service shows Connected only after a real test succeeds">
        {can("integration.manage") && <button className="btn primary" onClick={() => { setForm(true); setErr(""); }}>Connect WordPress</button>}
      </PageHeader>
      {loading ? <Skeleton /> : error ? <ErrorBox error={error} retry={reload} /> : data.length === 0 ?
        <div className="card"><Empty title="No accounts connected">Connect a WordPress site to publish approved blog posts. Other channels are not built yet.</Empty></div> :
        <div className="grid2">{data.map((i) => (
          <div className="card" key={i.id}>
            <div className="row between"><div><b>{i.label}</b><div className="mu small">WordPress · {i.site_url}</div></div><Badge>{i.status}</Badge></div>
            <p className="small mu">{i.status_detail || "Not tested yet"}<br />Last tested: {fmt(i.last_tested_at)}</p>
            {can("integration.manage") && i.status !== "disconnected" && <div className="row">
              <button className="btn" disabled={busy === i.id} onClick={() => test(i)}>{busy === i.id ? "Testing…" : "Test connection"}</button>
              <button className="btn danger-o" onClick={() => setDrop(i)}>Disconnect</button></div>}
          </div>))}</div>}
      <div className="card info"><b>Not available yet:</b> LinkedIn, Instagram, email delivery, Google Ads and analytics connectors. They need provider app registration and are not built.</div>
      {form && <Modal title="Connect WordPress" onClose={() => setForm(false)}>
        <form className="form" onSubmit={connect}>
          <Field label="Label"><input name="label" required placeholder="Company blog" /></Field>
          <Field label="Site URL" hint="Must be https. Internal addresses are blocked."><input name="site_url" type="url" required placeholder="https://blog.example.com" /></Field>
          <Field label="Username"><input name="username" required autoComplete="off" /></Field>
          <Field label="Application password" hint="Create it in WordPress under Users, Profile. It is stored encrypted and never shown again."><input name="app_password" type="password" required minLength={8} autoComplete="off" /></Field>
          {err && <div className="alert bd" role="alert">{err}</div>}
          <div className="mf"><button type="button" className="btn" onClick={() => setForm(false)}>Cancel</button><button className="btn primary">Save</button></div>
        </form></Modal>}
      {drop && <Confirm title="Disconnect this account?" danger confirmLabel="Disconnect" onClose={() => setDrop(null)} onConfirm={async () => { try { await api(`${base}/${drop.id}`, { method: "DELETE" }); toast("Disconnected. Also revoke the application password in WordPress."); } catch (x) { toast(x.message, "bd"); } setDrop(null); reload(); }}>
        <p>The stored password is deleted. Queued publishing to “{drop.label}” will be blocked.</p></Confirm>}
    </>
  );
}
