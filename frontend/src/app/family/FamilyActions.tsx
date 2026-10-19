"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { signOut } from "next-auth/react";
import { makeManager, removeMember, revokeInvitation } from "@/lib/api";

function useAction() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [failed, setFailed] = useState(false);
  const run = (fn: () => Promise<unknown>) => start(async () => {
    setFailed(false);
    try { await fn(); router.refresh(); } catch { setFailed(true); }
  });
  return { pending, failed, run };
}

const link = "text-xs font-medium hover:underline disabled:opacity-50";

export function RemoveMemberButton({ id, name }: { id: string; name: string }) {
  const t = useTranslations("Family");
  const { pending, failed, run } = useAction();
  return (
    <span className="flex flex-col items-end">
      <button type="button" disabled={pending} className={`${link} text-destructive`}
        onClick={() => confirm(t("RemoveConfirm", { name })) && run(() => removeMember(id))}>
        {t("Remove")}
      </button>
      {failed && <span className="text-xs text-destructive">{t("Failed")}</span>}
    </span>
  );
}

// The session still carries the old role, so the old manager signs in again as a member (ADR 052).
export function HandOverButton({ id, name }: { id: string; name: string }) {
  const t = useTranslations("Family");
  const [pending, start] = useTransition();
  const [failed, setFailed] = useState(false);
  return (
    <span className="flex flex-col items-end">
      <button type="button" disabled={pending} className={`${link} text-muted-foreground hover:text-foreground`}
        onClick={() => confirm(t("HandOverConfirm", { name })) && start(async () => {
          setFailed(false);
          try { await makeManager(id); await signOut({ callbackUrl: "/login" }); } catch { setFailed(true); }
        })}>
        {t("HandOver")}
      </button>
      {failed && <span className="text-xs text-destructive">{t("Failed")}</span>}
    </span>
  );
}

export function RevokeInvitationButton({ id }: { id: string }) {
  const t = useTranslations("Family");
  const { pending, failed, run } = useAction();
  return (
    <span className="flex flex-col items-end">
      <button type="button" disabled={pending} className={`${link} text-muted-foreground hover:text-destructive`}
        onClick={() => run(() => revokeInvitation(id))}>
        {t("Revoke")}
      </button>
      {failed && <span className="text-xs text-destructive">{t("Failed")}</span>}
    </span>
  );
}
