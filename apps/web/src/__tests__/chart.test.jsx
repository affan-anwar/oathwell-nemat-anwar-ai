import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import Chart from "../Chart.jsx";

afterEach(cleanup);
describe("Chart", () => {
  const data = [{ date: "2026-10-01", a: 0, b: 2 }, { date: "2026-10-02", a: 3, b: 1 }];
  it("draws the supplied values and offers them as a table for screen readers", () => {
    render(<Chart data={data} label="Test chart" lines={[{ key: "a", label: "A", color: "red" }, { key: "b", label: "B", color: "blue" }]} />);
    expect(screen.getByRole("img", { name: "Test chart" })).toBeTruthy();
    expect(screen.getAllByRole("row")).toHaveLength(3);
    expect(screen.getAllByText("3").length).toBeGreaterThan(0);
  });
  it("handles an all-zero period and a single day without crashing", () => {
    render(<Chart data={[{ date: "2026-10-01", a: 0 }]} label="Empty" lines={[{ key: "a", label: "A", color: "red" }]} />);
    expect(screen.getByRole("img", { name: "Empty" })).toBeTruthy();
  });
});
