"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Cake } from "lucide-react";
import { PatientAvatar } from "@/components/PatientAvatar";
import { getPatient } from "@/lib/api";
import { formatDate } from "@/lib/utils";

// On a patient's subpages you otherwise lose sight of whose data you are
// looking at — the big header only exists on the overview. This is the same
// person, one line high. Hidden on the overview itself (no double header).
export function PatientMiniHeader() {
  const pathname = usePathname();
  const t = useTranslations("Patient");
  const locale = useLocale();

  const m = pathname.match(/^\/patients\/([^/]+)\/([^/]+)/);
  const patientId = m && m[1] !== "new" ? m[1] : null;

  const [patient, setPatient] = useState<any>(null);
  useEffect(() => {
    if (!patientId) { setPatient(null); return; }
    let active = true;
    getPatient(patientId)
      .then((p) => { if (active) setPatient(p); })
      .catch(() => {});
    return () => { active = false; };
  }, [patientId]);

  if (!patientId || !patient) return null;

  const age = patient.birth_date
    ? Math.floor((Date.now() - new Date(patient.birth_date).getTime()) / 31_557_600_000)
    : null;

  return (
    <Link
      href={`/patients/${patientId}`}
      className="flex items-center gap-3 rounded-xl border bg-card px-3 py-2 transition-colors hover:bg-accent/50"
    >
      <PatientAvatar
        givenName={patient.given_name}
        familyName={patient.family_name}
        photoUrl={patient.has_photo ? `/api/patients/${patientId}/photo` : undefined}
        className="size-12 text-sm"
      />
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold leading-tight">
          {patient.given_name} {patient.family_name}
        </div>
        {patient.birth_date && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Cake className="size-3 shrink-0" />
            <span className="truncate">
              {formatDate(patient.birth_date, locale)}
              {age !== null && ` · ${t("Age", { count: age })}`}
            </span>
          </div>
        )}
      </div>
      <span
        className={`ml-auto shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
          patient.active
            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300"
            : "bg-muted text-muted-foreground"
        }`}
      >
        {patient.active ? t("Active") : t("Inactive")}
      </span>
    </Link>
  );
}
