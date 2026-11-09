import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "../api.js";
import { DEF, DASH, mockApi, show } from "./helpers.jsx";

beforeEach(() => { sessionStorage.clear(); localStorage.clear(); document.documentElement.setAttribute("data-theme", "dark"); document.getElementById("owner-theme")?.remove(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("signed out", () => {
  it("shows the sign in form", async () => { mockApi(); show("/"); expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy(); });
});

describe("every screen renders with empty data", () => {
  const pages = [["/", /Good (Morning|Afternoon|Evening)/], ["/campaigns", "Campaigns"], ["/content", "Content Studio"], ["/agent", "Agent Control Center"], ["/calendar", "Occasions calendar"], ["/approvals", "Approval inbox"], ["/publishing", "Publishing"], ["/analytics", "Analytics"], ["/integrations", "Integrations"], ["/team", "Team"], ["/audit", "Audit Log"], ["/brand", "Brand Voice"], ["/settings", "Settings"], ["/owner", "Owner Console"], ["/copilot", "AI Copilot"]];
  for (const [path, title] of pages) {
    it(String(title), async () => { setToken("t"); mockApi(); show(path); expect(await screen.findByRole("heading", { level: 1, name: title })).toBeTruthy(); });
  }
  it("the sidebar lists the 13 sections plus the Owner Console for the Owner", async () => {
    setToken("t"); mockApi(); show("/");
    const nav = await screen.findByRole("navigation");
    for (const n of ["Dashboard", "Campaigns", "Content Studio", "Agent Control Center", "Calendar", "Approvals", "Publishing", "Analytics", "Integrations", "Team", "Audit Log", "Brand Voice", "Settings", "Owner Console"]) expect(within(nav).getByRole("link", { name: n })).toBeTruthy();
  });
  it("a viewer does not get the Owner Console link and sees Owner only on that page", async () => {
    setToken("t"); mockApi({}, "viewer"); show("/owner");
    expect(await screen.findByText("Only the workspace Owner can open the Owner Console.")).toBeTruthy();
    expect(within(screen.getByRole("navigation")).queryByRole("link", { name: "Owner Console" })).toBeNull();
  });
  it("viewer cannot see create buttons", async () => {
    setToken("t"); mockApi({}, "viewer"); show("/campaigns");
    await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Campaigns" })).toBeTruthy());
    expect(screen.queryByRole("button", { name: "New campaign" })).toBeNull();
  });
  it("shows an honest error with retry when the API fails", async () => {
    setToken("t"); mockApi({ "/workspaces/w1/campaigns": { status: 500, body: {} } }); show("/campaigns");
    expect(await screen.findByRole("alert")).toBeTruthy(); expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

describe("dashboard tells the truth", () => {
  it("agent Unavailable and engagement Not connected when nothing reports in", async () => {
    setToken("t"); mockApi(); show("/");
    expect(await screen.findByText("Agent: Unavailable")).toBeTruthy(); expect(screen.getAllByText("Not connected").length).toBeGreaterThan(0);
    expect(screen.getByText("Worker offline")).toBeTruthy();
  });
  it("Running only when the API says so, with real quick stats and agent counts", async () => {
    setToken("t");
    mockApi({ "/workspaces/w1/dashboard": { body: { ...DASH, agent: { ...DASH.agent, state: "Running", reason: "The scheduler worker is reporting in." }, quick: { active_campaigns: 2, content_in_review: 3, scheduled: 4, published_today: 5 }, agents: { active: 2, total: 3 } } } });
    show("/");
    expect(await screen.findByText("Agent: Running")).toBeTruthy(); expect(screen.getByText("System healthy")).toBeTruthy();
    expect(screen.getByText("2/3")).toBeTruthy(); expect(screen.getByText("Content in review").nextSibling.textContent).toBe("3");
  });
  it("campaign progress is unknown, not zero, when no content is linked", async () => {
    setToken("t");
    mockApi({ "/workspaces/w1/dashboard": { body: { ...DASH, kpis: { ...DASH.kpis, campaigns: { total: 1, by_status: { ACTIVE: 1 } } }, campaigns: [{ id: "c1", name: "Eid push", objective: null, status: "ACTIVE", channels: ["blog"], start_date: null, end_date: null, content_count: 0, published_count: 0, progress: null }] } } });
    show("/");
    expect(await screen.findByText("No content yet")).toBeTruthy(); expect(screen.queryByRole("progressbar")).toBeNull();
  });
  it("social platforms are shown as not available, never as connected", async () => {
    setToken("t"); mockApi(); show("/");
    await screen.findByText("Agent: Unavailable");
    for (const n of ["Instagram", "LinkedIn", "Facebook"]) expect(screen.getByText(n).parentElement.textContent).toContain("Not available yet");
  });
  it("AI Content Studio shows the server's setup message and keeps nothing when AI is not configured", async () => {
    setToken("t"); mockApi({ "/workspaces/w1/content/generate": { status: 503, body: { detail: "AI provider not configured. Set OPENAI_API_KEY on the server." } } }); show("/");
    fireEvent.change(await screen.findByLabelText("Topic or keywords"), { target: { value: "Eid sale" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate content" }));
    expect(await screen.findByText(/AI provider not configured/)).toBeTruthy(); expect(screen.queryByText(/Saved as draft/)).toBeNull();
  });
});

describe("shell", () => {
  it("account menu holds settings and sign out", async () => {
    setToken("t"); mockApi(); show("/");
    fireEvent.click(await screen.findByRole("button", { name: /account menu/i }));
    expect(within(screen.getByRole("region", { name: "Account" })).getByRole("link", { name: "Settings" })).toBeTruthy(); expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
  });
  it("search finds a campaign from the top bar", async () => {
    setToken("t"); mockApi(); show("/");
    fireEvent.change(await screen.findByLabelText("Search campaigns and content"), { target: { value: "ei" } });
    expect(await screen.findByText("Eid Offers")).toBeTruthy();
  });
  it("notification bell shows the unread count", async () => {
    setToken("t"); mockApi({ "/workspaces/w1/notifications": { body: { unread: 3, items: [{ id: "n1", kind: "approval_requested", title: "Approval needed", body: null, link: "/approvals", read: false, created_at: "2026-10-20T10:00:00" }] } } }); show("/");
    expect(await screen.findByRole("button", { name: /Alerts.*3.*unread/ })).toBeTruthy();
  });
  it("Alt+Right Arrow moves to the next page (keyboard fallback for gestures)", async () => {
    setToken("t"); mockApi(); show("/");
    await screen.findByText("Agent: Unavailable");
    fireEvent.keyDown(window, { key: "ArrowRight", altKey: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Campaigns" })).toBeTruthy();
  });
});

describe("dark and light mode for every person", () => {
  const toggle = () => screen.findByRole("button", { name: /switch to (dark|light) theme/i });
  it("toggles the whole app, saves the person's own choice on the server, and toggles back", async () => {
    setToken("t"); const calls = mockApi(); show("/");
    fireEvent.click(await toggle());
    expect(document.documentElement.getAttribute("data-theme")).toBe("light"); expect(localStorage.getItem("na_theme")).toBe("light");
    await waitFor(() => expect(calls.some((c) => c.p.endsWith("/preferences") && c.method === "PUT" && JSON.parse(c.body).mode === "light")).toBe(true));
    fireEvent.click(await toggle());
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
  it("restores the person's saved mode from the server", async () => {
    setToken("t"); mockApi({}, "owner", { my_mode: "light" }); show("/");
    await screen.findByText("Agent: Unavailable");
    await waitFor(() => expect(document.documentElement.getAttribute("data-theme")).toBe("light"));
  });
  it("the Owner's default mode applies until the person chooses", async () => {
    setToken("t"); mockApi({}, "owner", { default_mode: "light" }); show("/");
    await screen.findByText("Agent: Unavailable");
    await waitFor(() => expect(document.documentElement.getAttribute("data-theme")).toBe("light"));
  });
  it("when the Owner locks the mode, other people cannot change it", async () => {
    setToken("t"); const calls = mockApi({}, "viewer", { allow_user_mode: false, default_mode: "dark" }); show("/");
    fireEvent.click(await toggle());
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(calls.some((c) => c.p.endsWith("/preferences"))).toBe(false);
    expect(await screen.findByText("The Owner has set the display mode for everyone")).toBeTruthy();
  });
  it("the Owner's brand colours are injected as CSS variables and a person's mode does not remove them", async () => {
    setToken("t"); mockApi({}, "owner", { source: "workspace", tokens: { dark: { ...DEF.dark, primary: "#ff9500" }, light: DEF.light } }); show("/");
    await screen.findByText("Agent: Unavailable");
    await waitFor(() => expect(document.getElementById("owner-theme")?.textContent).toContain("--pri:#ff9500"));
    expect(document.getElementById("owner-theme").textContent).toContain("--btn:#ff9500");
  });
});
