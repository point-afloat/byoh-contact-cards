import { cn } from "@/lib/utils";
import { strings } from "@/strings";

export type Step = "upload" | "review" | "done";
const ORDER: Step[] = ["upload", "review", "done"];

export function StepIndicator({ current }: { current: Step }) {
  const currentIndex = ORDER.indexOf(current);
  return (
    <nav aria-label={strings.stepsLabel}>
      <ol className="flex items-center gap-2 text-sm">
        {ORDER.map((step, index) => {
          const isCurrent = index === currentIndex;
          const isDone = index < currentIndex;
          return (
            <li
              key={step}
              aria-current={isCurrent ? "step" : undefined}
              data-state={isCurrent ? "current" : isDone ? "complete" : "upcoming"}
              className={cn(
                "flex items-center gap-2 rounded-full px-3 py-1 font-medium",
                isCurrent && "bg-primary text-primary-foreground",
                isDone && "bg-muted text-foreground",
                !isCurrent && !isDone && "text-muted-foreground",
              )}
            >
              <span aria-hidden="true">{isDone ? "✓" : index + 1}</span>
              <span>{strings.steps[step]}</span>
              {isDone && <span className="sr-only"> (completed)</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
