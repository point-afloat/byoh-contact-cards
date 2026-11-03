import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import type { Contact, SessionOut } from "@/api/types";
import { emptyContact } from "@/screens/fields";
import { strings } from "@/strings";
import { adminUser } from "@/test/setup";
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

test("a session that expired while reviewing sends the user back to scan with an explanation", async () => {
  const expired = {
    code: "session_expired",
    message: "This review session has expired. Please scan the card again.",
  };
  backend(review(), () => HttpResponse.json(expired, { status: 404 }));
  let loads = 0;
  server.use(
    http.get("*/api/sessions/abc", () =>
      ++loads === 1 ? HttpResponse.json(review()) : HttpResponse.json(expired, { status: 404 }),
    ),
  );
  render(<App />);

  await userEvent.click(await sendButton());

  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("scan the card again");
  expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent(strings.steps.upload);
});

// ---- the sign-in ends while someone is reviewing ----------------------------------------------
const notAuthenticated = () =>
  HttpResponse.json({ code: "not_authenticated", message: "Please sign in." }, { status: 401 });

/** Signed in until the first send is rejected with a 401; signing in again restores access. */
function expiringBackend() {
  let signedIn = true;
  const bodies = backend(review(), (_body, call) => {
    if (call === 1) {
      signedIn = false;
      return notAuthenticated();
    }
    return HttpResponse.json(sent);
  });
  server.use(
    http.get("*/api/auth/me", () => (signedIn ? HttpResponse.json(adminUser) : notAuthenticated())),
    http.post("*/api/auth/login", () => {
      signedIn = true;
      return HttpResponse.json(adminUser);
    }),
  );
  return bodies;
}

async function signInAgain() {
  const dialog = await screen.findByRole("dialog", { name: strings.auth.expiredHeading });
  await userEvent.type(within(dialog).getByLabelText(strings.auth.email), "admin@example.org");
  await userEvent.type(within(dialog).getByLabelText(strings.auth.password), "my admin password");
  await userEvent.click(within(dialog).getByRole("button", { name: strings.auth.signIn }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
}

test("when the sign-in ends while sending, a dialog asks to sign in again and keeps what was typed", async () => {
  const bodies = expiringBackend();
  render(<App />);
  await userEvent.type(await screen.findByLabelText(strings.fields.phone), "+49 30 1234");
  await userEvent.click(await sendButton());

  const dialog = await screen.findByRole("dialog", { name: strings.auth.expiredHeading });
  expect(dialog).toHaveTextContent(strings.auth.expiredText);
  // the form is still there underneath, with the typed value, and shows no stale error
  expect(screen.getByLabelText(strings.fields.phone)).toHaveValue("+49 30 1234");
  expect(screen.getByLabelText(strings.fields.last_name)).toHaveValue("Meier");
  expect(screen.queryByText(strings.send.failed)).not.toBeInTheDocument();
  expect(window.location.pathname).toBe("/");

  await signInAgain();
  expect(screen.getByLabelText(strings.fields.phone)).toHaveValue("+49 30 1234"); // still kept

  await userEvent.click(await sendButton()); // the person sends again
  expect(await screen.findByRole("heading", { name: strings.done.heading })).toBeInTheDocument();
  expect(bodies).toHaveLength(2);
  expect(bodies[1].contact.phone).toBe("+49 30 1234");
});

test("a failed sign-in inside the dialog shows the reason and keeps the dialog and the form", async () => {
  expiringBackend();
  server.use(
    http.post("*/api/auth/login", () =>
      HttpResponse.json({ code: "invalid_credentials", message: "Email or password incorrect." }, { status: 401 }),
    ),
  );
  render(<App />);
  await userEvent.type(await screen.findByLabelText(strings.fields.phone), "+49 30 1234");
  await userEvent.click(await sendButton());

  const dialog = await screen.findByRole("dialog", { name: strings.auth.expiredHeading });
  await userEvent.type(within(dialog).getByLabelText(strings.auth.email), "admin@example.org");
  await userEvent.type(within(dialog).getByLabelText(strings.auth.password), "wrong password");
  await userEvent.click(within(dialog).getByRole("button", { name: strings.auth.signIn }));

  expect(await within(dialog).findByRole("alert")).toHaveTextContent("Email or password incorrect.");
  expect(screen.getByRole("dialog", { name: strings.auth.expiredHeading })).toBeInTheDocument();
  expect(screen.getByLabelText(strings.fields.phone)).toHaveValue("+49 30 1234");
});

test("when the draft cannot be saved because the sign-in ended, the same dialog appears", async () => {
  let signedIn = true;
  backend(review(), () => HttpResponse.json(sent));
  server.use(
    http.put("*/api/sessions/abc", () => {
      signedIn = false;
      return notAuthenticated();
    }),
    http.get("*/api/auth/me", () => (signedIn ? HttpResponse.json(adminUser) : notAuthenticated())),
  );
  render(<App />);
  await userEvent.type(await screen.findByLabelText(strings.fields.phone), "555");
  await userEvent.tab(); // leaving the field saves the draft
  expect(await screen.findByRole("dialog", { name: strings.auth.expiredHeading })).toBeInTheDocument();
  expect(screen.getByLabelText(strings.fields.phone)).toHaveValue("555");
});

test("the review page is not replaced by the scan page when reloading the review session answers 401", async () => {
  // "already sent" makes the app reload the review session; that reload is rejected because the
  // sign-in ended meanwhile. Without the guard the form would be thrown away for the scan page.
  let signedIn = true;
  let loads = 0;
  backend(review(), () =>
    HttpResponse.json({ code: "already_sent", message: "This contact was already sent." }, { status: 409 }),
  );
  server.use(
    http.get("*/api/sessions/abc", () => {
      loads += 1;
      if (loads === 1) return HttpResponse.json(review());
      signedIn = false;
      return notAuthenticated();
    }),
    http.get("*/api/auth/me", () => (signedIn ? HttpResponse.json(adminUser) : notAuthenticated())),
  );
  render(<App />);
  await userEvent.type(await screen.findByLabelText(strings.fields.phone), "777");
  await userEvent.click(await sendButton());

  await screen.findByRole("dialog", { name: strings.auth.expiredHeading });
  expect(loads).toBeGreaterThanOrEqual(2); // the reload really happened and was rejected
  expect(screen.queryByRole("heading", { name: strings.upload.heading })).not.toBeInTheDocument();
  expect(screen.getByLabelText(strings.fields.phone)).toHaveValue("777");
});
