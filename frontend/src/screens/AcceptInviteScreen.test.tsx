import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import App from "@/App";
import { strings } from "@/strings";
import { expectNoAccessibilityViolations } from "@/test/axe";
import { server } from "@/test/server";

const TOKEN = "a-long-random-token-1234567890-abcdefghijklmnop";
const GOOD = "the chosen long passphrase";
const joiner = { id: 2, email: "new@example.org", role: "member" };
const notSignedIn = () =>
  HttpResponse.json({ code: "not_authenticated", message: "Please sign in." }, { status: 401 });
const invalidLink = () =>
  HttpResponse.json(
    {
      code: "invite_invalid",
      message: "This link is no longer valid. Ask an administrator for a new one.",
    },
    { status: 400 },
  );

/** Someone who is not signed in opens an invitation link. */
function openLink(hash = `#token=${TOKEN}`, kind = "invite") {
  window.history.replaceState(null, "", `/accept-invite${hash}`);
  server.use(
    http.get("*/api/auth/me", notSignedIn),
    http.post("*/api/auth/invite-info", () => HttpResponse.json({ email: joiner.email, kind })),
  );
  return render(<App />);
}

const password = () => screen.findByLabelText(strings.invite.password);
const confirm = () => screen.getByLabelText(strings.invite.confirm);
const submit = (name: string = strings.invite.submitInvite) => screen.getByRole("button", { name });

test("a valid invitation asks for a password for that address, and signs the person in", async () => {
  let signedIn = false;
  const bodies: unknown[] = [];
  server.use(
    http.post("*/api/auth/accept-invite", async ({ request }) => {
      bodies.push(await request.json());
      signedIn = true;
      return HttpResponse.json(joiner);
    }),
  );
  openLink();
  server.use(http.get("*/api/auth/me", () => (signedIn ? HttpResponse.json(joiner) : notSignedIn())));

  expect(await screen.findByRole("heading", { name: strings.invite.welcomeHeading })).toBeInTheDocument();
  expect(screen.getByText(joiner.email)).toBeInTheDocument();
  await userEvent.type(await password(), GOOD);
  await userEvent.type(confirm(), GOOD);
  await userEvent.click(submit());

  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  expect(bodies).toEqual([{ token: TOKEN, password: GOOD }]);
  expect(window.location.pathname).toBe("/");
  expect(window.location.hash).toBe(""); // the token is gone from the address bar
});

test("a password-reset link has its own wording", async () => {
  openLink(`#token=${TOKEN}`, "reset");
  expect(await screen.findByRole("heading", { name: strings.invite.resetHeading })).toBeInTheDocument();
  expect(submit(strings.invite.submitReset)).toBeInTheDocument();
});

test("the token is sent in a request body, never in a URL", async () => {
  const urls: string[] = [];
  const record = ({ request }: { request: Request }) => urls.push(request.url);
  server.events.on("request:start", record);
  openLink();
  await password();
  server.events.removeListener("request:start", record);
  expect(urls.length).toBeGreaterThan(0);
  expect(urls.some((url) => url.includes(TOKEN))).toBe(false);
});

test("an invalid, used or expired link says so and points to an administrator", async () => {
  openLink();
  server.use(http.post("*/api/auth/invite-info", invalidLink));
  expect(await screen.findByRole("heading", { name: strings.invite.invalidHeading })).toBeInTheDocument();
  expect(screen.getByText(/Ask an administrator for a new one/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: strings.invite.toSignIn })).toHaveAttribute("href", "/login");
  expect(screen.queryByLabelText(strings.invite.password)).not.toBeInTheDocument();
});

test("a link without a token is invalid and no request is made", async () => {
  const requests: string[] = [];
  server.use(
    http.post("*/api/auth/invite-info", ({ request }) => {
      requests.push(request.url);
      return HttpResponse.json({ email: "x@y.org", kind: "invite" });
    }),
  );
  openLink("");
  expect(await screen.findByRole("heading", { name: strings.invite.invalidHeading })).toBeInTheDocument();
  expect(requests).toHaveLength(0);
});

test("the page works without signing in first", async () => {
  openLink();
  await password();
  expect(window.location.pathname).toBe("/accept-invite"); // not redirected to the sign-in page
});

test("a link that stops working while the form is open turns into the invalid message", async () => {
  server.use(http.post("*/api/auth/accept-invite", invalidLink));
  openLink();
  await userEvent.type(await password(), GOOD);
  await userEvent.type(confirm(), GOOD);
  await userEvent.click(submit());
  expect(await screen.findByRole("heading", { name: strings.invite.invalidHeading })).toBeInTheDocument();
});

test("a weak password is reported on the field and the form stays usable", async () => {
  server.use(
    http.post("*/api/auth/accept-invite", () =>
      HttpResponse.json(
        {
          code: "validation_error",
          message: "This password is too easy to guess. Choose a different one.",
          errors: { password: "This password is too easy to guess. Choose a different one." },
        },
        { status: 422 },
      ),
    ),
  );
  openLink();
  await userEvent.type(await password(), "password12345");
  await userEvent.type(confirm(), "password12345");
  await userEvent.click(submit());

  expect(await screen.findByRole("alert")).toHaveTextContent("too easy to guess");
  await waitFor(() => expect(screen.getByLabelText(strings.invite.password)).toHaveFocus());
  expect(screen.getByLabelText(strings.invite.password)).toHaveAttribute("aria-invalid", "true");
});

test("a too short password or a mismatch is caught before anything is sent", async () => {
  const bodies: unknown[] = [];
  server.use(
    http.post("*/api/auth/accept-invite", async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(joiner);
    }),
  );
  openLink();
  await userEvent.type(await password(), "short");
  await userEvent.click(submit());
  expect(await screen.findByRole("alert")).toHaveTextContent(strings.invite.tooShort);
  expect(screen.getByLabelText(strings.invite.password)).toHaveFocus();

  await userEvent.clear(screen.getByLabelText(strings.invite.password));
  await userEvent.type(screen.getByLabelText(strings.invite.password), GOOD);
  await userEvent.type(confirm(), GOOD + "!");
  await userEvent.click(submit());
  expect(await screen.findByText(strings.invite.mismatch)).toBeInTheDocument();
  expect(confirm()).toHaveFocus();
  expect(bodies).toHaveLength(0);
});

test("when the server cannot be asked, the page offers to try again", async () => {
  let calls = 0;
  window.history.replaceState(null, "", `/accept-invite#token=${TOKEN}`);
  server.use(
    http.get("*/api/auth/me", notSignedIn),
    http.post("*/api/auth/invite-info", () => {
      calls += 1;
      return calls === 1 ? HttpResponse.error() : HttpResponse.json({ email: joiner.email, kind: "invite" });
    }),
  );
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent(strings.networkError);
  await userEvent.click(screen.getByRole("button", { name: strings.invite.retry }));
  expect(await screen.findByRole("heading", { name: strings.invite.welcomeHeading })).toBeInTheDocument();
});

test("the ready and the invalid states have no accessibility violations", async () => {
  const ready = openLink();
  await password();
  await expectNoAccessibilityViolations(ready.container);
  ready.unmount();

  window.history.replaceState(null, "", `/accept-invite#token=${TOKEN}`);
  server.use(http.get("*/api/auth/me", notSignedIn), http.post("*/api/auth/invite-info", invalidLink));
  const invalid = render(<App />);
  await screen.findByRole("heading", { name: strings.invite.invalidHeading });
  await expectNoAccessibilityViolations(invalid.container);
});
