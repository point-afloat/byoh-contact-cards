import { CircleCheck } from "lucide-react";
import { useEffect, useRef } from "react";
import type { SessionOut } from "@/api/types";
import { Button } from "@/components/ui/button";
import { strings } from "@/strings";

export function DoneScreen({ session, onNext }: { session: SessionOut; onNext: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);

  // Only a mock-mode server returns the payload, so its presence means nothing was sent.
  const payload = session.demo_payload;
  const message = payload
    ? strings.done.mockMessage(session.person_id)
    : session.record_type === "company"
      ? strings.done.company(session.person_id)
      : strings.done.person(session.person_id);

  return (
    <section aria-labelledby="done-heading" className="flex flex-col items-start gap-4">
      <h2
        id="done-heading"
        ref={heading}
        tabIndex={-1}
        className="flex items-center gap-2 text-xl font-semibold outline-none"
      >
        <CircleCheck aria-hidden="true" className="size-6 text-primary" />
        {payload ? strings.done.mockHeading : strings.done.heading}
      </h2>
      <p role="status">{message}</p>
      {payload && (
        <details className="w-full rounded-lg border p-3">
          <summary className="min-h-11 cursor-pointer font-medium">
            {strings.done.mockPayloadSummary}
          </summary>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-sm">
            {JSON.stringify(payload, null, 2)}
          </pre>
        </details>
      )}
      <Button onClick={onNext}>{strings.done.next}</Button>
    </section>
  );
}
