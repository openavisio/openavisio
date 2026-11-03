"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Zap } from "lucide-react";
import { createIncident, type S } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { now } from "../medications/DosesPanel";

// ADR 062: one tap records now, the details follow when there is time
export function IncidentNowButton({ patientId, lastType, pill = false }: { patientId: string; lastType?: string; pill?: boolean }) {
  const t = useTranslations("Incidents");
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState(false);

  function record() {
    setError(false);
    startTransition(async () => {
      try {
        const i = await createIncident(patientId, { incident_type: (lastType ?? "seizure") as S<"IncidentIn">["incident_type"], occurred_at: now() });
        router.push(`/patients/${patientId}/incidents?open=${i.id}`);
        router.refresh();
      } catch {
        setError(true);
      }
    });
  }

  return (
    <span className="relative inline-flex">
      {pill ? (
        <button type="button" onClick={record} disabled={pending}
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-red-600/30 bg-red-500/10 px-3 py-1.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-500/20 disabled:opacity-60 dark:text-red-300">
          <Zap className="size-4" />{pending ? t("Saving") : t("Now")}
        </button>
      ) : (
        <Button onClick={record} disabled={pending} className="bg-red-600 text-white hover:bg-red-700">
          <Zap className="size-4" />{pending ? t("Saving") : t("Now")}
        </Button>
      )}
      {error && <span className="absolute top-full right-0 mt-1 whitespace-nowrap text-xs text-destructive">{t("SaveError")}</span>}
    </span>
  );
}
