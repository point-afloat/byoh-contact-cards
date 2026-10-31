import { render, screen } from "@testing-library/react";
import { StepIndicator } from "./StepIndicator";

test("shows the three steps in order with the active one marked", () => {
  render(<StepIndicator current="review" />);
  const items = screen.getAllByRole("listitem");
  expect(items.map((i) => i.textContent?.replace(/[✓\d]|\(completed\)/g, "").trim())).toEqual([
    "Scan",
    "Review",
    "Done",
  ]);
  expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Review");
  expect(items[0]).toHaveAttribute("data-state", "complete");
  expect(items[2]).toHaveAttribute("data-state", "upcoming");
});

test("completed steps are announced to screen readers, not only by colour", () => {
  render(<StepIndicator current="done" />);
  expect(screen.getAllByText("(completed)")).toHaveLength(2);
});
