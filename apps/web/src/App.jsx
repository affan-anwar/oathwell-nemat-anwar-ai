import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api.js";
import { CameraIndicator, GestureProvider } from "./GestureControl.jsx";
import Icon, { RobotArt } from "./Icons.jsx";
import Notifications from "./Notifications.jsx";
import TopSearch from "./TopSearch.jsx";
import { useApp } from "./state.jsx";
import { Field, Spinner, Toasts } from "./ui.jsx";
import AgentControl from "./pages/AgentControl.jsx";
import Analytics from "./pages/Analytics.jsx";
import Approvals from "./pages/Approvals.jsx";
import Audit from "./pages/Audit.jsx";
import Brand from "./pages/Brand.jsx";
import Calendar from "./pages/Calendar.jsx";
import Campaigns from "./pages/Campaigns.jsx";
import Content from "./pages/Content.jsx";
import Copilot from "./pages/Copilot.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Integrations from "./pages/Integrations.jsx";
import Login from "./pages/Login.jsx";
import Owner from "./pages/Owner.jsx";
import Publishing from "./pages/Publishing.jsx";
import Settings from "./pages/Settings.jsx";
import Team from "./pages/Team.jsx";

export const NAV = [["/", "Dashboard", "dash"], ["/campaigns", "Campaigns", "megaphone"], ["/content", "Content Studio", "pen"], ["/agent", "Agent Control Center", "bot"],
  ["/calendar", "Calendar", "cal"], ["/approvals", "Approvals", "check"], ["/publishing", "Publishing", "send"], ["/analytics", "Analytics", "chart"],
  ["/integrations", "Integrations", "plug"], ["/team", "Team", "users"], ["/audit", "Audit Log", "shield"], ["/brand", "Brand Voice", "mic"], ["/settings", "Settings", "gear"]];

function CreateWorkspace() {
  const { loadWorkspaces, toast } = useApp();
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    try { await api("/workspaces", { method: "POST", body: { name: new FormData(e.target).get("name") } }); await loadWorkspaces(); toast("Workspace created"); } catch (x) { setErr(x.message); }
  };
  return <main className="auth"><form className="card auth-card" onSubmit={submit}>
    <h1>Create your workspace</h1><p className="mu">A workspace holds one business: its brand, campaigns, content and connected accounts.</p>
    <Field label="Business name"><input name="name" required maxLength={200} /></Field>
    {err && <div className="alert bd" role="alert">{err}</div>}<button className="btn primary block">Create workspace</button></form></main>;
}

function Shell() {
  const { user, ws, workspaces, setWsId, can, perms, logout, theme, toggleTheme, themeLocked, toast, loadWorkspaces } = useApp();
  const nav = useNavigate();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("na_side") === "1");
  const [menu, setMenu] = useState(false);
  const pages = [...NAV.map((n) => n[0]), ...(can("theme.write") ? ["/owner"] : [])];
  const step = (dir) => { const i = Math.max(0, pages.indexOf(loc.pathname)); nav(pages[(i + (dir === "next" ? 1 : pages.length - 1)) % pages.length]); };
  const stepRef = useRef(step); stepRef.current = step;

  useEffect(() => {  // keyboard fallback for gestures, plus Ctrl+K for search
    const key = (e) => {
      if (e.altKey && e.key === "ArrowRight") { e.preventDefault(); stepRef.current("next"); }
      if (e.altKey && e.key === "ArrowLeft") { e.preventDefault(); stepRef.current("prev"); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); document.getElementById("global-search")?.focus(); }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  const toggleSide = () => {
    if (window.innerWidth <= 900) return setOpen((o) => !o);
    setCollapsed((c) => { localStorage.setItem("na_side", c ? "0" : "1"); return !c; });
  };
  const pause = async () => {
    try { await api(`/workspaces/${ws.id}/pause`, { method: "POST", body: { paused: !ws.paused } }); await loadWorkspaces(); toast(ws.paused ? "Resumed" : "Paused: nothing will be published", ws.paused ? "ok" : "wn"); }
    catch (x) { toast(x.message, "bd"); }
  };
  const initials = user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const label = perms?.label || "Member";
  const modeName = theme === "dark" ? "Dark" : "Light";
  return (
    <GestureProvider onSwipe={(d) => stepRef.current(d === "left" ? "next" : "prev")}>
      <div className={`app ${open ? "open" : ""} ${collapsed ? "collapsed" : ""}`}>
        <aside className="side" aria-label="Main">
          <div className="brand"><span className="mark">N</span><span>Nemat<b>Anwar</b> AI<small className="mu" style={{ display: "block", fontWeight: 400, fontSize: 11 }}>Autonomous Marketing</small></span></div>
          <nav>{[...NAV, ...(can("theme.write") ? [["/owner", "Owner Console", "crown"]] : [])].map(([to, l, ic]) => <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}><Icon n={ic} />{l}</NavLink>)}</nav>
          <div className="sidecard"><div className="who"><span className="av">{initials}</span><span><b>{user.full_name}</b><small>{label}</small>{perms?.role === "owner" && <span className="pillok">Full access</span>}</span></div></div>
          <div className="sidecard"><h4>Quick actions</h4><div className="qa2">
            {can("campaign.write") && <Link to="/campaigns?new=1"><Icon n="plus" />Create campaign</Link>}
            {can("content.write") && <Link to="/content?focus=generate"><Icon n="spark" />Generate content</Link>}
            <Link to="/calendar"><Icon n="cal" />View calendar</Link><Link to="/analytics"><Icon n="chart" />Open analytics</Link></div></div>
          <div className="promo"><b>Smarter marketing.<br />Bigger growth.</b><span className="mu">Powered by AI, approved by you.</span></div>
        </aside>
        {open && <div className="shade" onClick={() => setOpen(false)} />}
        <div className="main">
          <header className="top">
            <button className="btn sm" aria-label="Toggle menu" aria-expanded={!collapsed} onClick={toggleSide}><Icon n="menu" /></button>
            <select aria-label="Workspace" value={ws.id} onChange={(e) => setWsId(e.target.value)}>{workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
            <TopSearch />
            <span className="grow" />
            <CameraIndicator />
            {ws.paused && <span className="badge wn">Paused</span>}
            {can("automation.pause") && <button className={`btn sm ${ws.paused ? "primary" : "danger-o"}`} onClick={pause}>{ws.paused ? "Resume" : <><span className="full">Emergency </span>pause</>}</button>}
            <button className="pillbtn" aria-label={`${modeName} mode, switch to ${theme === "dark" ? "light" : "dark"} theme`} aria-disabled={themeLocked} title={themeLocked ? "The Owner has set the display mode" : undefined} onClick={toggleTheme}>
              <Icon n={theme === "dark" ? "moon" : "sun"} /><span className="t">{modeName} mode</span></button>
            <Notifications />
            <div className="acct">
              <button className="btn prof" aria-expanded={menu} onClick={() => setMenu(!menu)}>
                <span className="av" aria-hidden="true">{initials}</span><span className="who"><span><b>{user.full_name.split(" ")[0]}</b><small>{label}</small></span></span><span className="sr-only"> Account menu</span></button>
              {menu && <div className="panel" role="region" aria-label="Account">
                <span className="mu small user" style={{ display: "block", maxWidth: "none" }}>{user.email}</span>
                <NavLink className="btn sm" to="/settings" onClick={() => setMenu(false)}>Settings</NavLink>
                <button className="btn sm danger-o" onClick={logout}>Sign out</button>
              </div>}
            </div>
          </header>
          <main className="page">
            <Routes>
              <Route path="/" element={<Dashboard />} /><Route path="/campaigns" element={<Campaigns />} /><Route path="/content" element={<Content />} />
              <Route path="/approvals" element={<Approvals />} /><Route path="/publishing" element={<Publishing />} /><Route path="/brand" element={<Brand />} /><Route path="/calendar" element={<Calendar />} />
              <Route path="/integrations" element={<Integrations />} /><Route path="/team" element={<Team />} /><Route path="/audit" element={<Audit />} /><Route path="/settings" element={<Settings />} />
              <Route path="/copilot" element={<Copilot />} /><Route path="/agent" element={<AgentControl />} /><Route path="/analytics" element={<Analytics />} /><Route path="/owner" element={<Owner />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <footer className="foot"><span className="dots"><b>NematAnwar AI</b> Autonomous Marketing<i>·</i>Automate<i>·</i>Create<i>·</i>Analyze<i>·</i>Grow</span><span>Signed in as {user.full_name}, {label}</span></footer>
        </div>
      </div>
    </GestureProvider>
  );
}

export default function App() {
  const { user, booting, ws, permsReady } = useApp();
  return <>{booting ? <div className="auth"><Spinner label="Signing you in" /></div> : !user ? <Login /> : !ws ? <CreateWorkspace /> : !permsReady ? <div className="auth"><Spinner label="Loading your workspace" /></div> : <Shell key={ws.id} />}<Toasts /></>;
}
