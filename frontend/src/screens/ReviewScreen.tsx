import { zodResolver } from "@hookform/resolvers/zod";
import { CircleDashed } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { api, type ApiClientError } from "@/api/client";
import { useSaveContact } from "@/api/hooks";
import type { CompanyChoice, Contact, SessionOut } from "@/api/types";
import { CompanyPicker } from "@/components/CompanyPicker";
import { ErrorAlert, Spinner } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useSingleFlight } from "@/hooks/useSingleFlight";
import { cn } from "@/lib/utils";
import { strings } from "@/strings";
import { contactSchema, emptyContact, type FieldConfig, type FieldName, SECTIONS } from "./fields";

type Props = {
  session: SessionOut;
  /** When given, a confirm button is shown and called with the validated contact and company choice. */
  onConfirm?: (contact: Contact, company: CompanyChoice) => Promise<void> | void;
  /** A send is in progress: the form and button are disabled. */
  sending?: boolean;
  /** The last send failed; shown above the form while the entries are kept. */
  sendError?: ApiClientError | null;
  debounceMs?: number;
};

const inputClass =
  "min-h-11 w-full rounded-lg border border-border bg-background px-3 text-base focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring aria-[invalid=true]:border-destructive";

export function ReviewScreen({ session, onConfirm, sending = false, sendError, debounceMs }: Props) {
  const save = useSaveContact(session.id);
  const {
    register,
    handleSubmit,
    getValues,
    setError,
    control,
    formState: { errors },
  } = useForm<Contact>({
    defaultValues: session.contact ?? emptyContact(),
    resolver: zodResolver(contactSchema),
    shouldFocusError: true, // the first invalid field receives focus on a blocked submit
  });

  const values = useWatch({ control });
  const [company, setCompany] = useState<CompanyChoice>({ mode: "none" });
  const singleFlight = useSingleFlight();
  const companyName = (values.company ?? "").trim();
  const companyOnly = companyName !== "" && (values.last_name ?? "").trim() === "";

  // Field problems reported by the server (it stays authoritative) show on the fields.
  useEffect(() => {
    for (const [name, message] of Object.entries(sendError?.errors ?? {})) {
      setError(name as FieldName, { message });
    }
  }, [sendError, setError]);

  // Keep the draft on the server so a reload restores what the user has typed so far.
  const saveDraft = () => save.mutate(getValues());

  function renderField(field: FieldConfig) {
    const id = `field-${field.name}`;
    const error = errors[field.name]?.message;
    const empty = (values[field.name] ?? "").trim() === "";
    const describedBy = [error && `${id}-error`, empty && `${id}-hint`].filter(Boolean).join(" ");
    const common = {
      id,
      autoComplete: field.autoComplete,
      className: cn(inputClass, field.type === "textarea" && "min-h-24 py-2"),
      "aria-invalid": error ? true : undefined,
      "aria-describedby": describedBy || undefined,
      ...register(field.name),
    };
    const listId = field.suggestions ? `${id}-list` : undefined;

    return (
      <div key={field.name} className="flex flex-col gap-1">
        <label htmlFor={id} className="text-sm font-medium">
          {strings.fields[field.name]}
        </label>
        {field.type === "textarea" ? (
          <textarea {...common} rows={3} />
        ) : (
          <input {...common} type={field.type} list={listId} />
        )}
        {listId && (
          <datalist id={listId}>
            {field.suggestions?.map((value) => (
              <option key={value} value={value} />
            ))}
          </datalist>
        )}
        {empty && !error && (
          <p id={`${id}-hint`} className="flex items-center gap-1 text-sm text-muted-foreground">
            <CircleDashed aria-hidden="true" className="size-4" />
            {strings.review.notFound}
          </p>
        )}
        {error && (
          <p id={`${id}-error`} role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <section aria-labelledby="review-heading" className="flex flex-col gap-4">
      <div>
        <h2 id="review-heading" className="text-xl font-semibold">
          {strings.review.heading}
        </h2>
        <p className="text-muted-foreground">{strings.review.intro}</p>
      </div>

      {sendError && (
        <ErrorAlert>
          <p className="font-medium">{strings.send.failed}</p>
          <p>{sendError.message}</p>
        </ErrorAlert>
      )}

      {session.warnings.map((warning) => (
        <p
          key={warning}
          role="status"
          className="rounded-lg border border-border bg-muted px-4 py-3 text-sm"
        >
          {warning}
        </p>
      ))}

      <div className="grid gap-6 md:grid-cols-2">
        <figure className="md:sticky md:top-4 md:self-start">
          <img
            src={api.imageUrl(session.id)}
            alt={strings.review.imageAlt}
            className="max-h-[60vh] w-full rounded-lg border border-border object-contain"
          />
        </figure>

        <form
          noValidate
          onBlur={saveDraft}
          onSubmit={handleSubmit((contact) =>
            singleFlight(async () => {
              if (sending) return;
              await onConfirm?.(contact, companyName ? company : { mode: "none" });
            }),
          )}
          aria-busy={sending}
        >
          <fieldset disabled={sending} className="flex flex-col gap-6">
            {SECTIONS.map((section) => (
              <fieldset key={section.id} className="flex flex-col gap-3">
                <legend className="mb-1 text-base font-semibold">
                  {strings.review.sections[section.id]}
                </legend>
                {section.fields.map(renderField)}
                {section.id === "company" && (
                  <CompanyPicker
                    companyName={companyName}
                    companyOnly={companyOnly}
                    value={company}
                    onChange={setCompany}
                    debounceMs={debounceMs}
                  />
                )}
              </fieldset>
            ))}
            {onConfirm && (
              <Button type="submit" disabled={sending} className="w-full sm:w-auto">
                {sending ? (
                  <>
                    <Spinner />
                    {strings.send.sending}
                  </>
                ) : (
                  strings.review.send
                )}
              </Button>
            )}
          </fieldset>
        </form>
      </div>
    </section>
  );
}
