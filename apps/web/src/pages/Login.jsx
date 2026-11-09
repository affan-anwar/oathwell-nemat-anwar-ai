import { useState } from "react";
import { useApp } from "../state.jsx";
import { Field } from "../ui.jsx";

export default function Login() {
  const { login, register } = useApp();
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ email: "", password: "", name: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      if (mode === "login") await login(f.email, f.password);
      else await register(f.email, f.password, f.name);
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <main className="auth">
      <form className="card auth-card" onSubmit={submit}>
        <div className="brand"><span className="mark">N</span>NematAnwar AI</div>
        <h1>{mode === "login" ? "Sign in" : "Create your account"}</h1>
        <p className="mu">Your marketing workspace. Nothing is published without your approval.</p>
        {mode === "register" && <Field label="Full name"><input required value={f.name} onChange={set("name")} autoComplete="name" /></Field>}
        <Field label="Email"><input type="email" required value={f.email} onChange={set("email")} autoComplete="email" /></Field>
        <Field label="Password" hint={mode === "register" ? "At least 10 characters" : null}>
          <input type="password" required minLength={mode === "register" ? 10 : 1} value={f.password} onChange={set("password")} autoComplete={mode === "login" ? "current-password" : "new-password"} />
        </Field>
        {err && <div className="alert bd" role="alert">{err}</div>}
        <button className="btn primary block" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
          {mode === "login" ? "New here? Create an account" : "Have an account? Sign in"}
        </button>
      </form>
    </main>
  );
}
