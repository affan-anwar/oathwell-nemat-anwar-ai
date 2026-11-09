import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useApp } from "../state.jsx";
import { ErrorBox, Field, PageHeader, Skeleton, useAsync } from "../ui.jsx";

const TEXT = [["business_name", "Brand name", 1], ["industry", "Industry", 1], ["website", "Website", 1], ["market", "Market", 1], ["description", "Business description"], ["products", "Products and services"], ["target_audience", "Target audience"], ["brand_voice", "Brand voice and tone"], ["guidelines", "Style guidelines"], ["approved_claims", "Approved claims (one per line)"], ["prohibited_claims", "Forbidden phrases (one per line). Generated text containing these is rejected"], ["objectives", "Marketing objectives"]];
const LISTS = [["languages", "Languages"], ["competitors", "Competitors"], ["channels", "Preferred channels"], ["occasions", "Business occasions"]];

export default function Brand() {
  const { ws, can, toast } = useApp();
  const url = `/workspaces/${ws.id}/profile`;
  const { data, error, loading, reload } = useAsync(() => api(url), [ws.id]);
  const [f, setF] = useState(null); const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setF({ ...data, ...Object.fromEntries(LISTS.map(([k]) => [k, (data[k] || []).join(", ")])) }); }, [data]);
  if (loading || !f) return error ? <ErrorBox error={error} retry={reload} /> : <Skeleton rows={6} />;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async (e) => {
    e.preventDefault(); setBusy(true);
    const body = { ...f, budget_limit: f.budget_limit === "" || f.budget_limit == null ? null : Number(f.budget_limit), currency: f.currency || null };
    LISTS.forEach(([k]) => { body[k] = String(f[k]).split(",").map((s) => s.trim()).filter(Boolean); });
    TEXT.forEach(([k]) => { if (body[k] === "") body[k] = null; });
    try { await api(url, { method: "PUT", body }); toast("Brand settings saved"); reload(); } catch (x) { toast(x.message, "bd"); } finally { setBusy(false); }
  };
  const ro = !can("brand.write");
  return (
    <>
      <PageHeader title="Brand Voice" sub="Saved settings are sent to the AI with every generation request" />
      <form className="card form wide" onSubmit={save}>
        <fieldset disabled={ro}>
          <div className="grid2 tight">{TEXT.filter((t) => t[2]).map(([k, l]) => <Field key={k} label={l}><input value={f[k] || ""} onChange={set(k)} /></Field>)}</div>
          {TEXT.filter((t) => !t[2]).map(([k, l]) => <Field key={k} label={l}><textarea value={f[k] || ""} onChange={set(k)} /></Field>)}
          <div className="grid2 tight">{LISTS.map(([k, l]) => <Field key={k} label={l} hint="Comma separated"><input value={f[k]} onChange={set(k)} /></Field>)}</div>
          <div className="grid3 tight">
            <Field label="Currency"><input maxLength={3} value={f.currency || ""} onChange={set("currency")} placeholder="INR" /></Field>
            <Field label="Budget limit"><input type="number" min="0" value={f.budget_limit ?? ""} onChange={set("budget_limit")} /></Field>
            <Field label="Time zone"><input value={f.timezone || ""} onChange={set("timezone")} placeholder="Asia/Kolkata" /></Field>
          </div>
        </fieldset>
        {ro ? <p className="mu">Viewers cannot edit brand settings.</p> : <div><button className="btn primary" disabled={busy}>{busy ? "Saving…" : "Save brand settings"}</button></div>}
      </form>
    </>
  );
}
