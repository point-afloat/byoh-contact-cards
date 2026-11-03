import { strings } from "@/strings";
import type {
  CompanyMatch,
  Contact,
  InviteInfoOut,
  InviteOut,
  MeOut,
  SendRequest,
  SessionOut,
  UserOut,
  UserPatch,
} from "./types";

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
    // A custom header on every request is what the server checks to stop cross-site writes.
    response = await fetch(url(path), {
      ...init,
      headers: { "X-Requested-With": "XMLHttpRequest", ...(init?.headers as Record<string, string>) },
    });
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
  me: () => request<MeOut>("/api/auth/me"),
  login: (email: string, password: string) =>
    request<MeOut>("/api/auth/login", json("POST", { email, password })),
  logout: () => request<{ status: string }>("/api/auth/logout", { method: "POST" }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ status: string }>(
      "/api/auth/change-password",
      json("POST", { current_password, new_password }),
    ),
  inviteInfo: (token: string) =>
    request<InviteInfoOut>("/api/auth/invite-info", json("POST", { token })),
  acceptInvite: (token: string, password: string) =>
    request<MeOut>("/api/auth/accept-invite", json("POST", { token, password })),
  listUsers: () => request<UserOut[]>("/api/admin/users"),
  inviteUser: (email: string, role: string) =>
    request<InviteOut>("/api/admin/users", json("POST", { email, role })),
  reissueInvite: (id: number) => request<InviteOut>(`/api/admin/users/${id}/invite`, { method: "POST" }),
  revokeInvite: (id: number) =>
    request<{ status: string }>(`/api/admin/users/${id}/invite`, { method: "DELETE" }),
  updateUser: (id: number, patch: UserPatch) =>
    request<UserOut>(`/api/admin/users/${id}`, json("PATCH", patch)),
  issueResetLink: (id: number) =>
    request<InviteOut>(`/api/admin/users/${id}/reset-link`, { method: "POST" }),
  imageUrl: (id: string) => `/api/sessions/${encodeURIComponent(id)}/image`,
};
