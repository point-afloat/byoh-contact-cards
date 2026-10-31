import { act, renderHook } from "@testing-library/react";
import { useSystemTheme } from "./useSystemTheme";

type Listener = () => void;

function mockMatchMedia(initialDark: boolean) {
  let dark = initialDark;
  const listeners = new Set<Listener>();
  window.matchMedia = ((query: string) => ({
    media: query,
    get matches() {
      return dark;
    },
    addEventListener: (_: string, fn: Listener) => listeners.add(fn),
    removeEventListener: (_: string, fn: Listener) => listeners.delete(fn),
  })) as unknown as typeof window.matchMedia;
  return (next: boolean) => {
    dark = next;
    listeners.forEach((fn) => fn());
  };
}

test("follows the OS preference and reacts when it changes", () => {
  const setDark = mockMatchMedia(false);
  const { result } = renderHook(() => useSystemTheme());
  expect(result.current).toBe("light");
  expect(document.documentElement.dataset.theme).toBe("light");

  act(() => setDark(true));
  expect(result.current).toBe("dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(document.documentElement.style.colorScheme).toBe("dark");
});

test("starts dark when the OS already prefers dark", () => {
  mockMatchMedia(true);
  const { result } = renderHook(() => useSystemTheme());
  expect(result.current).toBe("dark");
});
