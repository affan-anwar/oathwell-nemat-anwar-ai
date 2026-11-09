import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "../api.js";
import { PRESETS_FOR_TEST } from "../pages/Owner.jsx";
import { problems } from "../theme.js";
import { DEF, mockApi, show } from "./helpers.jsx";

beforeEach(() => { sessionStorage.clear(); localStorage.clear(); document.documentElement.setAttribute("data-theme", "dark"); document.getElementById("owner-theme")?.remove(); document.getElementById("owner-preview")?.remove(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const studio = async () => { setToken("t"); const calls = mockApi(); show("/owner"); await screen.findByText("Live preview"); return calls; };
const hexFor = (label) => screen.getByLabelText(`${label} hex`);

describe("Theme Studio (Owner)", () => {
  it("every preset passes the same contrast rules the server enforces", () => {
    for (const [name, t] of PRESETS_FOR_TEST) {
      const merged = JSON.parse(JSON.stringify(DEF));
      if (t) for (const m of ["dark", "light"]) Object.assign(merged[m], t[m]);
      expect(problems(merged.dark), `${name} dark`).toEqual([]); expect(problems(merged.light), `${name} light`).toEqual([]);
    }
  });
  it("a colour change is applied live without saving", async () => {
    const calls = await studio();
    fireEvent.change(hexFor("primary"), { target: { value: "#ff9500" } });
    await waitFor(() => expect(document.getElementById("owner-preview")?.textContent).toContain("--pri:#ff9500"));
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
    expect(screen.getByText("You have unsaved changes.")).toBeTruthy();
  });
  it("hex, colour picker and RGB inputs stay in sync", async () => {
    await studio();
    fireEvent.change(screen.getByLabelText("primary R"), { target: { value: "255" } });
    expect(hexFor("primary").value.startsWith("#ff")).toBe(true);
    fireEvent.change(screen.getByLabelText("primary colour"), { target: { value: "#123456" } });
    expect(hexFor("primary").value).toBe("#123456");
  });
  it("unreadable colours are explained and Save stays disabled", async () => {
    await studio();
    fireEvent.change(hexFor("text"), { target: { value: "#0d1d17" } }); // dark text on a dark card
    expect(await screen.findByText("Cannot be saved yet")).toBeTruthy();
    expect(screen.getAllByText(/contrast|4\.5:1/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Save" }).disabled).toBe(true);
  });
  it("Save sends the chosen scope, tokens and mode settings to the server", async () => {
    const calls = await studio();
    fireEvent.change(hexFor("primary"), { target: { value: "#ff9500" } }); fireEvent.change(hexFor("primaryText"), { target: { value: "#000000" } });
    fireEvent.change(screen.getByLabelText("Apply to"), { target: { value: "global" } });
    fireEvent.click(screen.getByLabelText("Let each person choose their own dark or light mode"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT" && c.p.endsWith("/theme"))).toBe(true));
    const body = JSON.parse(calls.find((c) => c.method === "PUT" && c.p.endsWith("/theme")).body);
    expect(body.scope).toBe("global"); expect(body.allow_user_mode).toBe(false); expect(body.tokens.dark.primary).toBe("#ff9500");
  });
  it("Cancel discards the draft and the live preview; Reset asks first", async () => {
    const calls = await studio();
    fireEvent.change(hexFor("primary"), { target: { value: "#ff9500" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(document.getElementById("owner-preview")?.textContent).toContain(`--pri:${DEF.dark.primary}`));
    expect(hexFor("primary").value).toBe(DEF.dark.primary);
    fireEvent.click(screen.getByRole("button", { name: "Reset to default" }));
    expect(await screen.findByRole("dialog", { name: "Reset the theme?" })).toBeTruthy();
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.p.includes("/theme?scope="))).toBe(true));
  });
  it("leaving the studio removes an unsaved preview", async () => {
    await studio();
    fireEvent.change(hexFor("primary"), { target: { value: "#ff9500" } });
    fireEvent.click(within(screen.getByRole("navigation")).getByRole("link", { name: "Team" }));
    await waitFor(() => expect(document.getElementById("owner-preview")).toBeNull());
  });
});

describe("AI providers and access (Owner)", () => {
  it("shows a provider as not connected until a test succeeds, and never shows keys", async () => {
    setToken("t"); mockApi(); show("/owner");
    fireEvent.click(await screen.findByRole("tab", { name: "AI Providers" }));
    expect(await screen.findByText("No key")).toBeTruthy(); expect(screen.getByText("OPENAI_API_KEY")).toBeTruthy();
    expect(screen.queryByText("Connected")).toBeNull();
  });
  it("Test connection reports the provider's real error", async () => {
    setToken("t"); mockApi({ "/workspaces/w1/ai/providers/openai/test": { body: { ok: false, error: "The provider rejected the API key (HTTP 401)" } } }); show("/owner");
    fireEvent.click(await screen.findByRole("tab", { name: "AI Providers" }));
    fireEvent.click(await screen.findByRole("button", { name: "Test connection" }));
    expect(await screen.findByText(/rejected the API key/)).toBeTruthy();
  });
  it("emergency shutdown needs an explicit confirmation", async () => {
    setToken("t"); const calls = mockApi(); show("/owner");
    fireEvent.click(await screen.findByRole("tab", { name: "Access & Safety" }));
    fireEvent.click(await screen.findByRole("button", { name: "Emergency shutdown" }));
    const dlg = await screen.findByRole("dialog", { name: "Shut down this workspace?" });
    expect(within(dlg).getByRole("button", { name: "Shut down" }).disabled).toBe(true);
    fireEvent.click(within(dlg).getByLabelText("I understand and want to continue"));
    expect(calls.some((c) => c.p.endsWith("/emergency-shutdown"))).toBe(false);
  });
});

describe("Team page protects the Owner", () => {
  it("the Owner and the signed-in person have no role controls; others do", async () => {
    setToken("t"); mockApi(); show("/team");
    expect(await screen.findByText(/The Owner is protected/)).toBeTruthy();
    expect(screen.queryByLabelText("Role for o@example.com")).toBeNull();
    expect(screen.getByLabelText("Role for e@example.com")).toBeTruthy();
  });
});
