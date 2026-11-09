import { readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";

// theme-init.js runs before React so the page never flashes the wrong theme.
const code = readFileSync(join(process.cwd(), "public", "theme-init.js"), "utf8");
const run = (stored, lightSystem) => {
  localStorage.clear();
  if (stored) localStorage.setItem("na_theme", stored);
  window.matchMedia = () => ({ matches: lightSystem });
  document.documentElement.removeAttribute("data-theme");
  new Function(code)();
  return document.documentElement.getAttribute("data-theme");
};

describe("theme-init.js", () => {
  beforeEach(() => localStorage.clear());
  it("dark is the default, even when the system says light", () => { expect(run(null, false)).toBe("dark"); expect(run(null, true)).toBe("dark"); });
  it("a saved light or dark choice wins over the system", () => { expect(run("dark", true)).toBe("dark"); expect(run("light", false)).toBe("light"); });
  it("'system' follows the device", () => { expect(run("system", true)).toBe("light"); expect(run("system", false)).toBe("dark"); });
  it("ignores a corrupt saved value", () => expect(run("purple", true)).toBe("dark"));
});
