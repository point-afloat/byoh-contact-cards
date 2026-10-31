import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useState } from "react";
import type { CompanyChoice } from "@/api/types";
import { strings } from "@/strings";
import { server } from "@/test/server";
import { CompanyPicker } from "./CompanyPicker";

const acme = { id: 7, name: "Acme GmbH", city: "Berlin" };

function Harness({
  name = "Acme",
  companyOnly = false,
  onChange,
}: {
  name?: string;
  companyOnly?: boolean;
  onChange?: (c: CompanyChoice) => void;
}) {
  const [value, setValue] = useState<CompanyChoice>({ mode: "none" });
  return (
    <QueryClientProvider client={new QueryClient()}>
      <CompanyPicker
        companyName={name}
        companyOnly={companyOnly}
        value={value}
        debounceMs={0}
        onChange={(c) => {
          setValue(c);
          onChange?.(c);
        }}
      />
    </QueryClientProvider>
  );
}

test("matches are offered and one can be selected to link the contact", async () => {
  server.use(http.get("*/api/companies", () => HttpResponse.json([acme])));
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);

  const link = await screen.findByLabelText(strings.company.link("Acme GmbH", "Berlin"));
  expect(screen.getByLabelText(strings.company.none)).toBeChecked(); // nothing is linked by default
  await userEvent.click(link);
  expect(link).toBeChecked();
  expect(onChange).toHaveBeenLastCalledWith({ mode: "link", id: 7 });
});

test("the search is made with the company name from the form", async () => {
  let query: string | null = null;
  server.use(
    http.get("*/api/companies", ({ request }) => {
      query = new URL(request.url).searchParams.get("q");
      return HttpResponse.json([acme]);
    }),
  );
  render(<Harness name="Acme" />);
  await screen.findByLabelText(strings.company.link("Acme GmbH", "Berlin"));
  expect(query).toBe("Acme");
});

test("with no match the user can create the company or go without a link", async () => {
  server.use(http.get("*/api/companies", () => HttpResponse.json([])));
  const onChange = vi.fn();
  render(<Harness name="Brand New AG" onChange={onChange} />);

  expect(await screen.findByText(strings.company.noMatch)).toBeInTheDocument();
  await userEvent.click(screen.getByLabelText(strings.company.create("Brand New AG")));
  expect(onChange).toHaveBeenLastCalledWith({ mode: "create" });
  await userEvent.click(screen.getByLabelText(strings.company.none));
  expect(onChange).toHaveBeenLastCalledWith({ mode: "none" });
});

test("when the search fails a notice shows and the user can still go on without a link", async () => {
  server.use(
    http.get("*/api/companies", () =>
      HttpResponse.json(
        { code: "fundraisingbox_unreachable", message: "FundraisingBox could not be reached." },
        { status: 502 },
      ),
    ),
  );
  render(<Harness />);

  const notice = await screen.findByText(new RegExp(strings.company.searchFailed.slice(0, 20)));
  expect(notice).toHaveTextContent("FundraisingBox could not be reached.");
  expect(screen.getByLabelText(strings.company.none)).toBeChecked();
  // creating is not offered when we could not check whether the company exists
  expect(screen.queryByLabelText(strings.company.create("Acme"))).not.toBeInTheDocument();
});

test("a card with only a company offers only creating it", async () => {
  server.use(http.get("*/api/companies", () => HttpResponse.json([])));
  const onChange = vi.fn();
  render(<Harness name="Solo GmbH" companyOnly onChange={onChange} />);

  expect(await screen.findByText(strings.company.companyOnlyNote)).toBeInTheDocument();
  expect(screen.getByLabelText(strings.company.create("Solo GmbH"))).toBeChecked();
  expect(screen.queryByLabelText(strings.company.none)).not.toBeInTheDocument();
  expect(onChange).toHaveBeenCalledWith({ mode: "create" });
});

test("a company-only card warns when a similar company may already exist", async () => {
  server.use(http.get("*/api/companies", () => HttpResponse.json([acme])));
  render(<Harness name="Acme" companyOnly />);
  expect(await screen.findByText(/may already exist/)).toHaveTextContent("Acme GmbH");
});

test("nothing renders when there is no company name", () => {
  const { container } = render(<Harness name="  " />);
  expect(container).toBeEmptyDOMElement();
});

test("the choice resets when the company name changes", async () => {
  server.use(http.get("*/api/companies", () => HttpResponse.json([acme])));
  const onChange = vi.fn();
  const { rerender } = render(<Harness name="Acme" onChange={onChange} />);
  await userEvent.click(await screen.findByLabelText(strings.company.link("Acme GmbH", "Berlin")));
  expect(onChange).toHaveBeenLastCalledWith({ mode: "link", id: 7 });

  rerender(<Harness name="Acme Other" onChange={onChange} />);
  expect(onChange).toHaveBeenLastCalledWith({ mode: "none" });
});
