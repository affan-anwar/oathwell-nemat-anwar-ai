import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CameraIndicator, GesturePanel, GestureProvider } from "../GestureControl.jsx";
import { SAFE_ACTIONS, W, detectSwipe, motionCentroid } from "../gesture.js";

const run = (xs, step = 80, mass = 0.1) => xs.map((x, i) => ({ t: i * step, x, mass }));

describe("swipe detection (pure logic on synthetic data)", () => {
  it("recognises a consistent sweep in each direction, from the person's point of view", () => {
    expect(detectSwipe(run([0.1, 0.25, 0.4, 0.55, 0.7, 0.85]))).toBe("left");   // toward larger x in the unmirrored picture
    expect(detectSwipe(run([0.85, 0.7, 0.55, 0.4, 0.25, 0.1]))).toBe("right");
  });
  it("ignores small, jittery, too fast, too slow or too weak movement", () => {
    expect(detectSwipe(run([0.4, 0.45, 0.4, 0.45, 0.42, 0.44]))).toBeNull();
    expect(detectSwipe(run([0.1, 0.8, 0.2, 0.9, 0.1, 0.8]))).toBeNull();           // back and forth
    expect(detectSwipe(run([0.1, 0.3, 0.5, 0.7, 0.9], 5))).toBeNull();               // far too fast
    expect(detectSwipe(run([0.1, 0.3, 0.5, 0.7, 0.9], 400))).toBeNull();             // far too slow
    expect(detectSwipe(run([0.1, 0.25, 0.4, 0.55, 0.7, 0.85], 80, 0.001))).toBeNull(); // almost no movement in the picture
    expect(detectSwipe(run([0.1, 0.5]))).toBeNull();                                 // too few samples
  });
  it("finds where the movement is in a frame", () => {
    const a = new Array(W * 24).fill(0), b = a.slice();
    for (let y = 0; y < 24; y++) for (let x = 24; x < 28; x++) b[y * W + x] = 255;
    const m = motionCentroid(a, b);
    expect(m.mass).toBeGreaterThan(0.1); expect(m.x).toBeGreaterThan(0.7); expect(motionCentroid(a, a)).toEqual({ mass: 0, x: null });
  });
  it("gestures may only navigate", () => expect(SAFE_ACTIONS).toEqual(["navigate"]));
});

describe("camera permission flow", () => {
  let stop, getUserMedia;
  beforeEach(() => {
    stop = vi.fn();
    getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] });
    Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
    window.HTMLMediaElement.prototype.play = () => Promise.resolve();
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); });
  const ui = () => render(<GestureProvider onSwipe={() => {}}><CameraIndicator /><GesturePanel /></GestureProvider>);

  it("never touches the camera until the person switches it on", () => {
    ui();
    expect(getUserMedia).not.toHaveBeenCalled(); expect(screen.queryByText("Camera on")).toBeNull();
    expect(screen.getByRole("switch", { name: "Enable gesture controls" }).getAttribute("aria-checked")).toBe("false");
  });
  it("asks for video only, shows a visible camera indicator, and Stop turns the camera off", async () => {
    ui();
    fireEvent.click(screen.getByRole("switch", { name: "Enable gesture controls" }));
    expect(await screen.findByText("Camera on")).toBeTruthy();
    expect(getUserMedia).toHaveBeenCalledWith(expect.objectContaining({ audio: false }));
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    await waitFor(() => expect(screen.queryByText("Camera on")).toBeNull());
    expect(stop).toHaveBeenCalled(); // the camera tracks were really stopped
  });
  it("the switch itself also turns it off", async () => {
    ui();
    const sw = screen.getByRole("switch", { name: "Enable gesture controls" });
    fireEvent.click(sw); await screen.findByText("Camera on");
    fireEvent.click(sw);
    await waitFor(() => expect(screen.queryByText("Camera on")).toBeNull()); expect(stop).toHaveBeenCalled();
  });
  it("a denied permission leaves gestures off and says how to carry on", async () => {
    getUserMedia.mockRejectedValue(Object.assign(new Error("no"), { name: "NotAllowedError" }));
    ui();
    fireEvent.click(screen.getByRole("switch", { name: "Enable gesture controls" }));
    expect(await screen.findByText(/Camera permission was not given/)).toBeTruthy();
    expect(screen.queryByText("Camera on")).toBeNull(); expect(screen.getByRole("switch", { name: "Enable gesture controls" }).getAttribute("aria-checked")).toBe("false");
  });
  it("a browser without camera support is handled", async () => {
    Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true });
    ui();
    fireEvent.click(screen.getByRole("switch", { name: "Enable gesture controls" }));
    expect(await screen.findByText(/cannot use a camera/)).toBeTruthy();
  });
  it("face gestures are shown as not available and cannot be switched on", () => {
    ui();
    expect(screen.getByRole("switch", { name: "Face gestures" }).disabled).toBe(true);
    expect(screen.getByRole("switch", { name: "Hand swipe" }).disabled).toBe(true);
  });
  it("the guide explains privacy and safety", async () => {
    ui();
    fireEvent.click(screen.getByRole("button", { name: "How to use gestures" }));
    expect(await screen.findByText(/never recorded, stored or sent anywhere/)).toBeTruthy(); expect(screen.getByText(/can never publish, approve, delete, pay or change permissions/)).toBeTruthy();
  });
});
