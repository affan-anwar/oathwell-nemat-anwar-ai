import { useState } from "react";
import { api, setToken } from "../api.js";
import { useApp } from "../state.jsx";
import { GesturePanel } from "../GestureControl.jsx";
import { ErrorBox, Field, PageHeader, Skeleton, useAsync } from "../ui.jsx";

export default function Settings() {
  const { user, ws, toast, logout, themeMode, setThemeMode, themeLocked } = useApp();
  const { data: u, error, loading, reload } = useAsync(() => api(`/workspaces/${ws.id}/ai/usage`), [ws.id]);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const change = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    const f = Object.fromEntries(new FormData(e.target));
    try { const r = await api("/auth/change-password", { method: "POST", body: f }); setToken(r.access_token); toast("Password changed. Other devices were signed out."); e.target.reset(); }
    catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <>
      <PageHeader title="Settings" sub={user.email} />
      <div className="grid2">
        <form className="card form" onSubmit={change}>
          <h2>Change password</h2>
          <Field label="Current password"><input name="current_password" type="password" required autoComplete="current-password" /></Field>
          <Field label="New password" hint="At least 10 characters"><input name="new_password" type="password" required minLength={10} autoComplete="new-password" /></Field>
          {err && <div className="alert bd" role="alert">{err}</div>}
          <button className="btn primary" disabled={busy}>{busy ? "Saving…" : "Change password"}</button>
        </form>
        <div className="card">
          <h2>Appearance</h2>
          <p className="mu">Dark is the default. Choose "Match my system" to follow your device, including when it changes.</p>
          {themeLocked && <p className="small" role="status" style={{ color: "var(--wn)" }}>The Owner has set the display mode for everyone.</p>}
          <select aria-label="Appearance" value={themeMode} disabled={themeLocked} onChange={(e) => setThemeMode(e.target.value)}>
            <option value="dark">Dark (default)</option><option value="light">Light</option><option value="system">Match my system</option></select>
        </div>
        <div className="card"><h2>Gesture controls</h2><p className="mu">Optional. Uses your camera only after you switch it on and allow it.</p><GesturePanel /></div>
        <div className="card">
          <h2>Sessions</h2>
          <p className="mu">Signing out here also cancels your sign-in on every other device.</p>
          <button className="btn danger-o" onClick={logout}>Sign out everywhere</button>
        </div>
        <div className="card">
          <h2>AI usage this month</h2>
          {loading ? <Skeleton rows={2} /> : error ? <ErrorBox error={error} retry={reload} /> : <>
            <div className="meta"><div><span className="mu">Requests</span>{u.requests} of {u.limit}</div><div><span className="mu">Input tokens</span>{u.input_tokens.toLocaleString()}</div><div><span className="mu">Output tokens</span>{u.output_tokens.toLocaleString()}</div><div><span className="mu">Estimated cost</span>{u.estimated_cost == null ? "Unavailable" : `${u.estimated_cost} ${u.currency}`}</div></div>
            <div className="bar"><i style={{ width: `${Math.min(100, (u.requests / u.limit) * 100)}%` }} /></div>
            <p className="small mu">{u.cost_note}</p></>}
        </div>
      </div>
    </>
  );
}
