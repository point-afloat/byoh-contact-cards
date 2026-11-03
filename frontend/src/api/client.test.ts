import { http, HttpResponse } from "msw";
import { server } from "@/test/server";
import { api, ApiClientError } from "./client";

const session = { id: "abc", contact: null, warnings: [], sent: false, errors: {} };

test("uploads the file as multipart form data under the 'file' field", async () => {
  // jsdom's FormData cannot travel through Node's fetch, so inspect the request directly.
  const fetchSpy = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(session), { status: 201 }));
  const file = new File(["x"], "card.jpg", { type: "image/jpeg" });

  await expect(api.createSession(file)).resolves.toMatchObject({ id: "abc" });

  const [target, init] = fetchSpy.mock.calls[0];
  expect(String(target)).toMatch(/\/api\/sessions$/);
  expect(init?.method).toBe("POST");
  expect(init?.body).toBeInstanceOf(FormData);
  expect((init?.body as FormData).get("file")).toBe(file);
  fetchSpy.mockRestore();
});

test("turns the uniform error body into an ApiClientError with field errors", async () => {
  server.use(
    http.post("*/api/sessions/abc/send", () =>
      HttpResponse.json(
        { code: "validation_error", message: "Please fix the highlighted fields.", errors: { email: "bad" } },
        { status: 422 },
      ),
    ),
  );
  const error = await api.send("abc", { contact: {} as never, company: { mode: "none" } }).catch((e) => e);
  expect(error).toBeInstanceOf(ApiClientError);
  expect(error).toMatchObject({ status: 422, code: "validation_error", errors: { email: "bad" } });
});

test("reports an unreachable server with a readable message", async () => {
  server.use(http.get("*/api/sessions/abc", () => HttpResponse.error()));
  const error = await api.getSession("abc").catch((e) => e);
  expect(error).toMatchObject({ status: 0, code: "network_error" });
});

test("handles a non-JSON error body", async () => {
  server.use(http.get("*/api/sessions/abc", () => new HttpResponse("oops", { status: 500 })));
  const error = await api.getSession("abc").catch((e) => e);
  expect(error).toMatchObject({ status: 500, code: "http_500" });
});

test("encodes the company query", async () => {
  let query: string | null = null;
  server.use(
    http.get("*/api/companies", ({ request }) => {
      query = new URL(request.url).searchParams.get("q");
      return HttpResponse.json([]);
    }),
  );
  await api.searchCompanies("Müller & Söhne");
  expect(query).toBe("Müller & Söhne");
});

test("every request carries the custom header the server requires for writes", async () => {
  const seen: Array<string | null> = [];
  server.use(
    http.post("*/api/auth/logout", ({ request }) => {
      seen.push(request.headers.get("x-requested-with"));
      return HttpResponse.json({ status: "ok" });
    }),
    http.get("*/api/auth/me", ({ request }) => {
      seen.push(request.headers.get("x-requested-with"));
      return HttpResponse.json({ id: 1, email: "a@b.org", role: "admin" });
    }),
  );
  await api.logout();
  await api.me();
  expect(seen).toEqual(["XMLHttpRequest", "XMLHttpRequest"]);
});
