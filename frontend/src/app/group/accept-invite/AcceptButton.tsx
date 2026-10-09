"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { acceptGroupInviteAction } from "../[id]/actions";

export function AcceptButton({ inviteToken }: { inviteToken: string }) {
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function accept() {
    startTransition(async () => {
      const r = await acceptGroupInviteAction(inviteToken);
      if (r.group_id) {
        router.push(`/group/${r.group_id}`);
      }
    });
  }

  return (
    <button
      onClick={accept}
      disabled={pending}
      className="rounded-lg bg-primary text-primary-foreground px-6 py-2.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
    >
      {pending ? "Joining…" : "Join Group"}
    </button>
  );
}
