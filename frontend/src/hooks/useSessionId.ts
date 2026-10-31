import { useCallback, useEffect, useState } from "react";

const PARAM = "session";

function read(): string | null {
  return new URLSearchParams(window.location.search).get(PARAM);
}

/** The active review session id lives in the URL (`?session=…`) so a reload restores it. */
export function useSessionId(): [string | null, (id: string | null) => void] {
  const [id, setId] = useState<string | null>(read);

  useEffect(() => {
    const onPop = () => setId(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const update = useCallback((next: string | null) => {
    const url = new URL(window.location.href);
    if (next) url.searchParams.set(PARAM, next);
    else url.searchParams.delete(PARAM);
    window.history.pushState(null, "", url);
    setId(next);
  }, []);

  return [id, update];
}
