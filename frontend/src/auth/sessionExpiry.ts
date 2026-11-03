import { useSyncExternalStore } from "react";

let expired = false;
const listeners = new Set<() => void>();

/** Whether a signed-in user's session ended while the app was open (vs. never signed in). */
export const sessionExpiry = {
  get: () => expired,
  set(value: boolean) {
    if (value !== expired) {
      expired = value;
      listeners.forEach((listener) => listener());
    }
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useSessionExpired(): boolean {
  return useSyncExternalStore(sessionExpiry.subscribe, sessionExpiry.get);
}
