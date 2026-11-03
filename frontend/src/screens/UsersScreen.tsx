import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiClientError } from "@/api/client";
import type { InviteOut, UserOut } from "@/api/types";
import { useAuth } from "@/auth/AuthProvider";
import { inputClass } from "@/components/LoginForm";
import { ConfirmDialog } from "@/components/users/ConfirmDialog";
import { InviteDialog } from "@/components/users/InviteDialog";
import { LinkDialog } from "@/components/users/LinkDialog";
import { ErrorAlert, Spinner } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { strings } from "@/strings";
import { formatDate } from "./usersFormat";

const USERS_KEY = ["admin-users"] as const;
const t = strings.users;

type Dialog =
  | { kind: "invite" }
  | { kind: "link"; invite: InviteOut; linkKind: "invite" | "reset" }
  | { kind: "deactivate"; user: UserOut }
  | { kind: "revoke"; user: UserOut }
  | null;

function statusText(user: UserOut): string {
  if (user.status === "active") return t.status.active;
  if (user.status === "inactive") return t.status.inactive;
  const until = user.invite_expires_at;
  if (until && new Date(until) <= new Date()) return t.status.expired(formatDate(until));
  return t.status.pending(until ? formatDate(until) : "");
}

type CardProps = {
  user: UserOut;
  isMe: boolean;
  busy: boolean;
  onRole: (role: string) => void;
  onDeactivate: () => void;
  onReactivate: () => void;
  onResetLink: () => void;
  onNewLink: () => void;
  onRevoke: () => void;
};

function UserCard({ user, isMe, busy, ...actions }: CardProps) {
  const roleId = `role-${user.id}`;
  const action = (label: string, onClick: () => void, variant: "primary" | "outline" = "outline") => (
    <Button variant={variant} disabled={busy} onClick={onClick} aria-label={`${label} ${user.email}`}>
      {label}
    </Button>
  );

  return (
    <li className="flex flex-col gap-3 rounded-xl border border-border p-4" aria-busy={busy}>
      <div className="min-w-0">
        <h2 className="break-words text-base font-semibold [overflow-wrap:anywhere]">
          {user.email}
          {isMe && <span className="ml-2 font-normal text-muted-foreground">{t.you}</span>}
        </h2>
        <p>{statusText(user)}</p>
        <p className="text-sm text-muted-foreground">
          {user.last_sign_in_at
            ? `${t.lastSignIn}: ${formatDate(user.last_sign_in_at)}`
            : t.neverSignedIn}
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={roleId} className="text-sm font-medium">
            {t.role}
            <span className="sr-only">
              {" "}
              {t.roleFor} {user.email}
            </span>
          </label>
          <select
            id={roleId}
            value={user.role}
            disabled={busy}
            onChange={(event) => actions.onRole(event.target.value)}
            className={`${inputClass} w-auto`}
          >
            <option value="member">{t.roles.member}</option>
            <option value="admin">{t.roles.admin}</option>
          </select>
        </div>
        {user.status === "active" && (
          <>
            {action(t.actions.resetLink, actions.onResetLink)}
            {action(t.actions.deactivate, actions.onDeactivate)}
          </>
        )}
        {user.status === "inactive" && action(t.actions.reactivate, actions.onReactivate)}
        {user.status === "invited" && (
          <>
            {action(t.actions.newLink, actions.onNewLink)}
            {action(t.actions.revoke, actions.onRevoke)}
          </>
        )}
      </div>
    </li>
  );
}

export function UsersScreen() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: USERS_KEY, queryFn: api.listUsers, retry: false });
  const [dialog, setDialog] = useState<Dialog>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: USERS_KEY });

  /** Run one action for a user: disable their card, show server errors as they come, refresh. */
  async function act(id: number, task: () => Promise<void>) {
    setBusyId(id);
    setError(null);
    setNotice(null);
    try {
      await task();
      await refresh();
    } catch (failure) {
      setError(failure instanceof ApiClientError ? failure.message : strings.genericError);
    } finally {
      setBusyId(null);
    }
  }

  const roleName = (role: string) => t.roles[role] ?? role;

  return (
    <section aria-labelledby="users-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 id="users-heading" className="text-xl font-semibold">
            {t.heading}
          </h1>
          <p className="text-muted-foreground">{t.intro}</p>
        </div>
        <Button onClick={() => setDialog({ kind: "invite" })}>{t.invite}</Button>
      </div>

      {error && <ErrorAlert>{error}</ErrorAlert>}
      <p role="status" className={notice ? "rounded-lg border border-border bg-muted px-4 py-3 text-sm" : "sr-only"}>
        {notice}
      </p>

      {users.isPending && (
        <p role="status" className="flex items-center gap-3">
          <Spinner />
          {strings.auth.loading}
        </p>
      )}
      {users.isError && (
        <div className="flex flex-col items-start gap-3">
          <ErrorAlert>{users.error instanceof ApiClientError ? users.error.message : t.loadFailed}</ErrorAlert>
          <Button variant="outline" onClick={() => void users.refetch()}>
            {t.retry}
          </Button>
        </div>
      )}
      {users.data && (
        <ul aria-label={t.listLabel} className="flex flex-col gap-3">
          {users.data.map((user) => (
            <UserCard
              key={user.id}
              user={user}
              isMe={user.id === me?.id}
              busy={busyId === user.id}
              onRole={(role) =>
                void act(user.id, async () => {
                  await api.updateUser(user.id, { role });
                  setNotice(t.notices.roleChanged(user.email, roleName(role)));
                })
              }
              onDeactivate={() => setDialog({ kind: "deactivate", user })}
              onReactivate={() =>
                void act(user.id, async () => {
                  await api.updateUser(user.id, { is_active: true });
                  setNotice(t.notices.reactivated(user.email));
                })
              }
              onResetLink={() =>
                void act(user.id, async () => {
                  setDialog({ kind: "link", invite: await api.issueResetLink(user.id), linkKind: "reset" });
                })
              }
              onNewLink={() =>
                void act(user.id, async () => {
                  setDialog({ kind: "link", invite: await api.reissueInvite(user.id), linkKind: "invite" });
                })
              }
              onRevoke={() => setDialog({ kind: "revoke", user })}
            />
          ))}
        </ul>
      )}

      <InviteDialog
        open={dialog?.kind === "invite"}
        onClose={() => setDialog(null)}
        onInvited={(invite) => {
          setDialog({ kind: "link", invite, linkKind: "invite" });
          void refresh();
        }}
      />
      <LinkDialog
        invite={dialog?.kind === "link" ? dialog.invite : null}
        kind={dialog?.kind === "link" ? dialog.linkKind : "invite"}
        onClose={() => setDialog(null)}
      />
      <ConfirmDialog
        open={dialog?.kind === "deactivate"}
        heading={dialog?.kind === "deactivate" ? t.confirm.deactivateHeading(dialog.user.email) : ""}
        text={t.confirm.deactivateText}
        confirmLabel={t.actions.deactivate}
        onCancel={() => setDialog(null)}
        onConfirm={() => {
          if (dialog?.kind !== "deactivate") return;
          const { user } = dialog;
          setDialog(null);
          void act(user.id, async () => {
            await api.updateUser(user.id, { is_active: false });
            setNotice(t.notices.deactivated(user.email));
          });
        }}
      />
      <ConfirmDialog
        open={dialog?.kind === "revoke"}
        heading={dialog?.kind === "revoke" ? t.confirm.revokeHeading(dialog.user.email) : ""}
        text={t.confirm.revokeText}
        confirmLabel={t.actions.revoke}
        onCancel={() => setDialog(null)}
        onConfirm={() => {
          if (dialog?.kind !== "revoke") return;
          const { user } = dialog;
          setDialog(null);
          void act(user.id, async () => {
            await api.revokeInvite(user.id);
            setNotice(t.notices.revoked(user.email));
          });
        }}
      />
    </section>
  );
}
