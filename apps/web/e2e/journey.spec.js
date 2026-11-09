import { expect, test } from "@playwright/test";
import { goto, signUp, unique } from "./helpers.js";

test("sign up, workspace, dashboard: no console errors", async ({ page }) => {
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await signUp(page);
  await expect(page.getByText("Not connected", { exact: true }).first()).toBeVisible(); // engagement is never invented
  await expect(page.getByText("Agent: Unavailable")).toBeVisible(); // no worker is reporting in
  expect(errors).toEqual([]);
});

test("a campaign is saved and survives a reload", async ({ page }) => {
  await signUp(page);
  await goto(page, "Campaigns");
  await page.getByRole("button", { name: "New campaign" }).first().click();
  await page.getByLabel("Name", { exact: true }).fill("Eid sale");
  await page.getByRole("button", { name: "Save campaign" }).click();
  await expect(page.getByText("Eid sale")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Eid sale")).toBeVisible();
});

test("content: write, save a new version, history and reload", async ({ page }) => {
  await signUp(page);
  await goto(page, "Content Studio");
  await page.getByRole("button", { name: "New document" }).click();
  await page.getByLabel("Title").fill("My first post");
  await page.getByLabel("Body").fill("Version one text.");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  const editor = page.getByLabel("Content body");
  await expect(editor).toHaveValue("Version one text.");
  await editor.fill("Version two text, edited.");
  await page.getByRole("button", { name: "Save as new version" }).click();
  await expect(page.locator(".li", { hasText: "v2" })).toBeVisible();
  await expect(page.locator(".li", { hasText: "v1" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: /My first post/ }).click();
  await expect(page.getByLabel("Content body")).toHaveValue("Version two text, edited.");
  await page.getByRole("button", { name: "Check quality" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Blog posts under 300 words" })).toBeVisible();
});

test("AI is honest when no provider is configured", async ({ page }) => {
  await signUp(page);
  await goto(page, "Content Studio");
  await page.getByLabel("What should it say?").fill("Launch post for new shoes");
  await page.getByRole("button", { name: "Generate draft" }).click();
  await expect(page.getByText(/AI provider not configured/)).toBeVisible();
  await expect(page.getByText("No content yet")).toBeVisible(); // nothing fake was saved
});

test("theme toggle is in the top bar and sign out is in the account menu", async ({ page }) => {
  await signUp(page);
  const before = await page.locator("html").getAttribute("data-theme");
  await page.getByRole("button", { name: /switch to (dark|light) theme/i }).click();
  expect(await page.locator("html").getAttribute("data-theme")).not.toBe(before);
  await page.getByRole("button", { name: "Account" }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.goto("/campaigns");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible(); // protected after sign out
});

test("quick actions open working flows", async ({ page }) => {
  await signUp(page);
  const qa = page.locator(".qa2");
  await qa.getByRole("link", { name: /Create campaign/ }).click();
  await expect(page.getByRole("dialog", { name: "New campaign" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.goto("/integrations?connect=wordpress");
  await expect(page.getByRole("dialog", { name: "Connect WordPress" })).toBeVisible();
  await page.goto("/");
  await page.locator(".qa2").getByRole("link", { name: /Generate content/ }).click();
  await expect(page.getByLabel("What should it say?")).toBeFocused();
});

test("keyboard fallback for gestures: Alt+Arrow moves between pages", async ({ page }) => {
  await signUp(page);
  await page.keyboard.press("Alt+ArrowRight");
  await expect(page.getByRole("heading", { level: 1, name: "Campaigns" })).toBeVisible();
  await page.keyboard.press("Alt+ArrowLeft");
  await expect(page.getByRole("heading", { level: 1, name: /Good (Morning|Afternoon|Evening)/ })).toBeVisible();
});

test("dashboard panels show real empty states, not sample numbers", async ({ page }) => {
  await signUp(page);
  await expect(page.getByText("Agent: Unavailable")).toBeVisible();
  await expect(page.getByText("0/0")).toBeVisible(); // no agents added
  await expect(page.getByText("Nothing is scheduled")).toHaveCount(0);
  await expect(page.locator(".sidecard", { hasText: "Connected integrations" }).getByText("Not available yet")).toHaveCount(3);
  await expect(page.getByText("No campaigns here")).toBeVisible();
});

test("top search finds a saved campaign and opens it", async ({ page }) => {
  await signUp(page);
  await goto(page, "Campaigns");
  await page.getByRole("button", { name: "New campaign" }).first().click();
  await page.getByLabel("Name", { exact: true }).fill("Eid sale");
  await page.getByRole("button", { name: "Save campaign" }).click();
  await expect(page.getByRole("cell", { name: /Eid sale/ })).toBeVisible();
  await page.getByLabel("Search campaigns and content").fill("eid");
  await page.getByRole("region", { name: "Search results" }).getByRole("button", { name: /Eid sale/ }).click();
  await expect(page).toHaveURL(/\/campaigns/);
});

test("sign in with a wrong password shows an error and the lock-out message after repeated failures", async ({ page }) => {
  const email = unique("lock");
  await signUp(page, email);
  await page.getByRole("button", { name: "Account" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible(); // wait for the sign-in page before typing
  for (let i = 0; i < 5; i++) {
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("wrong-password-1");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Wrong email or password");
  }
  await page.getByLabel("Password").fill("correct-horse-9");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Too many failed sign-in attempts");
});
