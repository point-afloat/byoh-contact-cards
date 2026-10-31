import { strings } from "@/strings";
import type { CompanyMatch, Contact, SendRequest, SessionOut } from "./types";

/** Error from the backend's uniform `{code, message, errors?}` body (or a network failure). */
export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: Record<string, string>;

  constructor(status: number, code: string, message: string, errors: Record<string, string> = {}) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.errors = errors;
  }
}

function url(path: string): string {
  return new URL(path, window.location.origin).toString();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url(path), init);
  } catch {
    throw new ApiClientError(0, "network_error", strings.networkError);
  }

  if (!response.ok) {
    let body: { code?: unknown; message?: unknown; errors?: unknown } = {};
    try {
      body = await response.json();
    } catch {
      /* non-JSON error body */
    }
    throw new ApiClientError(
      response.status,
      typeof body.code === "string" ? body.code : `http_${response.status}`,
      typeof body.message === "string" ? body.message : strings.genericError,
      typeof body.errors === "object" && body.errors !== null
        ? (body.errors as Record<string, string>)
        : {},
    );
  }
  return (await response.json()) as T;
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export const api = {
  createSession(file: File): Promise<SessionOut> {
    const form = new FormData();
    form.append("file", file);
    return request<SessionOut>("/api/sessions", { method: "POST", body: form });
  },
  getSession: (id: string) => request<SessionOut>(`/api/sessions/${encodeURIComponent(id)}`),
  saveContact: (id: string, contact: Contact) =>
    request<SessionOut>(`/api/sessions/${encodeURIComponent(id)}`, json("PUT", contact)),
  send: (id: string, body: SendRequest) =>
    request<SessionOut>(`/api/sessions/${encodeURIComponent(id)}/send`, json("POST", body)),
  searchCompanies: (query: string) =>
    request<CompanyMatch[]>(`/api/companies?q=${encodeURIComponent(query)}`),
  imageUrl: (id: string) => `/api/sessions/${encodeURIComponent(id)}/image`,
};
