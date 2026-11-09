import { expect, test } from "@playwright/test";
import { unique } from "./helpers.js";

// Needs: API started with ALLOW_PRIVATE_URLS=true and `node e2e/fake-wordpress.mjs` running. The "site" is a MOCK.
const FAKE = "http://127.0.0.1:8099";
test.skip(!process.env.E2E_FAKE_WP, "set E2E_FAKE_WP=1 with the fake WordPress and the API configured for it");

test("a lost response becomes UNCLEAR, then Check the site finds the post without posting twice", async ({ page, request }) => {
  await request.get(`${FAKE}/__mode?m=reset`);
  const email = unique("fc");
  await request.post("/api/v1/auth/register", { data: { email, password: "correct-horse-9", full_name: "FC" } });
  const tok = (await (await request.post("/api/v1/auth/login", { data: { email, password: "correct-horse-9" } })).json()).access_token;
  const h = { Authorization: `Bearer ${tok}` };
  const ws = (await (await request.post("/api/v1/workspaces", { headers: h, data: { name: "FC Co" } })).json()).id;
  const b = `/api/v1/workspaces/${ws}`;
  const integ = await (await request.post(`${b}/integrations/wordpress`, { headers: h, data: { label: "Local site", site_url: FAKE, username: "bot", app_password: "abcd efgh ijkl" } })).json();
  expect((await (await request.post(`${b}/integrations/${integ.id}/test`, { headers: h })).json()).status).toBe("connected");
  const doc = await (await request.post(`${b}/content`, { headers: h, data: { kind: "blog", title: "Lost reply post", body: "Hello world" } })).json();
  const ap = await (await request.post(`${b}/approvals`, { headers: h, data: { version_id: doc.versions[0].id, integration_id: integ.id, action: "publish_blog" } })).json();
  await request.post(`${b}/approvals/${ap.id}/decision`, { headers: h, data: { decision: "approve" } });
  await request.get(`${FAKE}/__mode?m=lost`);
  const ex = await (await request.post(`${b}/approvals/${ap.id}/execute`, { headers: h })).json();
  expect(ex.execution.status).toBe("UNCLEAR");

  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-9");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("navigation").getByRole("link", { name: "Publishing", exact: true }).click();
  const row = page.locator("tr", { hasText: "Lost reply post" });
  await expect(row.getByText("unclear")).toBeVisible();
  await expect(row.getByRole("button", { name: "Retry" })).toHaveCount(0); // never offered while unclear
  await row.getByRole("button", { name: "Check the site" }).click();
  await expect(row.getByText("published")).toBeVisible();
  await expect(row.getByText(/confirmed by checking the site/)).toBeVisible();
  const posts = await (await request.get(`${FAKE}/__posts`)).json();
  expect(posts).toHaveLength(1); // checked, never posted again
});
