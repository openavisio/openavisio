"use client";

import { useState, useTransition } from "react";
import { Star } from "lucide-react";
import { useTranslations } from "next-intl";
import { toggleDocumentFavoriteAction } from "./actions";

export function FavoriteButton({
  docId,
  patientId,
  initial,
}: {
  docId: string;
  patientId: string;
  initial: boolean;
}) {
  const t = useTranslations("DocumentsPage");
  const [on, setOn] = useState(initial);
  const [, startTransition] = useTransition();

  function toggle() {
    const next = !on;
    setOn(next);  // optimistic — a failed star is not worth a spinner
    startTransition(async () => {
      const res = await toggleDocumentFavoriteAction(docId, patientId, next);
      if (res.error) setOn(!next);
    });
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={on}
      title={t(on ? "unfavorite" : "favorite")}
      aria-label={t(on ? "unfavorite" : "favorite")}
      className={`inline-flex shrink-0 cursor-pointer items-center justify-center rounded-md size-6 transition-colors ${
        on ? "text-amber-500 hover:bg-amber-500/10" : "text-muted-foreground/40 hover:text-muted-foreground hover:bg-muted"
      }`}
    >
      <Star className="h-3.5 w-3.5" fill={on ? "currentColor" : "none"} />
    </button>
  );
}
