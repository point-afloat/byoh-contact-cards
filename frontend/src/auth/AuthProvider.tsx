import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useMemo } from "react";
import { api, ApiClientError } from "@/api/client";
import type { MeOut } from "@/api/types";
import { ME_KEY } from "@/queryClient";
import { sessionExpiry, useSessionExpired } from "./sessionExpiry";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthValue = {
  status: AuthStatus;
  user: MeOut | null;
  /** The user was signed in and the server has ended the session. */
  expired: boolean;
  signIn: (email: string, password: string) => Promise<MeOut>;
  /** Use after the server signed someone in by other means (accepting an invitation). */
  setUser: (user: MeOut) => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

async function fetchMe(): Promise<MeOut | null> {
  try {
    return await api.me();
  } catch (error) {
    if (error instanceof ApiClientError && error.status === 401) return null; // not signed in
    throw error;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ME_KEY, queryFn: fetchMe, staleTime: Infinity, retry: false });
  const expired = useSessionExpired();
  const user = me.data ?? null;
  const status: AuthStatus = me.isPending ? "loading" : user ? "authenticated" : "anonymous";

  const setUser = useCallback(
    (next: MeOut) => {
      sessionExpiry.set(false);
      queryClient.setQueryData(ME_KEY, next);
    },
    [queryClient],
  );

  const signIn = useCallback(
    async (email: string, password: string) => {
      const next = await api.login(email, password);
      setUser(next);
      return next;
    },
    [setUser],
  );

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      sessionExpiry.set(false);
      // Nothing of this user's data may linger for the next one. The `me` query itself must
      // stay (the provider is listening to it), so it is set to "nobody" instead of removed.
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY[0] });
      queryClient.setQueryData(ME_KEY, null);
    }
  }, [queryClient]);

  const value = useMemo(
    () => ({ status, user, expired, signIn, setUser, signOut }),
    [status, user, expired, signIn, setUser, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (value === null) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}
