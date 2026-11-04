import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { Contact, SendRequest } from "./types";

export const sessionKey = (id: string) => ["session", id] as const;

export function useSession(id: string | null) {
  return useQuery({
    queryKey: sessionKey(id ?? ""),
    queryFn: () => api.getSession(id as string),
    enabled: id !== null,
    retry: false, // an expired session will not come back
    staleTime: Infinity,
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.createSession(file),
    onSuccess: (session) => queryClient.setQueryData(sessionKey(session.id), session),
  });
}

export function useSaveContact(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (contact: Contact) => api.saveContact(id, contact),
    onSuccess: (session) => queryClient.setQueryData(sessionKey(id), session),
  });
}

export function useSend(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SendRequest) => api.send(id, body),
    onSuccess: (session) => queryClient.setQueryData(sessionKey(id), session),
  });
}

export function useCompanySearch(query: string) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: ["companies", trimmed],
    queryFn: () => api.searchCompanies(trimmed),
    enabled: trimmed.length > 0,
    retry: false,
    staleTime: 60_000,
  });
}

/** What the server says about itself (for the mock-mode notice). It never changes while running. */
export function useAppInfo() {
  return useQuery({
    queryKey: ["app-info"],
    queryFn: () => api.appInfo(),
    retry: false,
    staleTime: Infinity,
  });
}
