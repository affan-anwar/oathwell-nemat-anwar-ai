import { describe, expect, it } from "vitest";
import { hijriOf, monthCells, utc } from "../hijri.js";

describe("calendar arithmetic (real computation)", () => {
  it("finds Ramadan and Eid in 2026", () => {
    const feb = monthCells(2026, 1).find((c) => c?.occasion === "Ramadan begins");
    expect(feb.d).toBe(18);
    expect(monthCells(2026, 2).find((c) => c?.occasion === "Eid al-Fitr").d).toBe(20);
  });
  it("has no Hijri date before 622 CE", () => {
    expect(hijriOf(570, 3, 20)).toBeNull();
    expect(hijriOf(622, 6, 19)).toEqual({ d: 1, m: 1, y: 1 });
  });
  it("handles the full range and weekdays", () => {
    expect(utc(2026, 9, 15).getUTCDay()).toBe(4);
    expect(hijriOf(2099, 11, 31)).not.toBeNull();
    expect(monthCells(570, 0).filter(Boolean)).toHaveLength(31);
  });
});
