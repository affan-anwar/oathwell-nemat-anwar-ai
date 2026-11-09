import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, errorMessage, getToken, qs, setToken } from "../api.js";

// These tests use a MOCKED fetch. They prove client behaviour only, not the real server.
const reply = (status, body) => vi.fn().mockResolvedValue({ status, ok: status < 400, json: async () => body });
beforeEach(() => sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the bearer token", async () => {
    setToken("abc");
    const f = reply(200, { ok: 1 });
    vi.stubGlobal("fetch", f);
    await api("/x");
    expect(f.mock.calls[0][1].headers.Authorization).toBe("Bearer abc");
  });
  it("clears the token and signals logout on 401", async () => {
    setToken("abc");
    const heard = vi.fn();
    window.addEventListener("na-logout", heard);
    vi.stubGlobal("fetch", reply(401, { detail: "Not authenticated" }));
    await expect(api("/x")).rejects.toThrow("Not authenticated");
    expect(getToken()).toBeNull();
    expect(heard).toHaveBeenCalled();
  });
  it("turns validation errors into readable text", () => {
    expect(errorMessage({ detail: [{ loc: ["body", "name"], msg: "Field required" }] }, 422)).toBe("name: Field required");
    expect(errorMessage(null, 500)).toMatch(/Server error/);
  });
  it("reports an unreachable server honestly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    const e = await api("/x").catch((x) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(e.message).toMatch(/Cannot reach the server/);
  });
  it("builds query strings without empty values", () => {
    expect(qs({ a: 1, b: "", c: null, d: "x y" })).toBe("?a=1&d=x+y");
    expect(qs({})).toBe("");
  });
});
