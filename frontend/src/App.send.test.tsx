import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import type { Contact, SessionOut } from "@/api/types";
import { emptyContact } from "@/screens/fields";
import { strings } from "@/strings";
import { server } from "@/test/server";
import App from "./App";

const contact = (overrides: Partial<Contact> = {}): Contact => ({
  ...emptyContact(),
  first_name: "Anna",
  last_name: "Meier",
  email: "anna@acme.org",
  ...overrides,
});
const review = (overrides: Partial<Contact> = {}): SessionOut => ({
  id: "abc",
  contact: contact(overrides),
  warnings: [],
  sent: false,
  errors: {},
});
const sent: SessionOut = {
  id: "abc",
  contact: null,
  warnings: [],
  sent: true,
  person_id: "733",
  record_type: "person",
  errors: {},
};

type SendBody = { contact: Contact; company: { mode: string; id?: number } };

/** Backend stub for a review session; `onSend` decides how each send is answered. */
function backend(
  session: SessionOut,
  onSend: (body: SendBody, call: number) => Response | Promise<Response>,
) {
  const bodies: SendBody[] = [];
  window.history.replaceState(null, "", "/?session=abc");
  server.use(
    http.get("*/api/sessions/abc", () => HttpResponse.json(session)),
    http.put("*/api/sessions/abc", () => HttpResponse.json(session)),
    http.get("*/api/companies", () => HttpResponse.json([{ id: 7, name: "Acme GmbH", city: "Berlin" }])),
    http.post("*/api/sessions/abc/send", async ({ request }) => {
      const body = (await request.json()) as SendBody;
      bodies.push(body);
      return onSend(body, bodies.length);
    }),
  );
  return bodies;
}

const sendButton = () => screen.findByRole("button", { name: strings.review.send });

test("sending shows the done screen with the created id, and the next card starts over", async () => {
  const bodies = backend(review(), () => HttpResponse.json(sent));
  render(<App />);

  await userEvent.click(await sendButton());

  expect(await screen.findByRole("heading", { name: strings.done.heading })).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("ID 733");
  expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent(strings.steps.done);
  expect(bodies).toHaveLength(1);
  expect(bodies[0].contact).toMatchObject({ first_name: "Anna", last_name: "Meier" });
  expect(bodies[0].company).toEqual({ mode: "none" });
  // the send action is gone once sent
  expect(screen.queryByRole("button", { name: strings.review.send })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: strings.done.next }));
  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  expect(window.location.search).toBe("");
});

test("an API error keeps the form, explains the failure, and a retry succeeds", async () => {
  const bodies = backend(review(), (_body, call) =>
    call === 1
      ? HttpResponse.json(
          { code: "fundraisingbox_rejected", message: "FundraisingBox returned an error (400)." },
          { status: 502 },
        )
      : HttpResponse.json(sent),
  );
  render(<App />);

  await userEvent.type(await screen.findByLabelText(strings.fields.phone), "+49 30 1234");
  await userEvent.click(await sendButton());

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent(strings.send.failed);
  expect(alert).toHaveTextContent("FundraisingBox returned an error (400).");
  expect(screen.getByLabelText(strings.fields.phone)).toHaveValue("+49 30 1234"); // entries kept
  expect(screen.getByLabelText(strings.fields.last_name)).toHaveValue("Meier");

  await userEvent.click(await sendButton());
  expect(await screen.findByRole("heading", { name: strings.done.heading })).toBeInTheDocument();
  expect(bodies).toHaveLength(2);
  expect(bodies[1].contact.phone).toBe("+49 30 1234");
});

test("a network failure is shown and can be retried without re-uploading", async () => {
  backend(review(), (_body, call) => (call === 1 ? HttpResponse.error() : HttpResponse.json(sent)));
  render(<App />);
  await userEvent.click(await sendButton());
  expect(await screen.findByRole("alert")).toHaveTextContent(strings.networkError);
  await userEvent.click(await sendButton());
  expect(await screen.findByRole("heading", { name: strings.done.heading })).toBeInTheDocument();
});

test("a double click sends only once and shows progress meanwhile", async () => {
  const bodies = backend(review(), async () => {
    await delay(150);
    return HttpResponse.json(sent);
  });
  render(<App />);

  await userEvent.dblClick(await sendButton());

  expect(await screen.findByText(strings.send.sending)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: strings.send.sending })).toBeDisabled();
  expect(await screen.findByRole("heading", { name: strings.done.heading })).toBeInTheDocument();
  expect(bodies).toHaveLength(1);
});

test("field problems reported by the server are shown on the fields", async () => {
  backend(review(), () =>
    HttpResponse.json(
      {
        code: "validation_error",
        message: "Please fix the highlighted fields.",
        errors: { email: "This is not a valid email address." },
      },
      { status: 422 },
    ),
  );
  render(<App />);
  await userEvent.click(await sendButton());

  const email = screen.getByLabelText(strings.fields.email);
  await waitFor(() => expect(email).toHaveAttribute("aria-invalid", "true"));
  expect(screen.getAllByRole("alert").map((a) => a.textContent).join(" ")).toContain(
    "This is not a valid email address.",
  );
});

test("the chosen company link is sent with the contact", async () => {
  const bodies = backend(review({ company: "Acme" }), () => HttpResponse.json(sent));
  render(<App />);

  await userEvent.click(await screen.findByLabelText(strings.company.link("Acme GmbH", "Berlin")));
  await userEvent.click(await sendButton());

  await screen.findByRole("heading", { name: strings.done.heading });
  expect(bodies[0].company).toEqual({ mode: "link", id: 7 });
});

test("creating a missing company is sent as the create choice", async () => {
  server.use(http.get("*/api/companies", () => HttpResponse.json([])));
  const bodies = backend(review({ company: "Brand New AG" }), () => HttpResponse.json(sent));
  server.use(http.get("*/api/companies", () => HttpResponse.json([])));
  render(<App />);

  await userEvent.click(await screen.findByLabelText(strings.company.create("Brand New AG")));
  await userEvent.click(await sendButton());

  await screen.findByRole("heading", { name: strings.done.heading });
  expect(bodies[0].company).toEqual({ mode: "create" });
});

test("reloading after a successful send shows the done screen and no send action", async () => {
  backend(sent, () => HttpResponse.json(sent));
  render(<App />);
  expect(await screen.findByRole("heading", { name: strings.done.heading })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: strings.review.send })).not.toBeInTheDocument();
});
