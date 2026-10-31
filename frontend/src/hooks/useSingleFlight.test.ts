import { renderHook } from "@testing-library/react";
import { useSingleFlight } from "./useSingleFlight";

test("a second call while the first is running is ignored", async () => {
  const { result } = renderHook(() => useSingleFlight());
  let release!: () => void;
  const task = vi.fn(() => new Promise<void>((resolve) => (release = resolve)));

  const first = result.current(task);
  await result.current(task); // ignored, resolves immediately
  expect(task).toHaveBeenCalledTimes(1);

  release();
  await first;
});

test("it re-opens after the task finishes", async () => {
  const { result } = renderHook(() => useSingleFlight());
  const task = vi.fn();
  await result.current(task);
  await result.current(task);
  expect(task).toHaveBeenCalledTimes(2);
});

test("it re-opens after the task fails, so a retry is possible", async () => {
  const { result } = renderHook(() => useSingleFlight());
  await expect(
    result.current(() => {
      throw new Error("boom");
    }),
  ).rejects.toThrow("boom");
  const retry = vi.fn();
  await result.current(retry);
  expect(retry).toHaveBeenCalledTimes(1);
});
