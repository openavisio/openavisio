"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import {
  Trash2,
  Weight,
  Ruler,
  CircleDot,
  Gauge,
  Thermometer,
  Wind,
  HeartPulse,
  Scale,
  Activity,
} from "lucide-react";
import { deleteObservation } from "@/lib/api";
import { TrendChart } from "@/components/TrendChart";
import { useTranslations } from "next-intl";
import { measurementLabel } from "@/lib/measurementTypes";

type Obs = {
  id: string;
  code: string | null;
  code_display: string | null;
  value_quantity: number | null;
  value_unit: string | null;
  value_string: string | null;
  effective_date_time: string | null;
  document_reference_id: string | null;
};

// Anything the pipeline extracted under an unknown code falls back to Activity.
const ICONS: Record<string, typeof Activity> = {
  "body-weight": Weight,
  "body-height": Ruler,
  "head-circumference": CircleDot,
  "blood-pressure-systolic": Gauge,
  "blood-pressure-diastolic": Gauge,
  "body-temperature": Thermometer,
  "oxygen-saturation": Wind,
  "heart-rate": HeartPulse,
  bmi: Scale,
};

export function MeasurementGroups({ observations }: { observations: Obs[] }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const t = useTranslations("Measurement");
  const tc = useTranslations("Common");

  const groups = new Map<string, { display: string; unit: string; items: Obs[] }>();
  for (const obs of observations) {
    const key = obs.code || obs.code_display || "unknown";
    if (!groups.has(key)) {
      // Known codes get the translated name, whatever English text an older row
      // stored in code_display; anything extracted under an unknown code keeps it.
      groups.set(key, { display: measurementLabel(t, obs.code, obs.code_display), unit: obs.value_unit || "", items: [] });
    }
    groups.get(key)!.items.push(obs);
  }

  function handleDelete(id: string) {
    if (!confirm(t("DeleteConfirm"))) return;
    startTransition(async () => {
      await deleteObservation(id);
      router.refresh();
    });
  }

  return (
    <div className="space-y-6">
      {[...groups.entries()].map(([key, group]) => {
        const chartData = group.items
          .filter((o) => o.value_quantity != null && o.effective_date_time)
          .map((o) => ({ date: o.effective_date_time!, value: o.value_quantity! }));
        const sorted = [...group.items].sort((a, b) =>
          (b.effective_date_time || "").localeCompare(a.effective_date_time || "")
        );

        const Icon = ICONS[key] ?? Activity;

        return (
          <div key={key} className="rounded-xl border bg-card overflow-hidden">
            <div className="px-4 py-3 border-b bg-muted/50 flex items-center justify-between">
              <span className="flex items-center gap-2.5 text-base font-semibold">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-4" />
                </span>
                {group.display}
              </span>
              {group.unit && (
                <span className="text-xs text-muted-foreground font-mono">{group.unit}</span>
              )}
            </div>

            {chartData.length >= 2 && (
              <div className="px-4 pt-4 pb-2">
                <TrendChart data={chartData} unit={group.unit || undefined} />
              </div>
            )}

            <table className="w-full text-sm">
              <thead className="border-b bg-muted/20">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-xs uppercase tracking-wide text-muted-foreground">{tc("Date")}</th>
                  <th className="px-4 py-2 text-left font-medium text-xs uppercase tracking-wide text-muted-foreground">{tc("Value")}</th>
                  <th className="px-4 py-2 text-left font-medium text-xs uppercase tracking-wide text-muted-foreground">{tc("Source")}</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {sorted.map((obs) => (
                  <tr key={obs.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-2 text-muted-foreground">
                      {obs.effective_date_time
                        ? new Date(obs.effective_date_time).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-2 font-medium">
                      {obs.value_quantity != null
                        ? `${obs.value_quantity}${group.unit ? ` ${group.unit}` : ""}`
                        : obs.value_string || "—"}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground text-xs">
                      {obs.document_reference_id ? tc("Extracted") : tc("Manual")}
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => handleDelete(obs.id)}
                        disabled={pending}
                        className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
