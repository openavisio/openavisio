"use client";

import { useTranslations } from "next-intl";
import { MODULES, type Einstufung } from "@/lib/einstufung";

/** The six modules across assessments.
 *
 *  This is why the history is kept: a Pflegegrad is one number that moves every few
 *  years and says nothing about what changed, while the modules say where the care
 *  need moved, in the terms the Pflegekasse itself decided in (ADR 042).
 *
 *  A table, not a chart. Six rows and typically two columns is not what bar charts
 *  are for, and it cost 800px to show twelve numbers. The question here is "what
 *  changed", which a chart makes the reader eyeball between two bar heights and a
 *  column states outright. No in-cell fill either: the cap is printed next to the
 *  module name, so a bar would encode the same thing a third time.
 */
export function ModuleTrend({ rows }: { rows: Einstufung[] }) {
  const t = useTranslations("Einstufung");
  // oldest first: a trend reads left to right
  const ordered = [...rows].reverse();
  const latest = ordered.length - 1;

  return (
    <div className="rounded-xl border bg-card p-5">
      <h2 className="font-semibold mb-1">{t("ModulesTitle")}</h2>
      <p className="text-xs text-muted-foreground mb-4">{t("ModulesHint")}</p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="text-left font-medium pb-2">{t("Module")}</th>
              {ordered.map((r) => (
                <th key={r.id} className="text-right font-medium pb-2 pl-4 tabular-nums w-24">
                  {(r.valid_from ?? "").slice(0, 7) || "—"}
                </th>
              ))}
              <th className="text-right font-medium pb-2 pl-4 w-24">{t("Change")}</th>
            </tr>
          </thead>
          <tbody>
            {MODULES.map(({ key, cap }) => {
              const values = ordered.map((r) => r[key] as number | null);
              if (values.every((v) => v == null)) return null;
              const first = values[0];
              const last = values[latest];
              const delta = first != null && last != null ? last - first : null;
              return (
                <tr key={key} className="border-t">
                  <td className="py-1.5 pr-3">
                    <span className="font-medium">{t(`module.${key}`)}</span>
                    <span className="text-xs text-muted-foreground"> · {t("OfCap", { cap })}</span>
                  </td>
                  {values.map((v, i) => (
                    <td key={ordered[i].id} className="py-1.5 pl-4 text-right tabular-nums">
                      {v ?? "—"}
                    </td>
                  ))}
                  <td className={`py-1.5 pl-4 text-right tabular-nums ${delta ? "font-medium" : "text-muted-foreground"}`}>
                    {delta == null ? "—" : delta === 0 ? "±0" : delta > 0 ? `+${delta}` : String(delta)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
