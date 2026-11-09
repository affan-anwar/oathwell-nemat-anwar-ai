import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { signUp } from "./helpers.js";

const PAGES = ["/", "/campaigns", "/content", "/copilot", "/agent", "/calendar", "/approvals", "/publishing", "/analytics", "/integrations", "/team", "/audit", "/brand", "/settings", "/owner"];

for (const theme of ["light", "dark"]) {
  test(`no serious accessibility violations on all 15 screens (${theme})`, async ({ page }) => {
    await signUp(page);
    if (theme === "light") await page.getByRole("button", { name: "Switch to light theme" }).click(); // dark is the default
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    for (const path of PAGES) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForTimeout(300);
      const { violations } = await new AxeBuilder({ page }).analyze();
      const bad = violations.filter((v) => ["serious", "critical"].includes(v.impact));
      expect(bad.map((v) => `${path}: ${v.id} ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`), `${theme} ${path}`).toEqual([]);
    }
  });
}

test("phone width: no sideways scroll and account menu reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await signUp(page);
  for (const path of PAGES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForTimeout(250);
    const { overflow, offenders } = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      offenders: [...document.querySelectorAll("*")].filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1)
        .map((e) => `${e.tagName.toLowerCase()}.${String(e.className).slice(0, 25)} right=${Math.round(e.getBoundingClientRect().right)}`).slice(0, 6),
    }));
    expect(overflow, `horizontal overflow on ${path}: ${offenders.join(", ")}`).toBeLessThanOrEqual(0);
  }
  const toggle = page.getByRole("button", { name: /switch to (dark|light) theme/i });
  await expect(toggle).toBeVisible();
  const tb = await toggle.boundingBox();
  expect(tb.x + tb.width).toBeLessThanOrEqual(390); // the theme switch is reachable on a phone
  await page.getByRole("button", { name: "Account" }).click();
  const out = page.getByRole("button", { name: "Sign out", exact: true });
  await expect(out).toBeVisible();
  const box = await out.boundingBox();
  expect(box.x + box.width).toBeLessThanOrEqual(390);
});

test("phone menu drawer opens and navigates", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await signUp(page);
  await page.getByRole("button", { name: "Toggle menu" }).click();
  await page.getByRole("navigation").getByRole("link", { name: "Calendar", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Occasions calendar" })).toBeVisible();
});

test("calendar toolbar stays on one row at desktop width", async ({ page }) => {
  await signUp(page);
  await page.goto("/calendar");
  const month = await page.getByLabel("Month", { exact: true }).boundingBox();
  const year = await page.getByLabel("Year", { exact: true }).boundingBox();
  expect(Math.abs(month.y - year.y)).toBeLessThan(8);
  expect(month.width).toBeLessThan(260);
});
