import { useEffect, useState } from "react";

export type Theme = "light" | "dark";
const QUERY = "(prefers-color-scheme: dark)";

function current(): Theme {
  return typeof window !== "undefined" && window.matchMedia?.(QUERY).matches ? "dark" : "light";
}

/**
 * Follows the operating system's light/dark preference. The colour tokens switch through a CSS
 * media query; this hook mirrors the preference to `data-theme` and `color-scheme` so native
 * controls and components can react to it as well.
 */
export function useSystemTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(current);

  useEffect(() => {
    const media = window.matchMedia(QUERY);
    const update = () => setTheme(media.matches ? "dark" : "light");
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  return theme;
}
