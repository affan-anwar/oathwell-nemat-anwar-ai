import { useCallback, useEffect, useRef, useState } from "react";
import { useApp } from "./state.jsx";

export function useAsync(fn, deps) {
  const [s, set] = useState({ data: null, error: null, loading: true });
  const run = useCallback(() => {
    set((p) => ({ ...p, loading: true, error: null }));
    return fn().then((data) => set({ data, error: null, loading: false }), (error) => set({ data: null, error, loading: false }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { ...s, reload: run };
}

const GOOD = ["ACTIVE", "APPROVED", "PUBLISHED", "connected", "published", "approved", "ok"];
const WARN = ["PENDING", "review", "unverified", "PAUSED", "UNCLEAR", "CHANGES_REQUESTED", "EXECUTING", "unclear", "pending", "blocked", "processing"];
const BAD = ["REJECTED", "FAILED", "failed", "CANCELLED", "REVOKED", "INVALIDATED", "disconnected", "expired", "EXPIRED"];
export function Badge({ children, kind }) {
  const k = kind || (GOOD.includes(children) ? "ok" : WARN.includes(children) ? "wn" : BAD.includes(children) ? "bd" : "");
  return <span className={`badge ${k}`}>{String(children).replaceAll("_", " ")}</span>;
}

export const Spinner = ({ label = "Loading" }) => <div className="loading" role="status"><span className="spin" />{label}…</div>;
export const Skeleton = ({ rows = 3 }) => <div aria-hidden="true">{Array.from({ length: rows }, (_, i) => <div key={i} className="skel" />)}</div>;

export function Empty({ title, children, action }) {
  return <div className="empty"><h2>{title}</h2><p>{children}</p>{action}</div>;
}

export function ErrorBox({ error, retry }) {
  return (
    <div className="alert bd" role="alert">
      <span>{error?.message || "Something went wrong"}</span>
      {retry && <button className="btn sm" onClick={retry}>Try again</button>}
    </div>
  );
}

export function PageHeader({ title, sub, children }) {
  return (
    <div className="ph">
      <div><h1>{title}</h1>{sub && <p className="mu">{sub}</p>}</div>
      <div className="row">{children}</div>
    </div>
  );
}

export function Modal({ title, onClose, children, footer }) {
  const ref = useRef(null);
  useEffect(() => {
    const prev = document.activeElement;
    ref.current?.querySelector("input,textarea,select,button")?.focus();
    const esc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("keydown", esc); prev?.focus?.(); };
  }, [onClose]);
  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <div className="mh"><h2>{title}</h2><button className="btn sm ghost" aria-label="Close" onClick={onClose}>✕</button></div>
        <div className="mb">{children}</div>
        {footer && <div className="mf">{footer}</div>}
      </div>
    </div>
  );
}

export function Confirm({ title, children, confirmLabel = "Confirm", danger, busy, disabled, onConfirm, onClose }) {
  return (
    <Modal title={title} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className={`btn ${danger ? "danger" : "primary"}`} disabled={busy || disabled} onClick={onConfirm}>{busy ? "Working…" : confirmLabel}</button>
    </>}>{children}</Modal>
  );
}

export const Field = ({ label, hint, children }) => (
  <label className="field"><span>{label}</span>{children}{hint && <small className="mu">{hint}</small>}</label>
);

export function Toasts() {
  const { toasts } = useApp();
  return <div className="toasts" aria-live="polite">{toasts.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.msg}</div>)}</div>;
}

export const fmt = (d) => (d ? new Date(d + (String(d).endsWith("Z") ? "" : "Z")).toLocaleString() : "—");
