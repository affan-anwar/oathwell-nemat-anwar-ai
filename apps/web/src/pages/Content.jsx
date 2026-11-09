import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, download, qs } from "../api.js";
import { useApp } from "../state.jsx";
import { Badge, Empty, ErrorBox, Field, Modal, PageHeader, Skeleton, Spinner, fmt, useAsync } from "../ui.jsx";

const KINDS = ["blog", "social_post", "email", "ad_copy", "product_description", "landing_page", "video_script", "content_brief", "seo_metadata"];
const label = (k) => k.replaceAll("_", " ");

function Editor({ docId, ws, can, toast, onChanged, onOpen }) {
  const base = `/workspaces/${ws.id}`;
  const { data: doc, error, loading, reload } = useAsync(() => api(`${base}/content/${docId}`), [docId]);
  const { data: integ } = useAsync(() => api(`${base}/integrations`), [ws.id]);
  const [body, setBody] = useState(null); const [saving, setSaving] = useState(false);
  const [diff, setDiff] = useState(null); const [pick, setPick] = useState("");
  const [when, setWhen] = useState(""); const [issues, setIssues] = useState(null);
  const [tone, setTone] = useState("friendly"); const [aiBusy, setAiBusy] = useState(""); const [sugg, setSugg] = useState(null);
  useEffect(() => {
    if (body === null) return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [body]);
  if (loading) return <Skeleton rows={5} />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  const latest = doc.versions[doc.versions.length - 1];
  const text = body ?? latest.body;
  const dirty = text !== latest.body;
  const wp = (integ || []).filter((i) => i.provider === "wordpress" && i.status === "connected");
  const save = async () => {
    setSaving(true);
    try { await api(`${base}/content/${doc.id}/versions`, { method: "POST", body: { body: text, meta: latest.meta } }); toast("Saved as a new version"); setBody(null); reload(); onChanged(); }
    catch (x) { toast(x.message, "bd"); } finally { setSaving(false); }
  };
  const showDiff = async (n) => {
    try { setDiff((await api(`${base}/content/${doc.id}/diff${qs({ a: n, b: latest.number })}`)).diff || "No differences"); }
    catch (x) { toast(x.message, "bd"); }
  };
  const request = async () => {
    try { await api(`${base}/approvals`, { method: "POST", body: { version_id: latest.id, integration_id: pick || wp[0].id, action: "publish_blog", scheduled_at: when ? new Date(when).toISOString() : undefined } }); toast(when ? "Sent for approval with a schedule. Nothing is published yet." : "Sent for approval. Nothing is published yet."); reload(); onChanged(); }
    catch (x) { toast(x.message, "bd"); }
  };
  const runAi = async (action) => {
    setAiBusy(action); setSugg(null);
    try {
      const r = await api(`${base}/content/${doc.id}/ai`, { method: "POST", body: { action, tone: action === "rewrite_tone" ? tone : undefined } });
      if (r.kind === "suggestions") setSugg({ action, items: r.items });
      else if (r.kind === "version") { toast(`New version v${r.version.number} created. The old version is unchanged.`); setBody(null); reload(); onChanged(); }
      else { toast("New document created from this one"); onOpen(r.document.id); }
    } catch (x) { toast(x.status === 503 ? `${x.message} Add the key on the server first.` : x.message, "bd"); } finally { setAiBusy(""); }
  };
  const checkIt = async () => { try { setIssues(await api(`${base}/content/${doc.id}/check`)); } catch (x) { toast(x.message, "bd"); } };
  const exportAs = async (f) => { try { await download(`${base}/content/${doc.id}/export?format=${f}`, `${doc.title.replace(/[^a-z0-9]+/gi, "-").slice(0, 50) || "content"}-v${latest.number}.${f}`); } catch (x) { toast(x.message, "bd"); } };
  return (
    <div className="card">
      <div className="row between"><h2>{doc.title}</h2><div className="row"><Badge>{doc.status}</Badge><Badge kind="">{label(doc.kind)}</Badge></div></div>
      <p className="mu small">Version {latest.number} · {latest.source === "ai" ? "AI generated, review before use" : "written by a person"} · {fmt(latest.created_at)}</p>
      {latest.meta?.used_profile_fields && <p className="mu small">Brand fields used: {latest.meta.used_profile_fields.join(", ") || "none"}</p>}
      <textarea className="editor" aria-label="Content body" value={text} readOnly={!can("content.write")} onChange={(e) => setBody(e.target.value)} />
      <div className="row wrap">
        {can("content.write") && <button className="btn primary" disabled={!dirty || saving || !text.trim()} onClick={save}>{saving ? "Saving…" : "Save as new version"}</button>}
        {dirty && <button className="btn" onClick={() => setBody(null)}>Discard changes</button>}
        <button className="btn" disabled={dirty} onClick={checkIt}>Check quality</button>
        <button className="btn" disabled={dirty} onClick={() => exportAs("md")}>Export .md</button>
        <button className="btn" disabled={dirty} onClick={() => exportAs("html")}>Export .html</button>
        {can("approval.request") && doc.kind === "blog" && (wp.length ? <>
          {wp.length > 1 && <select aria-label="Destination" value={pick} onChange={(e) => setPick(e.target.value)}>{wp.map((i) => <option key={i.id} value={i.id}>{i.label}</option>)}</select>}
          <input type="datetime-local" aria-label="Publish at (optional)" value={when} onChange={(e) => setWhen(e.target.value)} style={{ width: "auto" }} />
          <button className="btn" disabled={dirty} title={dirty ? "Save your changes first" : ""} onClick={request}>{when ? "Request approval for this time" : "Request approval to publish"}</button></> :
          <span className="mu small">Connect and test a WordPress account to request publishing.</span>)}
      </div>
      {can("content.write") && <div className="aibox">
        <h3>AI Copilot</h3>
        <p className="small mu">Rewrites become a new version. Repurposing makes a new document. Suggestions are not saved. Check every AI result before approving.</p>
        <div className="row wrap">
          <select aria-label="Tone" value={tone} onChange={(e) => setTone(e.target.value)} disabled={!!aiBusy}>{["professional", "friendly", "persuasive", "concise"].map((t) => <option key={t}>{t}</option>)}</select>
          <button className="btn ai" disabled={dirty || !!aiBusy} onClick={() => runAi("rewrite_tone")}>{aiBusy === "rewrite_tone" ? "Working…" : "Rewrite tone"}</button>
          <button className="btn ai" disabled={dirty || !!aiBusy} onClick={() => runAi("improve")}>{aiBusy === "improve" ? "Working…" : "Improve"}</button>
          <button className="btn" disabled={dirty || !!aiBusy} onClick={() => runAi("headlines")}>Headlines</button>
          <button className="btn" disabled={dirty || !!aiBusy} onClick={() => runAi("cta")}>CTAs</button>
          <button className="btn" disabled={dirty || !!aiBusy} onClick={() => runAi("brand_check")}>Brand check</button>
        </div>
        <div className="row wrap" style={{ marginTop: 8 }}>
          <span className="mu small">Repurpose as:</span>
          <button className="btn sm" disabled={dirty || !!aiBusy} onClick={() => runAi("to_linkedin")}>LinkedIn post</button>
          <button className="btn sm" disabled={dirty || !!aiBusy} onClick={() => runAi("to_email")}>Email</button>
          <button className="btn sm" disabled={dirty || !!aiBusy} onClick={() => runAi("to_social")}>Social caption</button>
        </div>
        {sugg && <div style={{ marginTop: 10 }}><b className="small">{sugg.action.replace("_", " ")} (not saved)</b>
          {sugg.items.map((t, k) => <div className="sug" key={k}><span>{t}</span><button className="btn sm" onClick={() => navigator.clipboard?.writeText(t).then(() => toast("Copied"))}>Copy</button></div>)}</div>}
      </div>}
      {issues && <div className={`alert ${issues.ok ? "ok" : "bd"}`} role="status" style={{ display: "block" }}>
        <b>{issues.ok ? "No blocking problems" : "Fix these before approval"}</b> (version {issues.version})
        {issues.issues.length === 0 ? <div>Nothing found.</div> : issues.issues.map((i, k) => <div key={k}>{i.level === "error" ? "Error" : "Warning"}: {i.message}</div>)}</div>}
      <h3>Version history</h3>
      {doc.versions.slice().reverse().map((v) => (
        <div className="li" key={v.id}><span>v{v.number} <small className="mu">{v.source} · {fmt(v.created_at)} · {v.content_hash.slice(0, 8)}</small></span>
          {v.number !== latest.number && <button className="btn sm" onClick={() => showDiff(v.number)}>Compare with latest</button>}</div>))}
      {diff && <pre className="diff">{diff}</pre>}
    </div>
  );
}

export default function Content() {
  const { ws, can, toast } = useApp();
  const base = `/workspaces/${ws.id}/content`;
  const [params] = useSearchParams();
  const [sel, setSel] = useState(params.get("doc")); const [kind, setKind] = useState("");
  useEffect(() => { if (params.get("focus") === "generate") document.getElementById("gen-brief")?.focus(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [gen, setGen] = useState({ kind: "blog", brief: "", language: "" }); const [busy, setBusy] = useState(false); const [setup, setSetup] = useState("");
  const [manual, setManual] = useState(null);
  const { data, error, loading, reload } = useAsync(() => api(`${base}${qs({ kind, limit: 100 })}`), [ws.id, kind]);
  const generate = async (e) => {
    e.preventDefault(); setBusy(true); setSetup("");
    try { const d = await api(`${base}/generate`, { method: "POST", body: { ...gen, language: gen.language || null } }); toast("Draft generated. Review it before use."); setSel(d.id); reload(); }
    catch (x) { x.status === 503 ? setSetup(x.message) : toast(x.message, "bd"); } finally { setBusy(false); }
  };
  const create = async (e) => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target));
    try { const d = await api(base, { method: "POST", body: f }); toast("Document created"); setManual(null); setSel(d.id); reload(); } catch (x) { toast(x.message, "bd"); }
  };
  return (
    <>
      <PageHeader title="Content Studio" sub="Write, generate and version your content">
        {can("content.write") && <button className="btn" onClick={() => setManual({})}>New document</button>}
      </PageHeader>
      <div className="split">
        <div>
          {can("content.write") && <form className="card gen" onSubmit={generate}>
            <h2>Generate with AI</h2>
            <Field label="Type"><select value={gen.kind} onChange={(e) => setGen({ ...gen, kind: e.target.value })}>{KINDS.map((k) => <option key={k} value={k}>{label(k)}</option>)}</select></Field>
            <Field label="What should it say?"><textarea id="gen-brief" required minLength={3} value={gen.brief} onChange={(e) => setGen({ ...gen, brief: e.target.value })} placeholder="Launch post for our new shoe range" /></Field>
            <Field label="Language (optional)"><input value={gen.language} onChange={(e) => setGen({ ...gen, language: e.target.value })} placeholder="English" /></Field>
            <button className="btn primary block" disabled={busy}>{busy ? "Generating…" : "Generate draft"}</button>
            {setup && <div className="alert wn" role="alert">{setup} Add the key on the server, then try again.</div>}
          </form>}
          <div className="toolbar"><select aria-label="Filter by type" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">All types</option>{KINDS.map((k) => <option key={k} value={k}>{label(k)}</option>)}</select></div>
          {loading ? <Spinner /> : error ? <ErrorBox error={error} retry={reload} /> : data.length === 0 ? <div className="card"><Empty title="No content yet">Generate a draft or create a document.</Empty></div> :
            data.map((d) => <button key={d.id} className={`item ${sel === d.id ? "sel" : ""}`} onClick={() => setSel(d.id)}><b>{d.title}</b><span className="row"><Badge>{d.status}</Badge><small className="mu">{label(d.kind)}</small></span></button>)}
        </div>
        <div>{sel ? <Editor key={sel} docId={sel} ws={ws} can={can} toast={toast} onChanged={reload} onOpen={(id) => { setSel(id); reload(); }} /> : <div className="card"><Empty title="Select a document">Choose one from the list to edit it and see its versions.</Empty></div>}</div>
      </div>
      {manual && <Modal title="New document" onClose={() => setManual(null)}>
        <form className="form" onSubmit={create}>
          <Field label="Type"><select name="kind">{KINDS.map((k) => <option key={k} value={k}>{label(k)}</option>)}</select></Field>
          <Field label="Title"><input name="title" required maxLength={200} /></Field>
          <Field label="Body"><textarea name="body" required className="editor" /></Field>
          <div className="mf"><button type="button" className="btn" onClick={() => setManual(null)}>Cancel</button><button className="btn primary">Create</button></div>
        </form></Modal>}
    </>
  );
}
