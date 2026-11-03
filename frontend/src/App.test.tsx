import { render, screen } from "@testing-library/react";
import App from "./App";
import { strings } from "./strings";

test("renders the app title and starts on the first step", async () => {
  render(<App />);
  expect(await screen.findByText(strings.appTitle)).toBeInTheDocument();
  const current = await screen.findByRole("listitem", { current: "step" });
  expect(current).toHaveTextContent(strings.steps.upload);
});
