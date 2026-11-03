import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { strings } from "@/strings";

/** Every plain-text label in the app, found by walking the strings (functions are skipped). */
function labels(value: unknown, found = new Set<string>()): Set<string> {
  if (typeof value === "string") found.add(value);
  else if (value && typeof value === "object") Object.values(value).forEach((v) => labels(v, found));
  return found;
}

// Tests run from the frontend folder; the guide lives next to it in the repository.
const guide = readFileSync(resolve(process.cwd(), "../docs/admin-guide.md"), "utf-8");
const quoted = [...guide.matchAll(/\*\*([^*]+)\*\*/g)].map((match) => match[1].replace(/\s+/g, " ").trim());

// Bold in the guide means "a name you will see in the app", except these emphasised phrases.
const EMPHASIS = new Set([
  "The app does not send emails.",
  "once",
  "7 days",
  "only now",
  "1 hour",
  "12 characters",
  "5 failed attempts",
  "This removes all accounts.",
]);

test("the guide quotes real buttons and menus: every bold name exists in the app", () => {
  const inApp = labels(strings);
  const unknown = quoted.filter((name) => !EMPHASIS.has(name) && !inApp.has(name));
  expect(unknown).toEqual([]);
});

test("the guide really names the controls an administrator needs", () => {
  const needed = [
    strings.nav.users,
    strings.users.invite,
    strings.users.inviteDialog.submit,
    strings.users.linkDialog.copy,
    strings.users.linkDialog.done,
    strings.users.actions.newLink,
    strings.users.actions.revoke,
    strings.users.actions.deactivate,
    strings.users.actions.reactivate,
    strings.users.actions.resetLink,
    strings.invite.submitInvite,
    strings.account.changeHeading,
    strings.nav.account,
  ];
  expect(needed.filter((name) => !quoted.includes(name))).toEqual([]);
});

test("the guide's numbers match the app's rules", () => {
  expect(strings.account.hint).toContain("12");
  expect(guide).toContain("**12 characters**");
  expect(guide).toContain("**7 days**"); // AUTH_INVITE_TTL_HOURS default 168
  expect(guide).toContain("**1 hour**"); // AUTH_RESET_TTL_MINUTES default 60
});
