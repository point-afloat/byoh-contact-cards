import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import App from "@/App";
import { strings } from "@/strings";
import { expectNoAccessibilityViolations } from "@/test/axe";
import { adminUser } from "@/test/setup";
import { server } from "@/test/server";

const notSignedIn = () =>
  HttpResponse.json({ code: "not_authenticated", message: "Please sign in." }, { status: 401 });
const wrongCredentials = () =>
  HttpResponse.json(
    { code: "invalid_credentials", message: "Email or password incorrect." },
    { status: 401 },
  );

function openLoginPage() {
  server.use(http.get("*/api/auth/me", notSignedIn));
  window.history.replaceState(null, "", "/login");
  return render(<App />);
}

const emailField = () => screen.findByLabelText(strings.auth.email);
const passwordField = () => screen.getByLabelText(strings.auth.password);
const submit = () => screen.getByRole("button", { name: strings.auth.signIn });

async function fillAndSubmit(email = "admin@example.org", password = "some long password") {
  await userEvent.type(await emailField(), email);
  await userEvent.type(passwordField(), password);
  await userEvent.click(submit());
}

test("the form has labelled fields and no accessibility violations", async () => {
  const { container } = openLoginPage();
  await emailField();
  expect(screen.getByLabelText(strings.auth.email)).toHaveAttribute("autocomplete", "username");
  expect(passwordField()).toHaveAttribute("autocomplete", "current-password");
  await expectNoAccessibilityViolations(container);
});

test("wrong credentials give one generic message, clear the password and refocus it", async () => {
  server.use(http.post("*/api/auth/login", wrongCredentials));
  openLoginPage();
  await fillAndSubmit("someone@example.org", "not the password");

  expect(await screen.findByRole("alert")).toHaveTextContent("Email or password incorrect.");
  expect(passwordField()).toHaveValue("");
  expect(passwordField()).toHaveFocus();
  expect(screen.getByLabelText(strings.auth.email)).toHaveValue("someone@example.org"); // kept
});

test("the message is the same for an unknown email and a wrong password", async () => {
  server.use(http.post("*/api/auth/login", wrongCredentials));
  openLoginPage();
  await fillAndSubmit("ghost@example.org", "x".repeat(14));
  const first = (await screen.findByRole("alert")).textContent;
  await userEvent.type(passwordField(), "another wrong password");
  await userEvent.click(submit());
  await waitFor(() => expect(screen.getByRole("alert").textContent).toBe(first));
});

test("too many attempts shows the server's try-again-later message", async () => {
  server.use(
    http.post("*/api/auth/login", () =>
      HttpResponse.json(
        { code: "too_many_attempts", message: "Too many failed attempts. Please try again later." },
        { status: 429 },
      ),
    ),
  );
  openLoginPage();
  await fillAndSubmit();
  expect(await screen.findByRole("alert")).toHaveTextContent("try again later");
});

test("an unreachable server is reported in words", async () => {
  server.use(http.post("*/api/auth/login", () => HttpResponse.error()));
  openLoginPage();
  await fillAndSubmit();
  expect(await screen.findByRole("alert")).toHaveTextContent(strings.networkError);
});

test("signing in takes the user to the app", async () => {
  let signedIn = false;
  server.use(
    http.post("*/api/auth/login", async ({ request }) => {
      const body = (await request.json()) as { email: string; password: string };
      expect(body).toEqual({ email: "admin@example.org", password: "some long password" });
      signedIn = true;
      return HttpResponse.json(adminUser);
    }),
    http.get("*/api/auth/me", () => (signedIn ? HttpResponse.json(adminUser) : notSignedIn())),
  );
  openLoginPage();
  await fillAndSubmit();

  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/");
});

test("while signing in the button shows progress and a double click sends one request", async () => {
  let requests = 0;
  server.use(
    http.post("*/api/auth/login", async () => {
      requests += 1;
      await delay(120);
      return HttpResponse.json(adminUser);
    }),
  );
  openLoginPage();
  await userEvent.type(await emailField(), "admin@example.org");
  await userEvent.type(passwordField(), "some long password");
  await userEvent.dblClick(submit());

  expect(await screen.findByRole("button", { name: strings.auth.signingIn })).toBeDisabled();
  await waitFor(() => expect(window.location.pathname).toBe("/"));
  expect(requests).toBe(1);
});

test("an error message does not introduce accessibility violations", async () => {
  server.use(http.post("*/api/auth/login", wrongCredentials));
  const { container } = openLoginPage();
  await fillAndSubmit();
  await screen.findByRole("alert");
  await expectNoAccessibilityViolations(container);
});
