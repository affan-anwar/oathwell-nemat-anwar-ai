import { useState } from "react";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { Badge, Confirm, ErrorBox, Field, PageHeader, Skeleton, useAsync } from "../ui.jsx";

const ADMIN_CAN = ["viewer", "editor", "research_agent", "analytics_agent", "content_agent", "publishing_agent"]; // convenience only; the server decides

export default function Team() {
  const { ws, can, perms, user, toast } = useApp();
  const base = `/workspaces/${ws.id}/members`;
  const { data, error, loading, reload } = useAsync(() => api(base), [ws.id]);
  const [busy, setBusy] = useState(false); const [drop, setDrop] = useState(null);
  const owner = perms.role === "owner";
  const roles = perms.roles.filter((r) => r.role !== "owner" && (owner || ADMIN_CAN.includes(r.role)));
  const manage = can("member.manage");
  const act = async (fn, ok) => { try { await fn(); toast(ok); reload(); } catch (x) { toast(x.message, "bd"); reload(); } };
  const add = async (e) => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)); setBusy(true);
    try { await api(base, { method: "POST", body: f }); toast("Member added"); e.target.reset(); reload(); } catch (x) { toast(x.message, "bd"); } finally { setBusy(false); }
  };
  const editable = (m) => manage && m.user_id !== user.id && m.role !== "owner" && (owner || ADMIN_CAN.includes(m.role));
  return (
    <>
      <PageHeader title="Team" sub="People and AI agents with access to this workspace" />
      <div className="grid2">
        <div className="card">{loading ? <Skeleton /> : error ? <ErrorBox error={error} retry={reload} /> : data.map((m) => (
          <div className="li" key={m.user_id}>
            <span><b>{m.full_name}</b><small className="mu"> {m.email}</small>{m.user_id === user.id && <small className="mu"> (you)</small>}</span>
            <span className="row">
              {m.suspended && <Badge kind="bd">suspended</Badge>}
              {editable(m) ? <select aria-label={`Role for ${m.email}`} value={m.role} onChange={(e) => act(() => api(`${base}/${m.user_id}`, { method: "PATCH", body: { role: e.target.value } }), "Role changed")}>
                {[...roles.map((r) => r.role), ...(roles.some((r) => r.role === m.role) ? [] : [m.role])].map((r) => <option key={r} value={r}>{perms.roles.find((x) => x.role === r)?.label || r}</option>)}</select> : <Badge kind={m.role === "owner" ? "ok" : ""}>{m.label}</Badge>}
              {editable(m) && <><button className="btn sm" onClick={() => act(() => api(`${base}/${m.user_id}`, { method: "PATCH", body: { suspended: !m.suspended } }), m.suspended ? "Access restored" : "Access suspended")}>{m.suspended ? "Restore" : "Suspend"}</button>
                <button className="btn sm danger-o" onClick={() => setDrop(m)}>Remove</button></>}
            </span></div>))}
          {data?.some((m) => m.role === "owner") && <p className="small mu" style={{ marginBottom: 0 }}>The Owner is protected: nobody can demote, suspend or remove the Owner.</p>}
        </div>
        {manage ? <form className="card form" onSubmit={add}><h2>Add a member</h2>
          <Field label="Email" hint="They must register first"><input name="email" type="email" required /></Field>
          <Field label="Role"><select name="role">{roles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}</select></Field>
          <button className="btn primary" disabled={busy}>Add member</button></form> : <div className="card"><p className="mu">Only the Owner and Admins can add people.</p></div>}
      </div>
      <section className="card"><h2>What each role can do</h2><p className="sub">The server checks these permissions on every request.</p>
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Table, scroll sideways if needed"><table className="table2"><thead><tr><th>Role</th><th>Permissions</th></tr></thead>
          <tbody>{perms.roles.map((r) => <tr key={r.role}><td><b>{r.label}</b></td><td className="small">{r.permissions.map((p) => <span className="chip2" key={p}>{p}</span>)}</td></tr>)}</tbody></table></div></section>
      {drop && <Confirm title="Remove this person?" danger confirmLabel="Remove" onClose={() => setDrop(null)} onConfirm={async () => { await act(() => api(`${base}/${drop.user_id}`, { method: "DELETE" }), "Member removed"); setDrop(null); }}>
        <p>{drop.email} will lose all access to this workspace. Their past work stays.</p></Confirm>}
    </>
  );
}
