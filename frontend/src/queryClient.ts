import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiClientError } from "@/api/client";
import { sessionExpiry } from "@/auth/sessionExpiry";

export const ME_KEY = ["me"] as const;

/**
 * One place that notices "you are not signed in" from any request. The page stays mounted, so
 * unsent form values survive, and a sign-in dialog is shown over it (see ReLoginDialog).
 */
export function createQueryClient(): QueryClient {
  const handle = (error: unknown) => {
    if (error instanceof ApiClientError && error.code === "not_authenticated") {
      client.setQueryData(ME_KEY, null);
      sessionExpiry.set(true);
    }
  };
  const client = new QueryClient({
    queryCache: new QueryCache({ onError: handle }),
    mutationCache: new MutationCache({ onError: handle }),
  });
  return client;
}
