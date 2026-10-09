"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { formatDate, formatDose } from "@/lib/utils";
import { MedicationActions } from "./MedicationActions";

function period(m: any, locale: string, t: (k: string) => string) {
  if (!m.effective_start && !m.effective_end) return "—";
  const start = m.effective_start ? formatDate(m.effective_start, locale) : "—";
  const end = m.effective_end ? formatDate(m.effective_end, locale) : t("Ongoing");
  return `${start} – ${end}`;
}

export function MedicationsTable({ medications }: { medications: any[] }) {
  const t = useTranslations("Med");
  const locale = useLocale();
  // Phone: cards + tap-reveal action bar, like documents and conditions — a
  // six-column table can only lose against a 400px viewport.
  const [revealed, setRevealed] = useState<string | null>(null);

  return (
    <>
      <div className="space-y-3 lg:hidden">
        {medications.map((m: any) => {
          const open = revealed === m.id;
          return (
            <div key={m.id} className={`overflow-hidden rounded-xl border bg-card ${m.is_active ? "" : "opacity-60"}`}>
              <div className="p-4" onClick={() => setRevealed(open ? null : m.id)}>
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0 truncate text-sm font-medium">{m.medication_display}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${m.is_active ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"}`}>
                    {m.is_active ? t("Active") : t("Ended")}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {formatDose(m) && <>{formatDose(m)} · </>}
                  {period(m, locale, t)}
                </div>
              </div>
              {open && <MedicationActions med={m} iconBar />}
            </div>
          );
        })}
      </div>

      <div className="hidden overflow-hidden rounded-xl border bg-card lg:block">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">{t("NameCol")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("Dosage")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("Period")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("Status")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("Source")}</th>
              <th className="w-px px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {medications.map((m: any) => (
              <tr key={m.id} className="hover:bg-muted/30 transition-colors">
                <td className={`px-4 py-3 font-medium ${m.is_active ? "" : "opacity-50"}`}>{m.medication_display}</td>
                <td className={`px-4 py-3 text-muted-foreground ${m.is_active ? "" : "opacity-50"}`}>{formatDose(m) || "—"}</td>
                <td className={`px-4 py-3 text-muted-foreground ${m.is_active ? "" : "opacity-50"}`}>{period(m, locale, t)}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${m.is_active ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"}`}>
                    {m.is_active ? t("Active") : t("Ended")}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground text-xs">
                  {m.document_reference_id ? t("Extracted") : t("Manual")}
                </td>
                <td className="w-px whitespace-nowrap px-4 py-3">
                  <MedicationActions med={m} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
