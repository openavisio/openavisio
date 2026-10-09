"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { acceptCaregiverInviteAction } from "@/app/patients/[id]/access-actions";

export function AcceptButton({ inviteToken }: { inviteToken: string }) {
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function accept() {
    startTransition(async () => {
      const result = await acceptCaregiverInviteAction(inviteToken);
      if (result.patient_id) {
        router.push(`/patients/${result.patient_id}`);
      }
    });
  }

  return (
    <button
      onClick={accept}
      disabled={pending}
      className="rounded-lg bg-primary text-primary-foreground px-6 py-2.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
    >
      {pending ? "Accepting…" : "Accept invitation"}
    </button>
  );
}
