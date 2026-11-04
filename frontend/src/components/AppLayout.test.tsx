import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import App from "@/App";
import { strings } from "@/strings";
import { server } from "@/test/server";
import { expectNoAccessibilityViolations } from "@/test/axe";

const mode = (fundraisingbox_mode: "live" | "mock") =>
  server.use(http.get("*/api/app-info", () => HttpResponse.json({ fundraisingbox_mode })));

const banner = () => screen.queryByText(strings.mock.banner);

test.each([
  ["scan", "/"],
  ["account", "/account"],
  ["users", "/admin/users"],
])("in mock mode the %s page shows the notice", async (_name, path) => {
  mode("mock");
  window.history.replaceState(null, "", path);
  render(<App />);
  expect(await screen.findByText(strings.mock.banner)).toBeInTheDocument();
});

test("in live mode there is no notice anywhere", async () => {
  mode("live");
  render(<App />);
  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  expect(banner()).not.toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/mock/i);
});

test("the notice does not appear before the sign-in is known or on the sign-in page", async () => {
  mode("mock");
  server.use(
    http.get("*/api/auth/me", () =>
      HttpResponse.json({ code: "not_authenticated", message: "Please sign in." }, { status: 401 }),
    ),
  );
  render(<App />);
  await screen.findByRole("heading", { name: strings.auth.signInHeading });
  expect(banner()).not.toBeInTheDocument();
});

test("if the server cannot say which mode it is in, no notice is shown and the page still works", async () => {
  server.use(http.get("*/api/app-info", () => HttpResponse.json({ code: "x" }, { status: 500 })));
  render(<App />);
  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  expect(banner()).not.toBeInTheDocument();
});

test("the page with the notice has no accessibility violations", async () => {
  mode("mock");
  render(<App />);
  await screen.findByText(strings.mock.banner);
  await expectNoAccessibilityViolations();
});
