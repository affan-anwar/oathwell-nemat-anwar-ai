import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { contrast, isHex, problems as findProblems } from "../theme.js";
import { Badge, Confirm, Empty, ErrorBox, Field, PageHeader, Skeleton, fmt, useAsync } from "../ui.jsx";

const KEYS = ["bg", "surface", "surface2", "text", "muted", "border", "primary", "primaryText", "success", "warning", "danger", "accent", "sidebar", "chart1", "chart2"];
const PRESETS = [
  ["Premium Black & Emerald (default)", null],
  ["Carbon & Amber", { dark: { primary: "#f59e0b", primaryText: "#140c00", accent: "#fcd34d", chart1: "#f59e0b" }, light: { primary: "#92400e", primaryText: "#ffffff", accent: "#78350f", chart1: "#92400e" } }],
  ["Obsidian & Lime", { dark: { primary: "#a3e635", primaryText: "#0a1200", accent: "#d9f99d", chart1: "#a3e635" }, light: { primary: "#3f6212", primaryText: "#ffffff", accent: "#365314", chart1: "#3f6212" } }],
  ["Graphite & Rose", { dark: { primary: "#fb7185", primaryText: "#1a0509", accent: "#fda4af", chart1: "#fb7185" }, light: { primary: "#be123c", primaryText: "#ffffff", accent: "#9f1239", chart1: "#be123c" } }],
];
export const PRESETS_FOR_TEST = PRESETS;
const rgb = (h) => [1, 3, 5].map((i) => parseInt((isHex(h) ? h : "#000000").slice(i, i + 2), 16));
const hex = (r, g, b) => "#" + [r, g, b].map((n) => Math.max(0, Math.min(255, Math.round(+n || 0))).toString(16).padStart(2, "0")).join("");

function ThemeStudio() {
  const { ws, themeCfg, previewTheme, clearPreview, reloadTheme, toast } = useApp();
  const base = useMemo(() => JSON.stringify({ tokens: themeCfg.tokens, scope: themeCfg.source === "global" ? "global" : "workspace", dm: themeCfg.default_mode, au: themeCfg.allow_user_mode }), [themeCfg]);
  const [draft, setDraft] = useState(() => JSON.parse(JSON.stringify(themeCfg.tokens)));
  const [mode, setMode] = useState(document.documentElement.getAttribute("data-theme") || "dark");
  const [scope, setScope] = useState(themeCfg.source === "global" ? "global" : "workspace");
  const [dm, setDm] = useState(themeCfg.default_mode); const [au, setAu] = useState(themeCfg.allow_user_mode);
  const [serverProblems, setServerProblems] = useState([]); const [reset, setReset] = useState(false); const [busy, setBusy] = useState(false);
  const orig = useRef(document.documentElement.getAttribute("data-theme"));
  const dirty = JSON.stringify({ tokens: draft, scope, dm, au }) !== base;
  const probs = { dark: findProblems(draft.dark, themeCfg.labels), light: findProblems(draft.light, themeCfg.labels) };
  const bad = probs.dark.length + probs.light.length;

  useEffect(() => { previewTheme(draft); }, [draft, previewTheme]);          // live: every change is on screen immediately
  useEffect(() => { document.documentElement.setAttribute("data-theme", mode); }, [mode]); // show the mode being edited (not saved as a preference)
  useEffect(() => () => { clearPreview(); document.documentElement.setAttribute("data-theme", orig.current || "dark"); }, [clearPreview]);
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const set = (k, v) => setDraft((d) => ({ ...d, [mode]: { ...d[mode], [k]: v } }));
  const preset = (t) => setDraft(() => { const n = JSON.parse(JSON.stringify(themeCfg.defaults)); if (t) for (const m of ["dark", "light"]) Object.assign(n[m], t[m]); return n; });
  const save = async () => {
    setBusy(true); setServerProblems([]);
    try { await api(`/workspaces/${ws.id}/theme`, { method: "PUT", body: { scope, tokens: draft, default_mode: dm, allow_user_mode: au } }); await reloadTheme(); toast("Theme saved for " + (scope === "global" ? "all your workspaces" : "this workspace")); }
    catch (x) { setServerProblems([x.message]); toast("The theme was not saved", "bd"); } finally { setBusy(false); }
  };
  const cancel = () => { const b = JSON.parse(base); setDraft(JSON.parse(JSON.stringify(b.tokens))); setScope(b.scope); setDm(b.dm); setAu(b.au); setServerProblems([]); toast("Changes discarded"); };
  const doReset = async () => {
    setBusy(true);
    try { const r = await api(`/workspaces/${ws.id}/theme?scope=${scope}`, { method: "DELETE" }); setDraft(JSON.parse(JSON.stringify(r.tokens))); await reloadTheme(); toast("Reset to " + (r.source === "default" ? "the default theme" : `the ${r.source} theme`)); }
    catch (x) { toast(x.message, "bd"); } finally { setBusy(false); setReset(false); }
  };
  return (
    <div className="grid2" style={{ gridTemplateColumns: "minmax(0,1.5fr) minmax(0,1fr)" }}>
      <section className="card"><h2>Colours</h2>
        <p className="sub">Changes show on every page straight away. Nothing is saved until you press Save.</p>
        <div className="row wrap" style={{ marginBottom: 10 }}>
          <div className="seg2" role="group" aria-label="Mode being edited" style={{ width: 240 }}>{["dark", "light"].map((m) => <button key={m} className={mode === m ? "on" : ""} aria-pressed={mode === m} onClick={() => setMode(m)}>Edit {m}</button>)}</div>
          <select aria-label="Preset palette" value="" onChange={(e) => e.target.value !== "" && preset(PRESETS[+e.target.value][1])}><option value="">Preset palettes</option>{PRESETS.map(([n], i) => <option key={n} value={i}>{n}</option>)}</select></div>
        {KEYS.map((k) => { const v = draft[mode][k], [r, g, b] = rgb(v); return (
          <div className="crow" key={k}><span>{themeCfg.labels[k]}</span>
            <input type="color" aria-label={`${themeCfg.labels[k]} colour`} value={isHex(v) ? v : "#000000"} onChange={(e) => set(k, e.target.value)} />
            <input aria-label={`${themeCfg.labels[k]} hex`} value={v} onChange={(e) => set(k, e.target.value)} spellCheck={false} />
            {[r, g, b].map((n, i) => <input key={i} className="rgb" type="number" min="0" max="255" aria-label={`${themeCfg.labels[k]} ${"RGB"[i]}`} value={n} onChange={(e) => { const c = [r, g, b]; c[i] = e.target.value; set(k, hex(...c)); }} />)}</div>); })}
      </section>
      <div className="col" style={{ display: "grid", gap: 16, alignContent: "start" }}>
        <section className="card"><h2>Live preview</h2>
          <div className="prevbox"><b>Sample card</b><span className="mu small">Secondary text on the card surface</span>
            <div className="row wrap"><button className="btn primary sm" type="button">Primary action</button><span className="badge ok">Success</span><span className="badge wn">Warning</span><span className="badge bd">Error</span></div></div>
          {bad === 0 ? <p className="small" style={{ color: "var(--ok)" }}>Readable: every text colour passes the 4.5:1 contrast check in both modes.</p> :
            <div className="problems" role="alert"><b>Cannot be saved yet</b>{[...probs.dark.map((p) => `Dark: ${p}`), ...probs.light.map((p) => `Light: ${p}`)].slice(0, 6).map((p) => <div key={p}>{p}</div>)}</div>}
          {serverProblems.map((p) => <div className="problems" role="alert" key={p}>{p}</div>)}
        </section>
        <section className="card"><h2>Where it applies</h2>
          <Field label="Apply to"><select value={scope} onChange={(e) => setScope(e.target.value)}><option value="workspace">This workspace only</option><option value="global">All workspaces I own</option></select></Field>
          <Field label="Default display mode"><select value={dm} onChange={(e) => setDm(e.target.value)}><option value="dark">Dark</option><option value="light">Light</option></select></Field>
          <label className="row" style={{ marginBottom: 12 }}><input type="checkbox" style={{ width: "auto" }} checked={au} onChange={(e) => setAu(e.target.checked)} />Let each person choose their own dark or light mode</label>
          <div className="row wrap"><button className="btn" onClick={() => { previewTheme(draft); toast("Applied on screen. Save to keep it."); }}>Apply</button>
            <button className="btn primary" disabled={busy || bad > 0 || !dirty} onClick={save}>{busy ? "Saving…" : "Save"}</button>
            <button className="btn" disabled={!dirty} onClick={cancel}>Cancel</button><button className="btn danger-o" onClick={() => setReset(true)}>Reset to default</button></div>
          {dirty && <p className="small mu" style={{ marginBottom: 0 }}>You have unsaved changes.</p>}</section>
      </div>
      {reset && <Confirm title="Reset the theme?" danger confirmLabel="Reset" busy={busy} onClose={() => setReset(false)} onConfirm={doReset}><p>The {scope === "global" ? "global" : "workspace"} theme is removed and the {scope === "global" ? "default" : "global or default"} theme applies again.</p></Confirm>}
    </div>
  );
}

function AiProviders() {
  const { ws, toast } = useApp();
  const { data, error, loading, reload } = useAsync(() => api(`/workspaces/${ws.id}/ai/providers`), [ws.id]);
  const [busy, setBusy] = useState(""); const [f, setF] = useState(null); const [err, setErr] = useState("");
  useEffect(() => { if (data) setF(data.config ? { ...data.config, fast_model: data.config.fast_model || "", fallback_provider: data.config.fallback_provider || "openai", fallback_model: data.config.fallback_model || "" } : { provider: "openai", model: "", fast_model: "", fallback_enabled: false, fallback_provider: "anthropic", fallback_model: "" }); }, [data]);
  if (loading && !data) return <Skeleton rows={4} />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  const test = async (p) => { setBusy(p); try { const r = await api(`/workspaces/${ws.id}/ai/providers/${p}/test`, { method: "POST" }); toast(r.ok ? `Connected. ${r.model_count} models available.` : r.error, r.ok ? "ok" : "bd"); } catch (x) { toast(x.message, "bd"); } finally { setBusy(""); reload(); } };
  const save = async (e) => {
    e.preventDefault(); setErr("");
    try { await api(`/workspaces/${ws.id}/ai/config`, { method: "PUT", body: { provider: f.provider, model: f.model, fast_model: f.fast_model || null, fallback_enabled: f.fallback_enabled, fallback_provider: f.fallback_enabled ? f.fallback_provider : null, fallback_model: f.fallback_enabled ? f.fallback_model : null } }); toast("AI settings saved"); reload(); }
    catch (x) { setErr(x.message); }
  };
  const models = (p) => data.providers.find((x) => x.provider === p)?.models || [];
  return (
    <div className="grid2">
      <section className="card"><h2>Providers</h2><p className="sub">A provider shows as connected only after a real test succeeded. Keys live in the server environment and are never shown here.</p>
        {data.providers.map((p) => (
          <div className="tcard" key={p.provider}>
            <div className="row between"><b>{p.label}</b><Badge kind={p.connected ? "ok" : p.key_configured ? "wn" : ""}>{p.connected ? "Connected" : p.key_configured ? "Not tested" : "No key"}</Badge></div>
            <div className="mu small">Server variable: <code>{p.env}</code> · {p.key_configured ? "key set" : "key missing"}</div>
            <div className="mu small">Last test: {p.last_test_at ? fmt(p.last_test_at) : "never"}{p.last_ok_at && ` · last success ${fmt(p.last_ok_at)}`}</div>
            {p.last_error && <div className="small" style={{ color: "var(--bd)" }}>{p.last_error}</div>}
            <button className="btn sm" style={{ marginTop: 6 }} disabled={busy === p.provider} onClick={() => test(p.provider)}>{busy === p.provider ? "Testing…" : "Test connection"}</button></div>))}
      </section>
      <form className="card form" onSubmit={save}><h2>Models</h2><p className="sub">{data.note}</p>
        {f && <>
          <Field label="Primary provider"><select value={f.provider} onChange={(e) => setF({ ...f, provider: e.target.value })}>{data.providers.map((p) => <option key={p.provider} value={p.provider}>{p.label}</option>)}</select></Field>
          <Field label="Primary model" hint="Run the test, then choose a model your account can use"><input list="m1" required value={f.model} onChange={(e) => setF({ ...f, model: e.target.value })} /></Field>
          <Field label="Fast model (optional)" hint="Used for quick tasks such as headlines and short captions"><input list="m1" value={f.fast_model} onChange={(e) => setF({ ...f, fast_model: e.target.value })} /></Field>
          <datalist id="m1">{models(f.provider).map((m) => <option key={m} value={m} />)}</datalist>
          <label className="row" style={{ marginBottom: 12 }}><input type="checkbox" style={{ width: "auto" }} checked={f.fallback_enabled} onChange={(e) => setF({ ...f, fallback_enabled: e.target.checked })} />Use a fallback if the primary fails (off unless you turn it on)</label>
          {f.fallback_enabled && <div className="grid2 tight"><Field label="Fallback provider"><select value={f.fallback_provider} onChange={(e) => setF({ ...f, fallback_provider: e.target.value })}>{data.providers.map((p) => <option key={p.provider} value={p.provider}>{p.label}</option>)}</select></Field>
            <Field label="Fallback model"><input list="m2" value={f.fallback_model} onChange={(e) => setF({ ...f, fallback_model: e.target.value })} /></Field><datalist id="m2">{models(f.fallback_provider).map((m) => <option key={m} value={m} />)}</datalist></div>}
          {err && <div className="alert bd" role="alert">{err}</div>}
          <div className="row"><button className="btn primary">Save AI settings</button>
            <button type="button" className="btn" onClick={async () => { await api(`/workspaces/${ws.id}/ai/config`, { method: "DELETE" }); toast("Back to the server defaults"); reload(); }}>Use server defaults</button></div></>}
      </form>
    </div>
  );
}

function Access() {
  const { ws, perms, toast, loadWorkspaces } = useApp();
  const [revoked, setRevoked] = useState(perms.admin_revoked || []); const [off, setOff] = useState(false); const [ack, setAck] = useState(false); const [busy, setBusy] = useState(false);
  const label = (p) => ({ "approval.decide": "Approve or reject content", "integration.manage": "Connect and disconnect accounts", "member.manage": "Manage lower roles", "automation.pause": "Pause automation", "audit.read": "Read the audit log", "events.manage": "Manage events" }[p] || p);
  const flip = async (p) => {
    const next = revoked.includes(p) ? revoked.filter((x) => x !== p) : [...revoked, p];
    try { await api(`/workspaces/${ws.id}/admin-permissions`, { method: "PUT", body: { revoked: next } }); setRevoked(next); toast("Admin powers updated"); } catch (x) { toast(x.message, "bd"); }
  };
  const shut = async () => {
    setBusy(true);
    try { const r = await api(`/workspaces/${ws.id}/emergency-shutdown`, { method: "POST" }); await loadWorkspaces(); toast(`Shut down. ${r.approvals_revoked} approvals withdrawn.`, "wn"); } catch (x) { toast(x.message, "bd"); } finally { setBusy(false); setOff(false); setAck(false); }
  };
  return (
    <div className="grid2">
      <section className="card"><h2>What Admins can do</h2><p className="sub">Switch off any power you do not want to delegate. You, the Owner, always keep everything.</p>
        {perms.delegable.map((p) => <div className="sw2" key={p}><span>{label(p)}</span><button className="toggle" role="switch" aria-checked={!revoked.includes(p)} aria-label={label(p)} onClick={() => flip(p)} /></div>)}
        <p className="small mu">Manage people on the <Link to="/team">Team</Link> page. Every change is recorded in the <Link to="/audit">audit log</Link>.</p></section>
      <section className="card"><h2>Emergency shutdown</h2><p className="sub">Pauses this workspace and withdraws every approval that has not run yet. Nothing is deleted. Resume from the top bar when you are ready.</p>
        <button className="btn danger" onClick={() => setOff(true)}>Emergency shutdown</button></section>
      {off && <Confirm title="Shut down this workspace?" danger confirmLabel="Shut down" busy={busy} disabled={!ack} onClose={() => { setOff(false); setAck(false); }} onConfirm={shut}>
        <p>All automation stops and approved posts that have not been published are withdrawn.</p>
        <label className="row"><input type="checkbox" style={{ width: "auto" }} checked={ack} onChange={(e) => setAck(e.target.checked)} />I understand and want to continue</label></Confirm>}
    </div>
  );
}

export default function Owner() {
  const { can, themeCfg } = useApp();
  const [tab, setTab] = useState("theme");
  if (!can("theme.write")) return <><PageHeader title="Owner Console" /><div className="card"><Empty title="Owner only">Only the workspace Owner can open the Owner Console.</Empty></div></>;
  return (
    <>
      <PageHeader title="Owner Console" sub="Themes, AI providers and access controls" />
      <div className="otabs" role="tablist">{[["theme", "Theme Studio"], ["ai", "AI Providers"], ["access", "Access & Safety"]].map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "theme" ? (themeCfg ? <ThemeStudio /> : <Skeleton rows={4} />) : tab === "ai" ? <AiProviders /> : <Access />}
    </>
  );
}
