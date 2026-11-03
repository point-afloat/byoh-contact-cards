import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import App from "@/App";
import { strings } from "@/strings";
import { adminUser } from "@/test/setup";
import { server } from "@/test/server";

const member = { id: 2, email: "member@example.org", role: "member" };
const notSignedIn = () =>
  HttpResponse.json({ code: "not_authenticated", message: "Please sign in." }, { status: 401 });

test("someone who is not signed in is sent to the sign-in page and sees nothing else", async () => {
  server.use(http.get("*/api/auth/me", notSignedIn));
  render(<App />);

  expect(await screen.findByRole("heading", { name: strings.auth.signInHeading })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/login");
  expect(screen.queryByRole("heading", { name: strings.upload.heading })).not.toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: strings.nav.mainLabel })).not.toBeInTheDocument();
});

test("no data is requested before the user is known", async () => {
  const requests: string[] = [];
  server.use(
    http.get("*/api/auth/me", notSignedIn),
    http.all("*/api/*", ({ request }) => {
      requests.push(new URL(request.url).pathname);
      return HttpResponse.json({});
    }),
  );
  render(<App />);
  await screen.findByRole("heading", { name: strings.auth.signInHeading });
  expect(requests).toEqual([]);
});

test("a signed-in user sees the scan page with their address and the navigation", async () => {
  render(<App />);
  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/");
  expect(screen.getByText(adminUser.email)).toBeInTheDocument();
  const nav = screen.getByRole("navigation", { name: strings.nav.mainLabel });
  expect(nav).toHaveTextContent(strings.nav.scan);
  expect(nav).toHaveTextContent(strings.nav.account);
});

test("a loading state shows while the session is being checked", async () => {
  server.use(
    http.get("*/api/auth/me", async () => {
      await delay(80);
      return HttpResponse.json(adminUser);
    }),
  );
  render(<App />);
  expect(screen.getByRole("status")).toHaveTextContent(strings.auth.loading);
  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
});

test("opening the sign-in page while signed in goes to the app", async () => {
  window.history.replaceState(null, "", "/login");
  render(<App />);
  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  await waitFor(() => expect(window.location.pathname).toBe("/"));
});

test("signing out ends the session and shows the sign-in page", async () => {
  let loggedOut = false;
  server.use(
    http.post("*/api/auth/logout", () => {
      loggedOut = true;
      return HttpResponse.json({ status: "ok" });
    }),
    // like a real server: once logged out, nobody is signed in any more
    http.get("*/api/auth/me", () => (loggedOut ? notSignedIn() : HttpResponse.json(adminUser))),
  );
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: strings.nav.signOut }));

  expect(await screen.findByRole("heading", { name: strings.auth.signInHeading })).toBeInTheDocument();
  expect(loggedOut).toBe(true);
  expect(window.location.pathname).toBe("/login");
});

test("signing out still signs the person out in the app when the server is unreachable", async () => {
  let unreachable = false;
  server.use(
    http.post("*/api/auth/logout", () => {
      unreachable = true;
      return HttpResponse.error();
    }),
    http.get("*/api/auth/me", () => (unreachable ? HttpResponse.error() : HttpResponse.json(adminUser))),
  );
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: strings.nav.signOut }));
  expect(await screen.findByRole("heading", { name: strings.auth.signInHeading })).toBeInTheDocument();
});

test("administrators see the Users link, members do not", async () => {
  const { unmount } = render(<App />);
  expect(await screen.findByRole("link", { name: strings.nav.users })).toHaveAttribute("href", "/admin/users");
  unmount();

  server.use(http.get("*/api/auth/me", () => HttpResponse.json(member)));
  render(<App />);
  await screen.findByRole("link", { name: strings.nav.account });
  expect(screen.queryByRole("link", { name: strings.nav.users })).not.toBeInTheDocument();
});

test("a session the server ended keeps the page and asks for the password in a dialog", async () => {
  // signed in at first; then an upload is answered with "not authenticated"
  server.use(
    http.post("*/api/sessions", () =>
      HttpResponse.json({ code: "not_authenticated", message: "Please sign in." }, { status: 401 }),
    ),
  );
  render(<App />);
  const file = new File(["jpeg"], "card.jpg", { type: "image/jpeg" });
  await userEvent.upload(await screen.findByLabelText(strings.upload.chooseFile, { selector: "input" }), file);

  const dialog = await screen.findByRole("dialog", { name: strings.auth.expiredHeading });
  expect(dialog).toHaveTextContent(strings.auth.expiredText);
  // the page underneath is still there, not replaced by the sign-in page
  expect(screen.getByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/");
});

test("signing out leaves no data of the previous user in the app", async () => {
  let loggedOut = false;
  server.use(
    http.post("*/api/auth/logout", () => {
      loggedOut = true;
      return HttpResponse.json({ status: "ok" });
    }),
    http.get("*/api/auth/me", () => (loggedOut ? notSignedIn() : HttpResponse.json(adminUser))),
  );
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: strings.nav.signOut }));
  await screen.findByRole("heading", { name: strings.auth.signInHeading });
  expect(screen.queryByText(adminUser.email)).not.toBeInTheDocument();
});
