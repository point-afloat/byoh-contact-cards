import { QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiClientError } from "@/api/client";
import { sessionKey, useSend, useSession } from "@/api/hooks";
import type { SessionOut } from "@/api/types";
import { AuthProvider } from "@/auth/AuthProvider";
import { AppLayout } from "@/components/AppLayout";
import { Protected } from "@/components/Protected";
import { type Step, StepIndicator } from "@/components/StepIndicator";
import { useSessionId } from "@/hooks/useSessionId";
import { DoneScreen } from "@/screens/DoneScreen";
import { ReviewScreen } from "@/screens/ReviewScreen";
import { UploadScreen } from "@/screens/UploadScreen";
import { useSystemTheme } from "@/hooks/useSystemTheme";
import { createQueryClient } from "@/queryClient";
import { AcceptInviteScreen } from "@/screens/AcceptInviteScreen";
import { AccountScreen } from "@/screens/AccountScreen";
import { LoginScreen } from "@/screens/LoginScreen";
import { UsersScreen } from "@/screens/UsersScreen";
import { usePath } from "@/router";
import { strings } from "@/strings";

function ReviewContainer({ session }: { session: SessionOut }) {
  const queryClient = useQueryClient();
  const send = useSend(session.id);
  // "Not signed in" is handled by the sign-in dialog over the page, not by an error under the form.
  const sendError =
    send.error instanceof ApiClientError
      ? send.error.code === "not_authenticated"
        ? null
        : send.error
      : send.error
        ? new ApiClientError(0, "unknown", strings.genericError)
        : null;

  return (
    <ReviewScreen
      session={session}
      sending={send.isPending}
      sendError={sendError}
      onConfirm={(contact, company, preferences) =>
        // Always resolves: failures are shown through `sendError`, and the promise settling
        // is what re-opens the form's single-flight guard.
        send.mutateAsync({ contact, company, preferences }).then(
          () => undefined,
          (error: unknown) => {
            // Already sent elsewhere (a second tab) or the session expired mid-review: reload the
            // session so the app shows the done screen, or the scan screen with an explanation.
            if (
              error instanceof ApiClientError &&
              (error.code === "already_sent" ||
                error.code === "session_expired")
            ) {
              void queryClient.invalidateQueries({
                queryKey: sessionKey(session.id),
              });
            }
          },
        )
      }
    />
  );
}

function ScanPage() {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useSessionId();
  const session = useSession(sessionId);

  // A 401 means the sign-in ended, not that the review session is gone: keep the page (and
  // whatever was typed into it) and let the sign-in dialog deal with it.
  const signedOut =
    session.error instanceof ApiClientError &&
    session.error.code === "not_authenticated";
  const step: Step =
    !sessionId || (session.isError && !signedOut)
      ? "upload"
      : session.data?.sent
        ? "done"
        : "review";

  return (
    <div className="flex flex-col gap-6">
      <StepIndicator current={step} />
      {step === "upload" && (
        <UploadScreen
          onCreated={setSessionId}
          notice={
            sessionId && session.isError ? session.error.message : undefined
          }
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
    </div>
  );
}

function Routes() {
  const path = usePath();
  switch (path) {
    case "/login":
      return <LoginScreen />;
    case "/accept-invite":
      return <AcceptInviteScreen />; // public: the link itself is the credential
    case "/admin/users":
      return (
        <Protected admin>
          <AppLayout>
            <UsersScreen />
          </AppLayout>
        </Protected>
      );
    case "/account":
      return (
        <Protected>
          <AppLayout>
            <AccountScreen />
          </AppLayout>
        </Protected>
      );
    default:
      return (
        <Protected>
          <AppLayout>
            <ScanPage />
          </AppLayout>
        </Protected>
      );
  }
}

export default function App() {
  const [queryClient] = useState(createQueryClient);
  useSystemTheme();
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Routes />
      </AuthProvider>
    </QueryClientProvider>
  );
}
