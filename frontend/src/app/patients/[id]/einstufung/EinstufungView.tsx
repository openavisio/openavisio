"use client";

import { useTranslations } from "next-intl";
import { PflegegradScale } from "./PflegegradScale";
import { ModuleTrend } from "./ModuleTrend";
import type { Einstufung, Scale } from "@/lib/einstufung";

export function EinstufungView({ rows, scale }: { rows: Einstufung[]; scale: Scale | null }) {
  const t = useTranslations("Einstufung");
  const current = rows[0];

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-card p-5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-3xl font-semibold tabular-nums">
            {current.pflegegrad ? t("GradeValue", { grade: current.pflegegrad }) : "—"}
          </span>
          {current.valid_from && (
            <span className="text-sm text-muted-foreground">{t("Since", { date: current.valid_from })}</span>
          )}
        </div>
        <div className="mt-1 text-sm text-muted-foreground">
          {[current.authority, current.file_reference && `${t("FileReference")}: ${current.file_reference}`]
            .filter(Boolean)
            .join(" · ")}
        </div>
        {current.valid_until && (
          <p className="mt-3 text-sm rounded-lg bg-amber-500/10 text-amber-700 dark:text-amber-300 px-3 py-2">
            {t("ExpiresOn", { date: current.valid_until })}
          </p>
        )}
      </div>

      {scale && <PflegegradScale scale={scale} />}

      {rows.length > 1 && <ModuleTrend rows={rows} />}

      <div className="rounded-xl border bg-card overflow-hidden">
        <h2 className="font-semibold px-5 pt-5 pb-3">{t("History")}</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th className="text-left px-4 py-2 font-medium">{t("ValidFrom")}</th>
                <th className="text-left px-4 py-2 font-medium">{t("Grade")}</th>
                <th className="text-left px-4 py-2 font-medium">{t("Points")}</th>
                <th className="text-left px-4 py-2 font-medium">{t("Source")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="px-4 py-2 tabular-nums">{r.valid_from ?? "—"}</td>
                  <td className="px-4 py-2 font-medium">
                    {r.pflegegrad ? t("GradeValue", { grade: r.pflegegrad }) : "—"}
                  </td>
                  <td className="px-4 py-2 tabular-nums">{r.total_points ?? "—"}</td>
                  <td className="px-4 py-2 text-muted-foreground text-xs">
                    {r.source === "pipeline" ? t("FromDocument") : t("Manual")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
