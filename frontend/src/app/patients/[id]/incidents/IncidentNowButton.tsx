"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Zap } from "lucide-react";
import { createIncident, type S } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { now } from "../medications/DosesPanel";

// ADR 062: one tap records now, the details follow when there is time
export function IncidentNowButton({ patientId, lastType }: { patientId: string; lastType?: string }) {
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
    <span className="inline-flex flex-col">
      <Button onClick={record} disabled={pending} className="bg-red-600 text-white hover:bg-red-700">
        <Zap className="size-4" />{pending ? t("Saving") : t("Now")}
      </Button>
      {error && <span className="mt-1 text-xs text-destructive">{t("SaveError")}</span>}
    </span>
  );
}
