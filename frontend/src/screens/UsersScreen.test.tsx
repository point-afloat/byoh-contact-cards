import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import App from "@/App";
import type { UserOut } from "@/api/types";
import { strings } from "@/strings";
import { expectNoAccessibilityViolations } from "@/test/axe";
import { adminUser } from "@/test/setup";
import { server } from "@/test/server";

const t = strings.users;
const day = 24 * 60 * 60 * 1000;
const iso = (offsetMs: number) => new Date(Date.now() + offsetMs).toISOString();

const user = (overrides: Partial<UserOut> & { id: number; email: string }): UserOut => ({
  role: "member",
  status: "active",
  created_at: iso(-30 * day),
  last_sign_in_at: iso(-day),
  invite_expires_at: null,
  ...overrides,
});

const START: UserOut[] = [
  user({ id: 1, email: adminUser.email, role: "admin" }),
  user({ id: 2, email: "member@example.org" }),
  user({ id: 3, email: "off@example.org", status: "inactive" }),
  user({ id: 4, email: "pending@example.org", status: "invited", last_sign_in_at: null, invite_expires_at: iso(3 * day) }),
  user({ id: 5, email: "lapsed@example.org", status: "invited", last_sign_in_at: null, invite_expires_at: iso(-2 * day) }),
];

type Call = { method: string; path: string; body?: unknown };

/** An in-memory stand-in for the admin API that enforces the same rules as the real one. */
function fakeBackend(initial: UserOut[] = START) {
  const users = initial.map((u) => ({ ...u }));
  const calls: Call[] = [];
  let nextId = 100;
  const find = (id: string) => users.find((u) => String(u.id) === id);
  const issued = (u: UserOut, kind: string) => ({
    user: u,
    token: `${kind}-token-${u.id}-${calls.length}`,
    invite_path: `/accept-invite#token=${kind}-token-${u.id}-${calls.length}`,
    expires_at: iso(kind === "reset" ? 60 * 60 * 1000 : 7 * day),
  });
  const notFound = () => HttpResponse.json({ code: "user_not_found", message: "User not found." }, { status: 404 });

  server.use(
    http.get("*/api/admin/users", () => {
      calls.push({ method: "GET", path: "/api/admin/users" });
      return HttpResponse.json(users);
    }),
    http.post("*/api/admin/users", async ({ request }) => {
      const body = (await request.json()) as { email: string; role: string };
      calls.push({ method: "POST", path: "/api/admin/users", body });
      const email = body.email.trim().toLowerCase();
      if (!email.includes("@")) {
        return HttpResponse.json(
          { code: "validation_error", message: "Please fix the highlighted fields.", errors: { email: "This is not a valid email address." } },
          { status: 422 },
        );
      }
      if (users.some((u) => u.email === email)) {
        return HttpResponse.json({ code: "user_exists", message: "A user with this email address already exists." }, { status: 409 });
      }
      const created = user({ id: nextId++, email, role: body.role, status: "invited", last_sign_in_at: null, invite_expires_at: iso(7 * day) });
      users.push(created);
      return HttpResponse.json(issued(created, "invite"), { status: 201 });
    }),
    http.patch("*/api/admin/users/:id", async ({ request, params }) => {
      const body = (await request.json()) as { role?: string; is_active?: boolean };
      calls.push({ method: "PATCH", path: `/api/admin/users/${params.id}`, body });
      const target = find(String(params.id));
      if (!target) return notFound();
      const activeAdmins = users.filter((u) => u.role === "admin" && u.status === "active");
      const losesAdmin = body.role === "member" || body.is_active === false;
      if (target.role === "admin" && target.status === "active" && losesAdmin && activeAdmins.length === 1) {
        return HttpResponse.json(
          { code: "last_admin", message: "At least one active administrator is needed. Make someone else an administrator first." },
          { status: 409 },
        );
      }
      if (body.role) target.role = body.role;
      if (body.is_active !== undefined) target.status = body.is_active ? "active" : "inactive";
      return HttpResponse.json(target);
    }),
    http.post("*/api/admin/users/:id/invite", ({ params }) => {
      calls.push({ method: "POST", path: `/api/admin/users/${params.id}/invite` });
      const target = find(String(params.id));
      return target ? HttpResponse.json(issued(target, "invite")) : notFound();
    }),
    http.delete("*/api/admin/users/:id/invite", ({ params }) => {
      calls.push({ method: "DELETE", path: `/api/admin/users/${params.id}/invite` });
      const index = users.findIndex((u) => String(u.id) === params.id);
      if (index < 0) return notFound();
      users.splice(index, 1);
      return HttpResponse.json({ status: "ok" });
    }),
    http.post("*/api/admin/users/:id/reset-link", ({ params }) => {
      calls.push({ method: "POST", path: `/api/admin/users/${params.id}/reset-link` });
      const target = find(String(params.id));
      return target ? HttpResponse.json(issued(target, "reset")) : notFound();
    }),
  );
  return { users, calls };
}

function openUsers(initial?: UserOut[]) {
  const backend = fakeBackend(initial);
  window.history.replaceState(null, "", "/admin/users");
  const view = render(<App />);
  return { ...backend, ...view };
}

const cardOf = async (email: string) =>
  within((await screen.findByRole("heading", { name: new RegExp(email.replace(".", "\\.")) })).closest("li") as HTMLElement);
const dialog = (name: string | RegExp) => screen.findByRole("dialog", { name });

// ---- access ------------------------------------------------------------------------------------
test("a member is sent away from the page and no user data is requested", async () => {
  const backend = fakeBackend();
  server.use(http.get("*/api/auth/me", () => HttpResponse.json({ id: 2, email: "member@example.org", role: "member" })));
  window.history.replaceState(null, "", "/admin/users");
  render(<App />);
  expect(await screen.findByRole("heading", { name: strings.upload.heading })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/");
  expect(backend.calls).toEqual([]);
});

// ---- the list ----------------------------------------------------------------------------------
test("every user is listed with role, status and last sign-in, and the current user is marked", async () => {
  openUsers();
  const list = await screen.findByRole("list", { name: t.listLabel });
  expect(within(list).getAllByRole("listitem")).toHaveLength(5);

  const me = await cardOf(adminUser.email);
  expect(me.getByText(t.you)).toBeInTheDocument();
  expect(me.getByLabelText(new RegExp(t.role))).toHaveValue("admin");
  expect(me.getByText(t.status.active)).toBeInTheDocument();
  expect(me.getByText(new RegExp(t.lastSignIn))).toBeInTheDocument();

  const member = await cardOf("member@example.org");
  expect(member.queryByText(t.you)).not.toBeInTheDocument();
  expect(member.getByLabelText(new RegExp(t.role))).toHaveValue("member");

  expect((await cardOf("off@example.org")).getByText(t.status.inactive)).toBeInTheDocument();
  expect((await cardOf("pending@example.org")).getByText(/Invitation pending, link valid until/)).toBeInTheDocument();
  expect((await cardOf("pending@example.org")).getByText(t.neverSignedIn)).toBeInTheDocument();
  expect((await cardOf("lapsed@example.org")).getByText(/Invitation expired on/)).toBeInTheDocument();
});

test("each status offers the actions that make sense for it", async () => {
  openUsers();
  const active = await cardOf("member@example.org");
  expect(active.getByRole("button", { name: /Reset password link/ })).toBeInTheDocument();
  expect(active.getByRole("button", { name: /Deactivate/ })).toBeInTheDocument();
  expect(active.queryByRole("button", { name: /Reactivate/ })).not.toBeInTheDocument();

  const off = await cardOf("off@example.org");
  expect(off.getByRole("button", { name: /Reactivate/ })).toBeInTheDocument();
  expect(off.queryByRole("button", { name: /Deactivate/ })).not.toBeInTheDocument();

  const pending = await cardOf("pending@example.org");
  expect(pending.getByRole("button", { name: /New invitation link/ })).toBeInTheDocument();
  expect(pending.getByRole("button", { name: /Revoke invitation/ })).toBeInTheDocument();
});

test("actions are named after the person, so they can be told apart", async () => {
  openUsers();
  await screen.findByRole("list", { name: t.listLabel });
  expect(screen.getByRole("button", { name: "Deactivate member@example.org" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Revoke invitation pending@example.org" })).toBeInTheDocument();
});

test("the list is built for phone widths: stacked cards, no table, long addresses wrap", async () => {
  const long = "a.very.long.email.address.that.would.overflow@some-quite-long-organisation-name.example.org";
  openUsers([...START, user({ id: 9, email: long })]);
  await screen.findByRole("list", { name: t.listLabel });
  expect(document.querySelector("table")).toBeNull();
  const heading = screen.getByRole("heading", { name: new RegExp(long.slice(0, 20)) });
  expect(heading.className).toMatch(/break-words|overflow-wrap/);
  expect(heading.closest("div")?.className).toMatch(/min-w-0/);
  expect(heading.closest("ul")?.className).toMatch(/flex-col/);
});

test("a list that cannot be loaded shows the error and can be retried", async () => {
  let calls = 0;
  const backend = fakeBackend();
  server.use(
    http.get("*/api/admin/users", () => {
      calls += 1;
      return calls === 1 ? HttpResponse.json({ code: "internal_error", message: "Something went wrong on the server." }, { status: 500 }) : HttpResponse.json(backend.users);
    }),
  );
  window.history.replaceState(null, "", "/admin/users");
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on the server.");
  await userEvent.click(screen.getByRole("button", { name: t.retry }));
  expect(await screen.findByRole("list", { name: t.listLabel })).toBeInTheDocument();
});

// ---- inviting ----------------------------------------------------------------------------------
test("inviting shows a copyable one-time link with its expiry, then the new user in the list", async () => {
  const user = userEvent.setup();
  const backend = openUsers();
  await user.click(await screen.findByRole("button", { name: t.invite }));
  const form = await dialog(t.inviteDialog.heading);
  await user.type(within(form).getByLabelText(t.inviteDialog.email), "  New@Example.org ");
  await user.selectOptions(within(form).getByLabelText(t.inviteDialog.role), "admin");
  await user.click(within(form).getByRole("button", { name: t.inviteDialog.submit }));

  const linkDialog = await dialog(t.linkDialog.inviteHeading("new@example.org"));
  expect(backend.calls.find((c) => c.method === "POST")?.body).toEqual({ email: "New@Example.org", role: "admin" }) // an email input trims its value;
  const link = within(linkDialog).getByLabelText(t.linkDialog.linkLabel) as HTMLInputElement;
  expect(link.value).toMatch(new RegExp(`^${window.location.origin}/accept-invite#token=invite-token-`));
  expect(linkDialog).toHaveTextContent(/new@example.org.*expires on/s);
  expect(linkDialog).toHaveTextContent(/shown only now/);

  await user.click(within(linkDialog).getByRole("button", { name: t.linkDialog.copy }));
  expect(await navigator.clipboard.readText()).toBe(link.value);
  expect(await within(linkDialog).findByText(t.linkDialog.copied)).toBeInTheDocument();

  await user.click(within(linkDialog).getByRole("button", { name: t.linkDialog.done }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  const created = await cardOf("new@example.org");
  expect(created.getByText(/Invitation pending/)).toBeInTheDocument();
  expect(created.getByLabelText(new RegExp(t.role))).toHaveValue("admin");
});

test("inviting an address that already exists shows the reason and no link", async () => {
  const user = userEvent.setup();
  openUsers();
  await user.click(await screen.findByRole("button", { name: t.invite }));
  const form = await dialog(t.inviteDialog.heading);
  await user.type(within(form).getByLabelText(t.inviteDialog.email), "member@example.org");
  await user.click(within(form).getByRole("button", { name: t.inviteDialog.submit }));

  expect(await within(form).findByRole("alert")).toHaveTextContent("already exists");
  expect(screen.queryByRole("dialog", { name: /Invitation link/ })).not.toBeInTheDocument();
});

test("an invalid address is reported on the field", async () => {
  const user = userEvent.setup();
  openUsers();
  await user.click(await screen.findByRole("button", { name: t.invite }));
  const form = await dialog(t.inviteDialog.heading);
  await user.type(within(form).getByLabelText(t.inviteDialog.email), "not-an-address");
  await user.click(within(form).getByRole("button", { name: t.inviteDialog.submit }));
  const field = within(form).getByLabelText(t.inviteDialog.email);
  expect(await within(form).findByRole("alert")).toHaveTextContent("not a valid email");
  expect(field).toHaveAttribute("aria-invalid", "true");
});

// ---- pending invitations -----------------------------------------------------------------------
test("a pending user can get a new link, which replaces the old one", async () => {
  const user = userEvent.setup();
  const backend = openUsers();
  const pending = await cardOf("pending@example.org");
  await user.click(pending.getByRole("button", { name: /New invitation link/ }));

  const linkDialog = await dialog(t.linkDialog.inviteHeading("pending@example.org"));
  expect(backend.calls.at(-2)).toEqual({ method: "POST", path: "/api/admin/users/4/invite" });
  expect((within(linkDialog).getByLabelText(t.linkDialog.linkLabel) as HTMLInputElement).value).toContain("invite-token-4-");
});

test("revoking asks first, naming the person, and removes the invitation only when confirmed", async () => {
  const user = userEvent.setup();
  const backend = openUsers();
  const pending = await cardOf("pending@example.org");
  await user.click(pending.getByRole("button", { name: /Revoke invitation/ }));

  const confirm = await dialog(t.confirm.revokeHeading("pending@example.org"));
  await user.click(within(confirm).getByRole("button", { name: t.confirm.cancel }));
  expect(backend.calls.some((c) => c.method === "DELETE")).toBe(false);

  await user.click((await cardOf("pending@example.org")).getByRole("button", { name: /Revoke invitation/ }));
  await user.click(within(await dialog(t.confirm.revokeHeading("pending@example.org"))).getByRole("button", { name: t.actions.revoke }));
  await waitFor(() => expect(screen.queryByRole("heading", { name: /pending@example\.org/ })).not.toBeInTheDocument());
  expect(await screen.findByRole("status", { name: "" })).toBeDefined();
  expect(screen.getByText(t.notices.revoked("pending@example.org"))).toBeInTheDocument();
});

// ---- deactivate / reactivate -------------------------------------------------------------------
test("deactivating asks first, naming the person and the consequence", async () => {
  const user = userEvent.setup();
  const backend = openUsers();
  await user.click((await cardOf("member@example.org")).getByRole("button", { name: /Deactivate/ }));

  const confirm = await dialog(t.confirm.deactivateHeading("member@example.org"));
  expect(confirm).toHaveTextContent(/signed out immediately/);
  await user.click(within(confirm).getByRole("button", { name: t.confirm.cancel }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(backend.calls.some((c) => c.method === "PATCH")).toBe(false);
  expect((await cardOf("member@example.org")).getByText(t.status.active)).toBeInTheDocument();
});

test("confirming deactivates, and the person can be reactivated afterwards", async () => {
  const user = userEvent.setup();
  const backend = openUsers();
  await user.click((await cardOf("member@example.org")).getByRole("button", { name: /Deactivate/ }));
  await user.click(within(await dialog(t.confirm.deactivateHeading("member@example.org"))).getByRole("button", { name: t.actions.deactivate }));

  await waitFor(async () => expect((await cardOf("member@example.org")).getByText(t.status.inactive)).toBeInTheDocument());
  expect(backend.calls.find((c) => c.method === "PATCH")).toEqual({ method: "PATCH", path: "/api/admin/users/2", body: { is_active: false } });
  expect(screen.getByText(t.notices.deactivated("member@example.org"))).toBeInTheDocument();

  await user.click((await cardOf("member@example.org")).getByRole("button", { name: /Reactivate/ }));
  await waitFor(async () => expect((await cardOf("member@example.org")).getByText(t.status.active)).toBeInTheDocument());
  expect(screen.getByText(t.notices.reactivated("member@example.org"))).toBeInTheDocument();
});

// ---- roles -------------------------------------------------------------------------------------
test("changing a role is applied at once and announced", async () => {
  const user = userEvent.setup();
  const backend = openUsers();
  await user.selectOptions((await cardOf("member@example.org")).getByLabelText(new RegExp(t.role)), "admin");

  await waitFor(() => expect(backend.calls.find((c) => c.method === "PATCH")?.body).toEqual({ role: "admin" }));
  expect(await screen.findByText(t.notices.roleChanged("member@example.org", t.roles.admin))).toBeInTheDocument();
});

test("the last administrator cannot be demoted: the reason is shown and nothing changes", async () => {
  const user = userEvent.setup();
  openUsers();
  const me = await cardOf(adminUser.email);
  await user.selectOptions(me.getByLabelText(new RegExp(t.role)), "member");

  expect(await screen.findByRole("alert")).toHaveTextContent(/At least one active administrator/);
  await waitFor(async () => expect((await cardOf(adminUser.email)).getByLabelText(new RegExp(t.role))).toHaveValue("admin"));
});

// ---- reset links -------------------------------------------------------------------------------
test("an administrator can create a password reset link for an active user", async () => {
  const user = userEvent.setup();
  openUsers();
  await user.click((await cardOf("member@example.org")).getByRole("button", { name: /Reset password link/ }));
  const linkDialog = await dialog(t.linkDialog.resetHeading("member@example.org"));
  expect((within(linkDialog).getByLabelText(t.linkDialog.linkLabel) as HTMLInputElement).value).toContain("reset-token-2-");
});

// ---- while an action runs ----------------------------------------------------------------------
test("a card is disabled while its action is running", async () => {
  const user = userEvent.setup();
  openUsers();
  server.use(
    http.patch("*/api/admin/users/:id", async () => {
      await delay(150);
      return HttpResponse.json(START[2]);
    }),
  );
  await user.click((await cardOf("off@example.org")).getByRole("button", { name: /Reactivate/ }));
  expect((await cardOf("off@example.org")).getByRole("button", { name: /Reactivate/ })).toBeDisabled();
  await waitFor(async () => expect((await cardOf("off@example.org")).getByRole("button", { name: /Reactivate/ })).toBeEnabled());
});

// ---- accessibility -----------------------------------------------------------------------------
test("the list, the invite dialog and the link dialog have no accessibility violations", async () => {
  const user = userEvent.setup();
  const { container } = openUsers();
  await screen.findByRole("list", { name: t.listLabel });
  await expectNoAccessibilityViolations(container);

  await user.click(screen.getByRole("button", { name: t.invite }));
  await expectNoAccessibilityViolations(await dialog(t.inviteDialog.heading));
  await user.type(screen.getByLabelText(t.inviteDialog.email), "axe@example.org");
  await user.click(screen.getByRole("button", { name: t.inviteDialog.submit }));
  await expectNoAccessibilityViolations(await dialog(/Invitation link/));
});
