import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "../App.jsx";
import { AppProvider } from "../state.jsx";

// MOCKED API. These tests prove the screens render and handle empty, error and restricted data. They do not prove the real backend.
export const DEF = {
  dark: { bg: "#030907", surface: "#08130f", surface2: "#0d1d17", text: "#f1f5f3", muted: "#9db3aa", border: "#16382c", primary: "#10e08a", primaryText: "#03120b", success: "#34d399", warning: "#fbbf24", danger: "#f87171", accent: "#6ee7b7", sidebar: "#020605", chart1: "#10e08a", chart2: "#e5efe9" },
  light: { bg: "#eef5f1", surface: "#ffffff", surface2: "#f4f9f6", text: "#0a1f17", muted: "#4b6358", border: "#d3e2da", primary: "#046c4e", primaryText: "#ffffff", success: "#047857", warning: "#92400e", danger: "#b91c1c", accent: "#065f46", sidebar: "#ffffff", chart1: "#046c4e", chart2: "#0a1f17" },
};
const LABELS = Object.fromEntries(Object.keys(DEF.dark).map((k) => [k, k]));
const ALL = ["read", "content.write", "campaign.write", "approval.request", "publish.execute", "brand.write", "events.plan", "approval.decide", "integration.manage", "member.manage", "automation.pause", "audit.read", "events.manage", "theme.write", "admin.delegate", "role.manage_privileged", "credentials.revoke", "emergency.shutdown", "ai.manage"];
const ROLES = ["viewer", "research_agent", "analytics_agent", "content_agent", "publishing_agent", "super_agent", "editor", "admin", "owner"].map((r) => ({ role: r, label: r, permissions: ["read"] }));
export const permsFor = (role) => ({ role, label: role === "owner" ? "Owner" : "Viewer", permissions: role === "owner" ? ALL : ["read"], admin_revoked: [], delegable: ["approval.decide", "integration.manage", "member.manage", "automation.pause", "audit.read", "events.manage"], roles: ROLES });
const WS = [{ id: "w1", name: "Acme", role: "owner", paused: false }];
export const DASH = {
  days: 7,
  agent: { state: "Unavailable", reason: "The scheduler worker is not running or has not reported in the last 90 seconds.", worker_last_seen: null, next_task: null, last_execution: null },
  kpis: { campaigns: { total: 0, by_status: {} }, content_created: { value: 0, previous: 0 }, posts_published: { value: 0, previous: 0 }, engagement_rate: { state: "unavailable", reason: "No analytics source is connected." } },
  definitions: { campaigns: "c", content_created: "cc", posts_published: "pp", progress: "p" },
  series: Array.from({ length: 7 }, (_, i) => ({ date: `2026-10-${10 + i}`, content_created: 0, posts_published: 0 })),
  today_tasks: [], quick: { active_campaigns: 0, content_in_review: 0, scheduled: 0, published_today: 0 }, agents: { active: 0, total: 0 }, campaigns: [], upcoming: [], integrations: [],
};
const SHAPES = {
  dashboard: DASH, activity: [], search: { campaigns: [{ id: "c1", name: "Eid Offers", status: "DRAFT" }], content: [] },
  notifications: { unread: 0, items: [] },
  "ai/usage": { requests: 0, input_tokens: 0, output_tokens: 0, limit: 200, remaining: 200, by_provider: {}, estimated_cost: null, currency: "USD", cost_note: "Unavailable. Set prices.", note: "n" },
  "metrics/operations": { days: 30, source: "internal", approvals: {}, executions: {}, publish_success_rate: null, content_created: 0, ai_requests: 0 },
  calendar: { scheduled: [], campaigns: [], times_are: "UTC" }, jobs: { counts: {}, items: [] },
  "ai/providers": { providers: [{ provider: "openai", label: "OpenAI", env: "OPENAI_API_KEY", key_configured: false, connected: false, last_test_at: null, last_ok_at: null, last_error: null, models: [] }], config: null, note: "Model IDs differ between accounts." },
};
export function mockApi(overrides = {}, role = "owner", theme = {}) {
  const calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url, opts) => {
    const p = String(url).replace("/api/v1", ""); calls.push({ p, method: opts?.method || "GET", body: opts?.body });
    for (const [k, v] of Object.entries(overrides)) if (p.startsWith(k)) return { status: v.status || 200, ok: (v.status || 200) < 400, json: async () => v.body };
    let body;
    if (p === "/workspaces") body = [{ ...WS[0], role }];
    else if (p.endsWith("/permissions")) body = permsFor(role);
    else if (p.endsWith("/theme")) body = { source: "default", tokens: DEF, defaults: DEF, labels: LABELS, default_mode: "dark", allow_user_mode: true, editable: role === "owner", my_mode: null, updated_at: null, ...theme };
    else if (p.startsWith("/auth/me")) body = { id: "u1", email: "o@example.com", full_name: "Owner Person" };
    else if (p.endsWith("/profile")) body = { languages: [], competitors: [], channels: [], occasions: [] };
    else if (p.includes("/members")) body = [{ user_id: "u1", email: "o@example.com", full_name: "Owner Person", role: "owner", label: "Owner", suspended: false }, { user_id: "u2", email: "e@example.com", full_name: "Editor Person", role: "editor", label: "editor", suspended: false }];
    else { const s = Object.entries(SHAPES).find(([k]) => p.includes(`/${k}`)); body = s ? s[1] : []; }
    return { status: 200, ok: true, json: async () => body };
  }));
  return calls;
}
export const show = (path) => render(<MemoryRouter initialEntries={[path]}><AppProvider><App /></AppProvider></MemoryRouter>);
