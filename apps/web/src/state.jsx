import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";
import { setStyle, tokensToCss } from "./theme.js";

// Old role names still map to a permission, so nothing silently breaks. Prefer real permission names.
const LEGACY = { viewer: "read", editor: "content.write", admin: "approval.decide", owner: "theme.write" };
const Ctx = createContext(null);
export const useApp = () => useContext(Ctx);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(!!getToken());
  const [workspaces, setWorkspaces] = useState([]);
  const [wsId, setWsId] = useState(sessionStorage.getItem("na_ws"));
  const wsIdRef = { current: wsId };
  const [toasts, setToasts] = useState([]);
  // Dark is the default. "system" is an explicit choice, because browsers report "no preference" as light.
  const [themeMode, setThemeModeState] = useState(() => { try { const m = localStorage.getItem("na_theme"); return ["light", "dark", "system"].includes(m) ? m : "dark"; } catch { return "dark"; } });
  const [theme, setThemeState] = useState(() => document.documentElement.getAttribute("data-theme") || "dark");
  const apply = useCallback((m, persist) => {
    if (persist) localStorage.setItem("na_theme", m);
    const t = m === "system" ? (window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark") : m;
    document.documentElement.setAttribute("data-theme", t);
    setThemeModeState(m); setThemeState(t);
  }, []);
  const [perms, setPerms] = useState(null);
  const [themeCfg, setThemeCfg] = useState(null);
  const locked = !!themeCfg && themeCfg.allow_user_mode === false && perms?.role !== "owner";
  const savePref = (m) => { if (wsIdRef.current) api(`/workspaces/${wsIdRef.current}/preferences`, { method: "PUT", body: { mode: m } }).catch(() => {}); };
  const choose = (m) => {
    if (locked) { toast("The Owner has set the display mode for everyone", "wn"); return; }
    apply(m, true); savePref(m);
  };
  const setThemeMode = (m) => choose(m);
  const toggleTheme = () => choose(theme === "dark" ? "light" : "dark");
  useEffect(() => {
    if (themeMode !== "system" || !window.matchMedia) return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const follow = () => apply("system", false);
    mq.addEventListener?.("change", follow);
    return () => mq.removeEventListener?.("change", follow);
  }, [themeMode, apply]);

  wsIdRef.current = wsId;
  const toast = useCallback((msg, kind = "ok") => {
    const id = Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);

  const loadWorkspaces = useCallback(async () => {
    const w = await api("/workspaces");
    setWorkspaces(w);
    setWsId((cur) => (w.find((x) => x.id === cur) ? cur : w[0]?.id || null));
    return w;
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    api("/auth/me").then(setUser).then(loadWorkspaces).catch(() => setToken(null)).finally(() => setBooting(false));
  }, [loadWorkspaces]);

  useEffect(() => {
    const f = () => { setUser(null); setWorkspaces([]); };
    window.addEventListener("na-logout", f);
    return () => window.removeEventListener("na-logout", f);
  }, []);

  useEffect(() => {
    if (wsId) sessionStorage.setItem("na_ws", wsId);
    else sessionStorage.removeItem("na_ws");
  }, [wsId]);

  const reloadTheme = useCallback(async (id = wsIdRef.current) => {
    if (!id) return null;
    const cfg = await api(`/workspaces/${id}/theme`).catch(() => null);
    if (!cfg) return null;
    setThemeCfg(cfg);
    setStyle("owner-theme", tokensToCss(cfg.tokens));
    return cfg;
  }, []);

  useEffect(() => {
    if (!user || !wsId) { setPerms(null); setThemeCfg(null); setStyle("owner-theme", ""); return undefined; }
    let live = true;
    Promise.all([api(`/workspaces/${wsId}/permissions`).catch(() => null), reloadTheme(wsId)]).then(([p, cfg]) => {
      if (!live) return;
      setPerms(p && Array.isArray(p.permissions) ? p : { role: null, permissions: [] });
      if (!cfg) return;
      const isOwner = p?.role === "owner";
      if (cfg.allow_user_mode === false && !isOwner) apply(cfg.default_mode, false);  // Owner locked the mode
      else if (cfg.my_mode) apply(cfg.my_mode, true);                                  // this person's own saved choice
      else if (!localStorage.getItem("na_theme")) apply(cfg.default_mode, false);      // the Owner's default
    });
    return () => { live = false; };
  }, [user, wsId, reloadTheme, apply]);

  const previewTheme = (tokens) => setStyle("owner-preview", tokensToCss(tokens));
  const clearPreview = () => setStyle("owner-preview", "");

  const login = async (email, password) => {
    const r = await api("/auth/login", { method: "POST", body: { email, password } });
    setToken(r.access_token);
    setUser(await api("/auth/me"));
    await loadWorkspaces();
  };
  const register = async (email, password, full_name) => {
    await api("/auth/register", { method: "POST", body: { email, password, full_name } });
    await login(email, password);
  };
  const logout = async () => {
    try { await api("/auth/logout", { method: "POST" }); } catch { /* token may already be invalid */ }
    setToken(null); setUser(null); setWorkspaces([]); setWsId(null);
  };
  const ws = workspaces.find((w) => w.id === wsId) || null;
  // UI convenience only. The server enforces every permission.
  const can = (p) => !!perms && perms.permissions.includes(LEGACY[p] || p);

  return (
    <Ctx.Provider value={{ user, booting, workspaces, ws, wsId, setWsId, loadWorkspaces, login, register, logout, can, perms, permsReady: perms !== null, toast, toasts, theme, themeMode, setThemeMode, toggleTheme, themeCfg, themeLocked: locked, reloadTheme, previewTheme, clearPreview }}>
      {children}
    </Ctx.Provider>
  );
}
