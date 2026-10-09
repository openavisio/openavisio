"use client";

import { useTranslations } from "next-intl";
import type { Scale } from "@/lib/einstufung";

/** Where the total sits between the statutory thresholds.
 *
 *  Deliberately a position and not a distance: "5 points to Pflegegrad 3" reads as a
 *  target to aim for, and the points come out of an assessment of actual need, not
 *  out of negotiation (ADR 042). The bands are drawn, the total is marked, and the
 *  reader draws their own conclusion.
 */
export function PflegegradScale({ scale }: { scale: Scale }) {
  const t = useTranslations("Einstufung");
  const min = scale.thresholds[0].from;
  const max = 100;
  const span = max - min;
  const pct = (v: number) => Math.min(100, Math.max(0, ((v - min) / span) * 100));

  return (
    <div className="rounded-xl border bg-card p-5">
      <h2 className="font-semibold mb-1">{t("ScaleTitle")}</h2>
      <p className="text-xs text-muted-foreground mb-4">{t("ScaleHint")}</p>

      <div className="relative h-8 rounded-lg overflow-hidden flex">
        {scale.thresholds.map((b) => (
          <div
            key={b.grade}
            style={{ width: `${((Math.min(b.to, max) - b.from) / span) * 100}%` }}
            className={`h-full flex items-center justify-center text-[11px] font-medium border-r last:border-r-0 ${
              b.grade === scale.grade
                ? "bg-indigo-500/20 text-indigo-700 dark:text-indigo-300"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {b.grade}
          </div>
        ))}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-foreground"
          style={{ left: `${pct(scale.total)}%` }}
          aria-hidden
        />
      </div>

      <div className="mt-2 flex justify-between text-[11px] text-muted-foreground tabular-nums">
        <span>{min}</span>
        <span className="font-medium text-foreground">{t("PointsValue", { points: scale.total })}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
