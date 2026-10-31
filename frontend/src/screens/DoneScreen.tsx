import { CircleCheck } from "lucide-react";
import { useEffect, useRef } from "react";
import type { SessionOut } from "@/api/types";
import { Button } from "@/components/ui/button";
import { strings } from "@/strings";

export function DoneScreen({ session, onNext }: { session: SessionOut; onNext: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);

  const message =
    session.record_type === "company"
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
        {strings.done.heading}
      </h2>
      <p role="status">{message}</p>
      <Button onClick={onNext}>{strings.done.next}</Button>
    </section>
  );
}
