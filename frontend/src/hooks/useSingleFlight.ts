import { useCallback, useRef } from "react";

/**
 * Runs a task unless one is already running. The flag flips synchronously, so two quick clicks
 * cannot both start (an asynchronous validation step would let a state check pass twice), and it
 * re-opens as soon as the task settles, whether it succeeded or failed.
 */
export function useSingleFlight() {
  const busy = useRef(false);
  return useCallback(async (task: () => Promise<void> | void): Promise<void> => {
    if (busy.current) return;
    busy.current = true;
    try {
      await task();
    } finally {
      busy.current = false;
    }
  }, []);
}
