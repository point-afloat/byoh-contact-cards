import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import App from "@/App";
import { api } from "@/api/client";
import type { Contact, SessionOut } from "@/api/types";
import { strings } from "@/strings";
import { server } from "@/test/server";
import { emptyContact } from "./fields";
import { ReviewScreen } from "./ReviewScreen";

const contact = (overrides: Partial<Contact> = {}): Contact => ({
  ...emptyContact(),
  first_name: "Anna",
  last_name: "Meier",
  company: "Acme GmbH",
  email: "anna@acme.org",
  ...overrides,
});
const session = (overrides: Partial<SessionOut> = {}): SessionOut => ({
  id: "abc123",
  contact: contact(),
  warnings: [],
  sent: false,
  errors: {},
  ...overrides,
});

function renderScreen(s: SessionOut, onConfirm?: (c: Contact) => void) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <ReviewScreen session={s} onConfirm={onConfirm} />
    </QueryClientProvider>,
  );
}

// The prefilled company triggers a search; most tests are not about it.
beforeEach(() => server.use(http.get("*/api/companies", () => HttpResponse.json([]))));
afterEach(() => vi.restoreAllMocks());

test("shows the card image next to a form pre-filled with every extracted field, all editable", async () => {
  renderScreen(session());
  expect(screen.getByRole("img", { name: strings.review.imageAlt })).toHaveAttribute(
    "src",
    "/api/sessions/abc123/image",
  );
  expect(screen.getByLabelText(strings.fields.first_name)).toHaveValue("Anna");
  expect(screen.getByLabelText(strings.fields.company)).toHaveValue("Acme GmbH");
  // every contact field has a labelled control
  for (const label of Object.values(strings.fields)) {
    expect(screen.getByLabelText(label)).toBeEnabled();
  }
  await userEvent.clear(screen.getByLabelText(strings.fields.first_name));
  await userEvent.type(screen.getByLabelText(strings.fields.first_name), "Berta");
  expect(screen.getByLabelText(strings.fields.first_name)).toHaveValue("Berta");
});

test("fields that were not found are marked with text, not only colour, and filled ones are not", () => {
  renderScreen(session());
  const phone = screen.getByLabelText(strings.fields.phone);
  const hint = within(phone.parentElement as HTMLElement).getByText(strings.review.notFound);
  expect(phone).toHaveAttribute("aria-describedby", expect.stringContaining(hint.id));

  const first = screen.getByLabelText(strings.fields.first_name).parentElement as HTMLElement;
  expect(within(first).queryByText(strings.review.notFound)).not.toBeInTheDocument();
});

test("the not-found hint disappears once the user fills the field in", async () => {
  renderScreen(session());
  const phone = screen.getByLabelText(strings.fields.phone);
  await userEvent.type(phone, "123");
  expect(
    within(phone.parentElement as HTMLElement).queryByText(strings.review.notFound),
  ).not.toBeInTheDocument();
});

test("extraction warnings are shown to the user", () => {
  renderScreen(session({ warnings: ["Some values could not be read reliably."] }));
  expect(screen.getByText(/could not be read reliably/)).toBeInTheDocument();
});

test("missing last name and company blocks confirmation and focuses the first invalid field", async () => {
  const onConfirm = vi.fn();
  renderScreen(session({ contact: contact({ last_name: "", company: "" }) }), onConfirm);
  await userEvent.click(screen.getByRole("button", { name: strings.review.send }));

  expect(onConfirm).not.toHaveBeenCalled();
  const lastName = screen.getByLabelText(strings.fields.last_name);
  await waitFor(() => expect(lastName).toHaveFocus());
  expect(lastName).toHaveAttribute("aria-invalid", "true");
  const errors = screen.getAllByRole("alert");
  expect(errors).toHaveLength(2); // last name and company
  expect(errors[0]).toHaveTextContent(strings.review.errors.identity);
  expect(lastName).toHaveAttribute("aria-describedby", expect.stringContaining(errors[0].id));
});

test("an invalid email blocks confirmation and the error is tied to the field", async () => {
  const onConfirm = vi.fn();
  renderScreen(session({ contact: contact({ email: "not-an-email" }) }), onConfirm);
  await userEvent.click(screen.getByRole("button", { name: strings.review.send }));

  const email = screen.getByLabelText(strings.fields.email);
  await waitFor(() => expect(email).toHaveFocus());
  expect(email).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByRole("alert")).toHaveTextContent(strings.review.errors.email);
  expect(onConfirm).not.toHaveBeenCalled();
});

test("a valid form calls onConfirm with the edited values", async () => {
  const onConfirm = vi.fn();
  renderScreen(session(), onConfirm);
  await userEvent.type(screen.getByLabelText(strings.fields.phone), "+49 30 1234");
  await userEvent.click(screen.getByRole("button", { name: strings.review.send }));
  await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
  expect(onConfirm.mock.calls[0][0]).toMatchObject({ last_name: "Meier", phone: "+49 30 1234" });
});

test("no confirm button is shown until a confirm handler exists", () => {
  renderScreen(session());
  expect(screen.queryByRole("button", { name: strings.review.send })).not.toBeInTheDocument();
});

test("leaving a field saves the draft so a reload restores it", async () => {
  const saveContact = vi.spyOn(api, "saveContact").mockResolvedValue(session());
  renderScreen(session());
  await userEvent.type(screen.getByLabelText(strings.fields.phone), "555");
  await userEvent.tab();
  await waitFor(() => expect(saveContact).toHaveBeenCalled());
  const [id, saved] = saveContact.mock.calls.at(-1) as [string, Contact];
  expect(id).toBe("abc123");
  expect(saved.phone).toBe("555");
});

test("reloading with the session id in the URL restores the review step with the card and values", async () => {
  window.history.replaceState(null, "", "/?session=abc123");
  server.use(
    http.get("*/api/sessions/abc123", () =>
      HttpResponse.json(session({ contact: contact({ phone: "+49 1" }) })),
    ),
  );
  render(<App />);
  expect(await screen.findByLabelText(strings.fields.phone)).toHaveValue("+49 1");
  expect(screen.getByRole("img", { name: strings.review.imageAlt })).toBeInTheDocument();
  expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent(strings.steps.review);
});

test("an expired session in the URL falls back to the scan step with an explanation", async () => {
  window.history.replaceState(null, "", "/?session=gone");
  server.use(
    http.get("*/api/sessions/gone", () =>
      HttpResponse.json(
        { code: "session_expired", message: "This review session has expired. Please scan the card again." },
        { status: 404 },
      ),
    ),
  );
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("scan the card again");
  expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent(strings.steps.upload);
});
