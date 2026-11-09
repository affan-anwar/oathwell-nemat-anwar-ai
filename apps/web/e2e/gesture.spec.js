import { expect, test } from "@playwright/test";
import { signUp } from "./helpers.js";

// Needs Chromium started with --use-fake-device-for-media-stream --use-fake-ui-for-media-stream (a pretend camera).
// This proves the permission, indicator and stop behaviour. It does not prove hand detection with a real hand.
test.skip(!process.env.E2E_FAKE_CAMERA, "set E2E_FAKE_CAMERA=1 and start Chromium with the fake camera flags");

test("the camera stays off until enabled, shows an indicator, and really stops", async ({ page }) => {
  await page.addInitScript(() => {
    window.__tracks = [];
    const orig = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async (c) => { const s = await orig(c); window.__tracks.push(...s.getTracks()); return s; };
  });
  await signUp(page);
  await expect(page.getByText("Camera on")).toHaveCount(0);
  expect(await page.evaluate(() => window.__tracks.length)).toBe(0); // nothing requested at load
  await page.getByRole("switch", { name: "Enable gesture controls" }).click();
  await expect(page.getByText("Camera on")).toBeVisible();
  expect(await page.evaluate(() => window.__tracks.filter((t) => t.readyState === "live").length)).toBeGreaterThan(0); // a real live camera track
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByText("Camera on")).toHaveCount(0);
  expect(await page.evaluate(() => window.__tracks.filter((t) => t.readyState === "live").length)).toBe(0); // the camera was released
});
