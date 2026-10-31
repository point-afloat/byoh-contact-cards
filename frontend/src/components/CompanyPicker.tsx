import { useEffect, useRef } from "react";
import { ApiClientError } from "@/api/client";
import { useCompanySearch } from "@/api/hooks";
import type { CompanyChoice } from "@/api/types";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { strings } from "@/strings";

type Props = {
  /** The company name currently in the form. */
  companyName: string;
  /** No last name on the card: only creating the company is possible. */
  companyOnly: boolean;
  value: CompanyChoice;
  onChange: (choice: CompanyChoice) => void;
  debounceMs?: number;
};

function Option(props: { id: string; checked: boolean; onSelect: () => void; label: string }) {
  return (
    <label htmlFor={props.id} className="flex min-h-11 cursor-pointer items-center gap-3">
      <input
        id={props.id}
        type="radio"
        name="company-choice"
        checked={props.checked}
        onChange={props.onSelect}
        className="size-5"
      />
      <span>{props.label}</span>
    </label>
  );
}

export function CompanyPicker({ companyName, companyOnly, value, onChange, debounceMs = 400 }: Props) {
  const name = companyName.trim();
  const query = useDebouncedValue(name, debounceMs);
  const search = useCompanySearch(query);

  // Keep the latest callback in a ref so a caller passing a new function every render
  // cannot re-trigger the reset below (which would loop forever).
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  });

  // A choice made for another company name no longer applies.
  useEffect(() => {
    onChangeRef.current({ mode: companyOnly ? "create" : "none" });
  }, [query, companyOnly]);

  if (!name) return null;

  const settled = query === name; // results shown belong to the name in the field
  const searching = !settled || search.isFetching;
  const failed = settled && search.isError;
  const matches = settled && search.data ? search.data : [];
  const failureMessage =
    search.error instanceof ApiClientError ? search.error.message : strings.company.searchFailed;

  return (
    <div className="flex flex-col gap-2" role="group" aria-label={strings.company.legend}>
      <p className="text-sm font-medium">{strings.company.legend}</p>

      {searching && (
        <p role="status" className="text-sm text-muted-foreground">
          {strings.company.searching}
        </p>
      )}
      {failed && (
        <p role="status" className="rounded-lg border border-border bg-muted px-3 py-2 text-sm">
          {strings.company.searchFailed} ({failureMessage})
        </p>
      )}
      {!searching && !failed && matches.length === 0 && (
        <p className="text-sm text-muted-foreground">{strings.company.noMatch}</p>
      )}

      {companyOnly ? (
        <>
          <p className="text-sm">{strings.company.companyOnlyNote}</p>
          {matches.length > 0 && (
            <p className="text-sm text-muted-foreground">
              {strings.company.mayExist} {matches.map((m) => m.name).join(", ")}
            </p>
          )}
          <Option
            id="company-create"
            checked={value.mode === "create"}
            onSelect={() => onChange({ mode: "create" })}
            label={strings.company.create(name)}
          />
        </>
      ) : (
        <>
          {matches.map((match) => (
            <Option
              key={match.id}
              id={`company-link-${match.id}`}
              checked={value.mode === "link" && value.id === match.id}
              onSelect={() => onChange({ mode: "link", id: match.id })}
              label={strings.company.link(match.name, match.city)}
            />
          ))}
          {!failed && !searching && (
            <Option
              id="company-create"
              checked={value.mode === "create"}
              onSelect={() => onChange({ mode: "create" })}
              label={strings.company.create(name)}
            />
          )}
          <Option
            id="company-none"
            checked={value.mode === "none"}
            onSelect={() => onChange({ mode: "none" })}
            label={strings.company.none}
          />
        </>
      )}
    </div>
  );
}
