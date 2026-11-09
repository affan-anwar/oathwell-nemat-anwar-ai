import { expect, test } from "@playwright/test";
import { goto, signUp, unique } from "./helpers.js";

const EMERALD = "rgb(16, 224, 138)", ORANGE = "rgb(255, 149, 0)";
const btn = async (page) => { await page.locator(".btn.primary").first().waitFor(); return page.evaluate(() => getComputedStyle(document.querySelector(".btn.primary")).backgroundColor); };
const studio = async (page) => { await signUp(page); await goto(page, "Owner Console"); await expect(page.getByText("Live preview")).toBeVisible(); };
const orange = async (page) => {
  await page.getByLabel("Primary / buttons hex", { exact: true }).fill("#ff9500");
  await page.getByLabel("Text on buttons hex", { exact: true }).fill("#000000");
};

test("colour changes apply live, persist once saved, and reset restores the default", async ({ page }) => {
  await studio(page);
  expect(await btn(page)).toBe(EMERALD);
  await orange(page);
  await expect.poll(() => btn(page)).toBe(ORANGE); // live, no save, no refresh
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText(/Theme saved/)).toBeVisible();
  await page.reload();
  await expect.poll(() => btn(page)).toBe(ORANGE); // loaded from the database
  await goto(page, "Campaigns");
  await expect.poll(() => btn(page)).toBe(ORANGE);
  await goto(page, "Owner Console");
  await page.getByRole("button", { name: "Reset to default" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Reset" }).click();
  await expect.poll(() => btn(page)).toBe(EMERALD);
  await page.reload();
  await expect.poll(() => btn(page)).toBe(EMERALD);
});

test("unreadable colours are refused with a reason", async ({ page }) => {
  await studio(page);
  await page.getByLabel("Text hex", { exact: true }).fill("#0d1d17"); // dark text on a dark card
  await expect(page.getByRole("alert").filter({ hasText: "Cannot be saved yet" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
});

test("an unsaved preview disappears when the Owner leaves the studio", async ({ page }) => {
  await studio(page);
  await orange(page);
  await expect.poll(() => btn(page)).toBe(ORANGE);
  await goto(page, "Campaigns");
  await expect.poll(() => btn(page)).toBe(EMERALD);
});

const login = async (request, email) => (await (await request.post("/api/v1/auth/login", { data: { email, password: "correct-horse-9" } })).json()).access_token;
async function asEditor(page, request, ownerEmail) {
  const oh = { Authorization: `Bearer ${await login(request, ownerEmail)}` };
  const ws = (await (await request.get("/api/v1/workspaces", { headers: oh })).json())[0].id;
  const email = unique("editor");
  await request.post("/api/v1/auth/register", { data: { email, password: "correct-horse-9", full_name: "Editor Person" } });
  await request.post(`/api/v1/workspaces/${ws}/members`, { headers: oh, data: { email, role: "editor" } });
  return { ws, email, eh: { Authorization: `Bearer ${await login(request, email)}` } };
}
async function signInAs(page, email) {
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-9");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Good (Morning|Afternoon|Evening)/ })).toBeVisible();
}

test("only the Owner can open the console or change platform colours, enforced by the server", async ({ page, request }) => {
  const owner = await signUp(page);
  const { ws, email, eh } = await asEditor(page, request, owner);
  await signInAs(page, email);
  await expect(page.getByRole("navigation").getByRole("link", { name: "Owner Console" })).toHaveCount(0);
  await page.goto("/owner");
  await expect(page.getByText("Only the workspace Owner can open the Owner Console.")).toBeVisible();
  const put = await request.put(`/api/v1/workspaces/${ws}/theme`, { headers: eh, data: { scope: "workspace", tokens: {}, default_mode: "dark", allow_user_mode: true } });
  expect(put.status()).toBe(403); // not just hidden in the interface
  expect((await request.put(`/api/v1/workspaces/${ws}/ai/config`, { headers: eh, data: { provider: "openai", model: "x" } })).status()).toBe(403);
  expect((await request.post(`/api/v1/workspaces/${ws}/emergency-shutdown`, { headers: eh })).status()).toBe(403);
});

test("each person keeps their own dark or light mode, and the Owner can lock it", async ({ page, request }) => {
  const owner = await signUp(page);
  const { ws, email, eh } = await asEditor(page, request, owner);
  await signInAs(page, email); // signing the Owner out also revoked the Owner's earlier API tokens, as it should
  const oh = { Authorization: `Bearer ${await login(request, owner)}` };
  await page.getByRole("button", { name: /switch to light theme/i }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light"); // remembered for this person
  expect((await (await request.get(`/api/v1/workspaces/${ws}/theme`, { headers: oh })).json()).my_mode).toBeNull(); // the Owner's own mode is untouched
  await request.put(`/api/v1/workspaces/${ws}/theme`, { headers: oh, data: { scope: "workspace", tokens: {}, default_mode: "dark", allow_user_mode: false } });
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark"); // the lock overrides the personal choice
  await expect(page.getByRole("button", { name: /switch to light theme/i })).toHaveAttribute("aria-disabled", "true"); // announced as unavailable
  await page.getByRole("button", { name: /switch to light theme/i }).click({ force: true }); // it still explains why
  await expect(page.getByText("The Owner has set the display mode for everyone")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect((await request.put(`/api/v1/workspaces/${ws}/preferences`, { headers: eh, data: { mode: "light" } })).status()).toBe(403);
});
