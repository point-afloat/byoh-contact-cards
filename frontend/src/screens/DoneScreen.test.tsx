import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SessionOut } from "@/api/types";
import { strings } from "@/strings";
import { DoneScreen } from "./DoneScreen";

const sent = (overrides: Partial<SessionOut> = {}): SessionOut => ({
  id: "abc",
  contact: null,
  warnings: [],
  sent: true,
  person_id: "733",
  record_type: "person",
  errors: {},
  ...overrides,
});

test("confirms the send with the created person's identifier and moves focus to the heading", () => {
  render(<DoneScreen session={sent()} onNext={() => {}} />);
  expect(screen.getByRole("heading", { name: strings.done.heading })).toHaveFocus();
  expect(screen.getByRole("status")).toHaveTextContent("The person was created (ID 733).");
});

test("says company when only a company was created", () => {
  render(<DoneScreen session={sent({ record_type: "company", person_id: "90" })} onNext={() => {}} />);
  expect(screen.getByRole("status")).toHaveTextContent("The company was created (ID 90).");
});

test("offers to scan the next card", async () => {
  const onNext = vi.fn();
  render(<DoneScreen session={sent()} onNext={onNext} />);
  await userEvent.click(screen.getByRole("button", { name: strings.done.next }));
  expect(onNext).toHaveBeenCalledTimes(1);
});
