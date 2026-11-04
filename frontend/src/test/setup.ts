import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest";
import { sessionExpiry } from "@/auth/sessionExpiry";
import { server } from "./server";

export const adminUser = { id: 1, email: "admin@example.org", role: "admin" };

// jsdom has no matchMedia; default to a light-scheme OS. Tests can override window.matchMedia.
window.matchMedia ??= ((query: string) => ({
  media: query,
  matches: false,
  addEventListener: () => {},
  removeEventListener: () => {},
})) as unknown as typeof window.matchMedia;

// jsdom has no modal <dialog>: open and close it by toggling the attribute.
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close() {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
// Most tests are about signed-in screens: start as the administrator. Tests override this.
beforeEach(() =>
  server.use(
    http.get("*/api/auth/me", () => HttpResponse.json(adminUser)),
    http.get("*/api/app-info", () => HttpResponse.json({ fundraisingbox_mode: "live" })),
  ),
);
afterEach(() => {
  cleanup();
  server.resetHandlers();
  window.history.replaceState(null, "", "/");
  sessionExpiry.set(false);
});
afterAll(() => server.close());
