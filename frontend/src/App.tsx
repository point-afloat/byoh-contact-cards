import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiClientError } from "@/api/client";
import { sessionKey, useSend, useSession } from "@/api/hooks";
import type { SessionOut } from "@/api/types";
import { type Step, StepIndicator } from "@/components/StepIndicator";
import { useSessionId } from "@/hooks/useSessionId";
import { DoneScreen } from "@/screens/DoneScreen";
import { ReviewScreen } from "@/screens/ReviewScreen";
import { UploadScreen } from "@/screens/UploadScreen";
import { useSystemTheme } from "@/hooks/useSystemTheme";
import { strings } from "@/strings";

function ReviewContainer({ session }: { session: SessionOut }) {
  const queryClient = useQueryClient();
  const send = useSend(session.id);
  const sendError =
    send.error instanceof ApiClientError
      ? send.error
      : send.error
        ? new ApiClientError(0, "unknown", strings.genericError)
        : null;

  return (
    <ReviewScreen
      session={session}
      sending={send.isPending}
      sendError={sendError}
      onConfirm={(contact, company) =>
        // Always resolves: failures are shown through `sendError`, and the promise settling
        // is what re-opens the form's single-flight guard.
        send.mutateAsync({ contact, company }).then(
          () => undefined,
          (error: unknown) => {
            // Already sent elsewhere (e.g. a second tab): show the done screen instead.
            if (error instanceof ApiClientError && error.code === "already_sent") {
              void queryClient.invalidateQueries({ queryKey: sessionKey(session.id) });
            }
          },
        )
      }
    />
  );
}

function Shell() {
  const queryClient = useQueryClient();
  useSystemTheme();
  const [sessionId, setSessionId] = useSessionId();
  const session = useSession(sessionId);

  const step: Step = !sessionId || session.isError ? "upload" : session.data?.sent ? "done" : "review";

  return (
    <div className="mx-auto flex min-h-dvh max-w-5xl flex-col gap-6 px-4 py-6">
      <header className="flex flex-col gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{strings.appTitle}</h1>
          <p className="text-muted-foreground">{strings.appTagline}</p>
        </div>
        <StepIndicator current={step} />
      </header>
      <main className="flex-1">
        {step === "upload" && (
          <UploadScreen
            onCreated={setSessionId}
            notice={sessionId && session.isError ? session.error.message : undefined}
          />
        )}
        {step === "review" && session.data && (
          <ReviewContainer key={session.data.id} session={session.data} />
        )}
        {step === "done" && session.data && (
          <DoneScreen
            session={session.data}
            onNext={() => {
              setSessionId(null);
              queryClient.removeQueries({ queryKey: ["session"] });
            }}
          />
        )}
      </main>
    </div>
  );
}

export default function App() {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <Shell />
    </QueryClientProvider>
  );
}
