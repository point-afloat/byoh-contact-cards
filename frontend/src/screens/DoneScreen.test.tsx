import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SessionOut } from "@/api/types";
import { strings } from "@/strings";
import { expectNoAccessibilityViolations } from "@/test/axe";
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

const PAYLOAD = {
  person: {
    last_name: "Meier",
    first_name: "Anna",
    fb_custom_fields: [{ id: 16786, value: "Sync" }],
  },
  emails: [{ fb_person_id: 900004, email: "anna@acme.org", type: "work", is_main: true }],
};
const demo = () => sent({ person_id: "900004", demo_payload: PAYLOAD });

test("in mock mode it says nothing was sent and that this was a demo record", () => {
  render(<DoneScreen session={demo()} onNext={() => {}} />);
  expect(screen.getByRole("heading", { name: strings.done.mockHeading })).toHaveFocus();
  expect(screen.getByRole("status")).toHaveTextContent(
    "This contact was not sent to FundraisingBox. It was a demo record (ID 900004).",
  );
  expect(screen.queryByText(strings.done.heading)).not.toBeInTheDocument();
  expect(screen.queryByText(/was created/)).not.toBeInTheDocument();
});

test("in mock mode the data that would have been sent can be opened and read", async () => {
  render(<DoneScreen session={demo()} onNext={() => {}} />);
  const details = screen.getByText(strings.done.mockPayloadSummary).closest("details");
  expect(details).not.toHaveAttribute("open"); // closed until asked for
  await userEvent.click(screen.getByText(strings.done.mockPayloadSummary));
  expect(details).toHaveAttribute("open");
  const text = details?.querySelector("pre")?.textContent ?? "";
  expect(JSON.parse(text)).toEqual(PAYLOAD);
  expect(text).toContain("16786");
  expect(text).toContain('"email": "anna@acme.org"');
});

test("in live mode there is no payload and no extra text", () => {
  render(<DoneScreen session={sent()} onNext={() => {}} />);
  expect(screen.queryByText(strings.done.mockPayloadSummary)).not.toBeInTheDocument();
  expect(screen.queryByText(/demo record|not sent/i)).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: strings.done.heading })).toBeInTheDocument();
  expect(document.querySelector("details")).toBeNull();
});

test("the mock done screen, with the payload open, has no accessibility violations", async () => {
  render(<DoneScreen session={demo()} onNext={() => {}} />);
  await userEvent.click(screen.getByText(strings.done.mockPayloadSummary));
  await expectNoAccessibilityViolations();
});
