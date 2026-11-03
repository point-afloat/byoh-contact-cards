import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import App from "@/App";
import { strings } from "@/strings";
import { expectNoAccessibilityViolations } from "@/test/axe";
import { adminUser } from "@/test/setup";
import { server } from "@/test/server";

const GOOD = "a perfectly fine new password";

function openAccount() {
  window.history.replaceState(null, "", "/account");
  return render(<App />);
}

const current = () => screen.findByLabelText(strings.account.current);
const next = () => screen.getByLabelText(strings.account.next);
const confirm = () => screen.getByLabelText(strings.account.confirm);
const submit = () => screen.getByRole("button", { name: strings.account.submit });

function changePasswordRequests() {
  const bodies: Array<{ current_password: string; new_password: string }> = [];
  server.use(
    http.post("*/api/auth/change-password", async ({ request }) => {
      bodies.push((await request.json()) as (typeof bodies)[number]);
      return HttpResponse.json({ status: "ok" });
    }),
  );
  return bodies;
}

test("shows who is signed in and their role", async () => {
  openAccount();
  expect(await screen.findByRole("heading", { name: strings.account.heading })).toBeInTheDocument();
  expect(screen.getByText(adminUser.email, { selector: "dd" })).toBeInTheDocument();
  expect(screen.getByText(strings.account.roles.admin)).toBeInTheDocument();
});

test("a successful change is confirmed, announced and the fields are cleared", async () => {
  const bodies = changePasswordRequests();
  openAccount();
  await userEvent.type(await current(), "my old password!");
  await userEvent.type(next(), GOOD);
  await userEvent.type(confirm(), GOOD);
  await userEvent.click(submit());

  expect(await screen.findByRole("status")).toHaveTextContent(strings.account.success);
  expect(bodies).toEqual([{ current_password: "my old password!", new_password: GOOD }]);
  expect(screen.getByLabelText(strings.account.current)).toHaveValue("");
  expect(next()).toHaveValue("");
  expect(confirm()).toHaveValue("");
});

test("passwords that do not match are caught before anything is sent", async () => {
  const bodies = changePasswordRequests();
  openAccount();
  await userEvent.type(await current(), "my old password!");
  await userEvent.type(next(), GOOD);
  await userEvent.type(confirm(), GOOD + "x");
  await userEvent.click(submit());

  const error = await screen.findByRole("alert");
  expect(error).toHaveTextContent(strings.account.mismatch);
  expect(confirm()).toHaveFocus();
  expect(confirm()).toHaveAttribute("aria-invalid", "true");
  expect(confirm()).toHaveAttribute("aria-describedby", expect.stringContaining(error.id));
  expect(bodies).toHaveLength(0);
});

test("a too short new password is caught first and receives focus", async () => {
  const bodies = changePasswordRequests();
  openAccount();
  await userEvent.type(await current(), "my old password!");
  await userEvent.type(next(), "short");
  await userEvent.click(submit());

  expect(await screen.findByRole("alert")).toHaveTextContent(strings.account.tooShort);
  expect(next()).toHaveFocus();
  expect(bodies).toHaveLength(0);
});

test("the current password is required", async () => {
  openAccount();
  await userEvent.type(await screen.findByLabelText(strings.account.next), GOOD);
  await userEvent.type(confirm(), GOOD);
  await userEvent.click(submit());
  expect(await screen.findByRole("alert")).toHaveTextContent(strings.account.required);
  expect(await current()).toHaveFocus();
});

test("a wrong current password reported by the server is shown on that field", async () => {
  server.use(
    http.post("*/api/auth/change-password", () =>
      HttpResponse.json(
        {
          code: "wrong_password",
          message: "The current password is incorrect.",
          errors: { current_password: "The current password is incorrect." },
        },
        { status: 400 },
      ),
    ),
  );
  openAccount();
  await userEvent.type(await current(), "not my password");
  await userEvent.type(next(), GOOD);
  await userEvent.type(confirm(), GOOD);
  await userEvent.click(submit());

  expect(await screen.findByRole("alert")).toHaveTextContent("The current password is incorrect.");
  expect(await current()).toHaveFocus();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test("a password the server finds too weak is shown on the new password field", async () => {
  server.use(
    http.post("*/api/auth/change-password", () =>
      HttpResponse.json(
        {
          code: "validation_error",
          message: "This password is too easy to guess. Choose a different one.",
          errors: { new_password: "This password is too easy to guess. Choose a different one." },
        },
        { status: 422 },
      ),
    ),
  );
  openAccount();
  await userEvent.type(await current(), "my old password!");
  await userEvent.type(next(), "password12345");
  await userEvent.type(confirm(), "password12345");
  await userEvent.click(submit());
  expect(await screen.findByRole("alert")).toHaveTextContent("too easy to guess");
  expect(next()).toHaveFocus();
});

test("being throttled shows the try-again-later message for the form", async () => {
  server.use(
    http.post("*/api/auth/change-password", () =>
      HttpResponse.json(
        { code: "too_many_attempts", message: "Too many failed attempts. Please try again later." },
        { status: 429 },
      ),
    ),
  );
  openAccount();
  await userEvent.type(await current(), "my old password!");
  await userEvent.type(next(), GOOD);
  await userEvent.type(confirm(), GOOD);
  await userEvent.click(submit());
  expect(await screen.findByRole("alert")).toHaveTextContent("try again later");
});

test("the page has no accessibility violations, also while errors are shown", async () => {
  const { container } = openAccount();
  await current();
  await expectNoAccessibilityViolations(container);
  await userEvent.click(submit()); // empty form: every field reports a problem
  await screen.findAllByRole("alert");
  await expectNoAccessibilityViolations(container);
});

test("someone who is not signed in cannot open the account page", async () => {
  server.use(
    http.get("*/api/auth/me", () =>
      HttpResponse.json({ code: "not_authenticated", message: "Please sign in." }, { status: 401 }),
    ),
  );
  openAccount();
  expect(await screen.findByRole("heading", { name: strings.auth.signInHeading })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/login");
});
