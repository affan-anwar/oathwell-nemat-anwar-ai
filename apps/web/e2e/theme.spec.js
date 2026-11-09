import { expect, test } from "@playwright/test";
import { goto, signUp } from "./helpers.js";

const bg = (page, sel) => page.evaluate((s) => { const c = getComputedStyle(document.querySelector(s)); return c.backgroundColor + "|" + c.backgroundImage; }, sel);

test.describe("dark default", () => {
  test.use({ colorScheme: "light" }); // the operating system says light; dark is still the default
  test("the whole app switches, and the choice survives reload and navigation", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark"); // even the sign-in page
    await signUp(page);
    await expect(page.locator(".card").first()).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem("na_theme"))).toBeNull(); // nothing saved until the user chooses
    const dark = { body: await bg(page, "body"), side: await bg(page, ".side"), card: await bg(page, ".card"), top: await bg(page, ".top") };
    await page.getByRole("button", { name: "Switch to light theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    const light = { body: await bg(page, "body"), side: await bg(page, ".side"), card: await bg(page, ".card"), top: await bg(page, ".top") };
    for (const k of Object.keys(dark)) expect(light[k], `${k} should change with the theme`).not.toBe(dark[k]);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await goto(page, "Campaigns");
    await goto(page, "Content Studio");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    expect(await page.evaluate(() => localStorage.getItem("na_theme"))).toBe("light");
  });

  test("the theme is set before first paint, and the button works from the keyboard", async ({ page }) => {
    await signUp(page);
    await page.getByRole("button", { name: "Switch to light theme" }).click();
    await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(await page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe("light"); // set by the blocking script in the head
    await page.getByRole("button", { name: "Switch to dark theme" }).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.getByRole("button", { name: "Switch to light theme" })).toBeVisible();
  });
});

test.describe("match my system", () => {
  test.use({ colorScheme: "dark" });
  test("follows the device live, only after the user chooses it in Settings", async ({ page }) => {
    await signUp(page);
    await goto(page, "Settings");
    await page.getByLabel("Appearance").selectOption("system");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.emulateMedia({ colorScheme: "light" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light"); // the device changed, the app followed
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light"); // still following after a reload
    await page.getByRole("button", { name: "Switch to dark theme" }).click(); // an explicit choice ends following
    await page.emulateMedia({ colorScheme: "light" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });
});
