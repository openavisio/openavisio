"use client";

import { useState, useTransition } from "react";
import { Lock } from "lucide-react";
import { useTranslations } from "next-intl";
import { closePurposeAction } from "./sharing-admin-actions";

export function ClosePurposeButton({ purposeId }: { purposeId: string }) {
  const t = useTranslations("AdminSharing");
  const tc = useTranslations("Common");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  function close() {
    setError("");
    startTransition(async () => {
      const r = await closePurposeAction(purposeId);
      if (r.error) setError(r.error);
    });
  }

  return (
    <span className="inline-flex flex-col">
      <button
        onClick={close}
        disabled={pending}
        className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
      >
        <Lock className="size-3.5" /> {pending ? t("Closing") : tc("Close")}
      </button>
      {error && <span className="text-xs text-destructive mt-1">{error}</span>}
    </span>
  );
}
