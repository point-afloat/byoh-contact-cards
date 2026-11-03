import { type AnchorHTMLAttributes, type MouseEvent, useEffect, useState } from "react";

/** Navigate without a page load. Listeners (usePath) are told through a popstate event. */
export function navigate(path: string, replace = false): void {
  if (window.location.pathname + window.location.search + window.location.hash !== path) {
    window.history[replace ? "replaceState" : "pushState"](null, "", path);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}

/** The current path, kept up to date on navigation and on the browser's back/forward buttons. */
export function usePath(): string {
  const [path, setPath] = useState(() => window.location.pathname);
  useEffect(() => {
    const update = () => setPath(window.location.pathname);
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  return path;
}

type LinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { to: string };

/** A normal link (works with open-in-new-tab) that switches pages without reloading. */
export function Link({ to, onClick, ...props }: LinkProps) {
  function handle(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    const modified = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
    if (event.defaultPrevented || event.button !== 0 || modified) return;
    event.preventDefault();
    navigate(to);
  }
  return <a href={to} onClick={handle} {...props} />;
}
