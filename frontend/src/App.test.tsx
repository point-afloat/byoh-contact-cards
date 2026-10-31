import { render, screen } from "@testing-library/react";
import App from "./App";
import { strings } from "./strings";

test("renders the app title and starts on the first step", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: strings.appTitle })).toBeInTheDocument();
  const current = screen.getByRole("listitem", { current: "step" });
  expect(current).toHaveTextContent(strings.steps.upload);
});
