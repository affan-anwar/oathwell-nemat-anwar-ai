import { expect } from "@playwright/test";

export const unique = (p) => `${p}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;

export async function signUp(page, email = unique("e2e")) {
  await page.goto("/");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Full name").fill("E2E User");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-9");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByLabel("Business name").fill("E2E Co");
  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Good (Morning|Afternoon|Evening)/ })).toBeVisible();
  return email;
}

export const goto = (page, name) => page.getByRole("navigation").getByRole("link", { name, exact: true }).click();
