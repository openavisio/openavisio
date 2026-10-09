"use client";

import { useRouter } from "next/navigation";
import { Fragment, useState, useTransition } from "react";
import { Trash2, ArrowUp, ArrowDown, ChevronDown } from "lucide-react";
import { deleteObservation } from "@/lib/api";
import { TrendChart } from "@/components/TrendChart";
import { useTranslations } from "next-intl";

type Obs = {
  id: string;
  code: string | null;
  code_display: string | null;
  panel: string | null;
  value_quantity: number | null;
  value_unit: string | null;
  value_string: string | null;
  reference_range: string | null;
  ref_low: number | null;
  ref_high: number | null;
  effective_date_time: string | null;
  document_reference_id: string | null;
};

const dayOf = (s: string | null) => (s ? s.slice(0, 10) : "");
const paramKey = (o: Obs) => o.code || o.code_display || "unknown";

// Only these 15 CBC slugs have translated labels (param_*); other coded analytes
// (ADR 029) show their printed name.
const CBC_I18N = new Set([
  "hemoglobin", "hematocrit", "rbc", "wbc", "platelets", "mcv", "mch", "mchc",
  "rdw", "mpv", "neutrophils", "lymphocytes", "monocytes", "eosinophils", "basophils",
]);

function outOfRange(o: Obs): "low" | "high" | null {
  if (o.value_quantity == null) return null;
  if (o.ref_low != null && o.value_quantity < o.ref_low) return "low";
  if (o.ref_high != null && o.value_quantity > o.ref_high) return "high";
  return null;
}

export function LabResultGroups({ observations }: { observations: Obs[] }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [openParam, setOpenParam] = useState<string | null>(null);
  const [expandedDays, setExpandedDays] = useState<Record<string, boolean>>({});
  const t = useTranslations("LabResult");
  const tc = useTranslations("Common");

  const distinctDates = new Set(observations.map((o) => dayOf(o.effective_date_time))).size;
  const [view, setView] = useState<"matrix" | "cards">(distinctDates >= 2 ? "matrix" : "cards");

  function label(o: Obs) {
    return o.code && CBC_I18N.has(o.code) ? t(`param_${o.code}`) : o.code_display || t("UnknownTest");
  }
  function refText(o: Obs) {
    if (o.reference_range) return o.reference_range;
    if (o.ref_low != null && o.ref_high != null) return `${o.ref_low}–${o.ref_high}`;
    if (o.ref_high != null) return `< ${o.ref_high}`;
    if (o.ref_low != null) return `> ${o.ref_low}`;
    return "—";
  }
  function seriesFor(key: string) {
    // One point per day, matching the matrix cell (some analytes appear twice per
    // report — machine vs microscopic differential); last wins, same as the table.
    const byDay = new Map<string, number>();
    for (const o of observations) {
      if (paramKey(o) === key && o.value_quantity != null && o.effective_date_time) {
        byDay.set(dayOf(o.effective_date_time), o.value_quantity);
      }
    }
    return [...byDay.entries()]
      .map(([date, value]) => ({ date, value }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }
  function cellValue(o: Obs) {
    return o.value_quantity != null ? `${o.value_quantity}` : o.value_string || "—";
  }

  function handleDelete(id: string) {
    if (!confirm(t("DeleteConfirm"))) return;
    startTransition(async () => {
      await deleteObservation(id);
      router.refresh();
    });
  }

  function handleDeletePanel(items: Obs[]) {
    if (!confirm(t("DeletePanelConfirm", { count: items.length }))) return;
    startTransition(async () => {
      await Promise.all(items.map((o) => deleteObservation(o.id)));
      router.refresh();
    });
  }

  const toggle = (
    <div className="flex justify-end">
      <div className="inline-flex items-center rounded-md border border-border p-0.5">
        {(["matrix", "cards"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              view === v ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t(v === "matrix" ? "viewTrend" : "viewCards")}
          </button>
        ))}
      </div>
    </div>
  );

  // ---- Matrix view: one table per panel, parameters × dates (#78) ----
  if (view === "matrix") {
    const byPanel = new Map<string, Obs[]>();
    for (const o of observations) {
      const title = o.panel || t("LabPanel");
      if (!byPanel.has(title)) byPanel.set(title, []);
      byPanel.get(title)!.push(o);
    }

    return (
      <div className="space-y-4">
        {toggle}
        {[...byPanel.entries()].map(([title, items]) => {
          const dates = [...new Set(items.map((o) => dayOf(o.effective_date_time)))].sort((a, b) => b.localeCompare(a));
          const paramsMap = new Map<string, { key: string; label: string; ref: string; unit: string; byDate: Record<string, Obs> }>();
          for (const o of items) {
            const key = paramKey(o);
            let p = paramsMap.get(key);
            if (!p) {
              p = { key, label: label(o), ref: refText(o), unit: o.value_unit || "", byDate: {} };
              paramsMap.set(key, p);
            }
            p.byDate[dayOf(o.effective_date_time)] = o;
            if (p.ref === "—") p.ref = refText(o);
            if (!p.unit && o.value_unit) p.unit = o.value_unit;
          }
          const params = [...paramsMap.values()].sort((a, b) => a.label.localeCompare(b.label));

          return (
            <div key={title} className="rounded-xl border bg-card overflow-hidden">
              <div className="px-4 py-3 border-b bg-muted/50">
                <span className="font-medium text-sm">{title}</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b bg-muted/20">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-xs sticky left-0 bg-muted/20 z-10">{t("Parameter")}</th>
                      {dates.map((d) => (
                        <th key={d} className="px-3 py-2 text-right font-medium text-xs whitespace-nowrap">
                          {d ? new Date(d).toLocaleDateString() : "—"}
                        </th>
                      ))}
                      <th className="px-4 py-2 text-left font-medium text-xs whitespace-nowrap">{t("Reference")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {params.map((p) => {
                      const isOpen = openParam === p.key;
                      const series = isOpen ? seriesFor(p.key) : [];
                      return (
                        <Fragment key={p.key}>
                          <tr
                            onClick={() => setOpenParam(isOpen ? null : p.key)}
                            className={`hover:bg-muted/30 transition-colors cursor-pointer ${isOpen ? "bg-muted/30" : ""}`}
                          >
                            <td className="px-4 py-2 font-medium whitespace-nowrap sticky left-0 bg-card">{p.label}</td>
                            {dates.map((d) => {
                              const o = p.byDate[d];
                              if (!o) return <td key={d} className="px-3 py-2 text-right text-muted-foreground">—</td>;
                              const flag = outOfRange(o);
                              return (
                                <td
                                  key={d}
                                  title={flag ? (flag === "high" ? t("AboveRef") : t("BelowRef")) : undefined}
                                  className={`px-3 py-2 text-right whitespace-nowrap font-medium ${
                                    flag === "high" ? "text-destructive" : flag === "low" ? "text-amber-600 dark:text-amber-400" : ""
                                  }`}
                                >
                                  {cellValue(o)}
                                  {flag === "high" ? " ↑" : flag === "low" ? " ↓" : ""}
                                </td>
                              );
                            })}
                            <td className="px-4 py-2 text-muted-foreground text-xs font-mono whitespace-nowrap">
                              {p.ref}{p.unit ? ` ${p.unit}` : ""}
                            </td>
                          </tr>
                          {isOpen && (
                            <tr>
                              <td colSpan={dates.length + 2} className="px-4 py-3 bg-muted/10">
                                {series.length >= 2 ? (
                                  <TrendChart data={series} unit={p.unit || undefined} />
                                ) : (
                                  <p className="text-xs text-muted-foreground">{t("NotEnoughTrend")}</p>
                                )}
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  // ---- Cards view: days as collapsible groups, panels within (#78) ----
  const days = new Map<string, Map<string, Obs[]>>(); // date -> panel -> items
  for (const o of observations) {
    const date = dayOf(o.effective_date_time);
    const title = o.panel || t("LabPanel");
    if (!days.has(date)) days.set(date, new Map());
    const pm = days.get(date)!;
    if (!pm.has(title)) pm.set(title, []);
    pm.get(title)!.push(o);
  }
  const sortedDays = [...days.keys()].sort((a, b) => b.localeCompare(a));
  const newestDay = sortedDays[0];
  const isDayOpen = (d: string) => expandedDays[d] ?? d === newestDay;
  const toggleDay = (d: string) => setExpandedDays((p) => ({ ...p, [d]: !isDayOpen(d) }));

  function paramRows(items: Obs[]) {
    return [...items]
      .sort((a, b) => label(a).localeCompare(label(b)))
      .map((obs) => {
        const flag = outOfRange(obs);
        const key = paramKey(obs);
        const numeric = obs.value_quantity != null;
        const isOpen = openParam === key;
        const series = isOpen ? seriesFor(key) : [];
        return (
          <Fragment key={obs.id}>
            <tr
              onClick={() => numeric && setOpenParam(isOpen ? null : key)}
              className={`hover:bg-muted/30 transition-colors ${numeric ? "cursor-pointer" : ""} ${isOpen ? "bg-muted/30" : ""}`}
            >
              <td className="px-4 py-2 font-medium">{label(obs)}</td>
              <td className="px-4 py-2">
                <span
                  className={`inline-flex items-center gap-1 font-medium ${
                    flag === "high" ? "text-destructive" : flag === "low" ? "text-amber-600 dark:text-amber-400" : ""
                  }`}
                >
                  {numeric
                    ? `${obs.value_quantity}${obs.value_unit ? ` ${obs.value_unit}` : ""}`
                    : obs.value_string || "—"}
                  {flag === "high" && <ArrowUp className="h-3.5 w-3.5" aria-label={t("AboveRef")} />}
                  {flag === "low" && <ArrowDown className="h-3.5 w-3.5" aria-label={t("BelowRef")} />}
                </span>
              </td>
              <td className="px-4 py-2 text-muted-foreground text-xs font-mono">{refText(obs)}</td>
              <td className="px-4 py-2 text-muted-foreground text-xs">
                {obs.document_reference_id ? tc("Extracted") : tc("Manual")}
              </td>
              <td className="px-4 py-2">
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(obs.id); }}
                  disabled={pending}
                  className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </td>
            </tr>
            {isOpen && (
              <tr>
                <td colSpan={5} className="px-4 py-3 bg-muted/10">
                  {series.length >= 2 ? (
                    <TrendChart data={series} unit={obs.value_unit || undefined} />
                  ) : (
                    <p className="text-xs text-muted-foreground">{t("NotEnoughTrend")}</p>
                  )}
                </td>
              </tr>
            )}
          </Fragment>
        );
      });
  }

  return (
    <div className="space-y-4">
      {toggle}
      {sortedDays.map((date) => {
        const panelMap = days.get(date)!;
        const open = isDayOpen(date);
        const count = [...panelMap.values()].reduce((n, it) => n + it.length, 0);
        return (
          <div key={date} className="rounded-xl border bg-card overflow-hidden">
            <button
              onClick={() => toggleDay(date)}
              className="w-full flex items-center justify-between px-4 py-3 bg-muted/50 hover:bg-muted/70 transition-colors"
            >
              <span className="flex items-center gap-2 font-medium text-sm">
                <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${open ? "" : "-rotate-90"}`} />
                {date ? new Date(date).toLocaleDateString() : "—"}
              </span>
              <span className="text-xs text-muted-foreground">{t("nValues", { count })}</span>
            </button>

            {open && (
              <div className="divide-y">
                {[...panelMap.entries()].map(([title, items]) => (
                  <div key={title}>
                    <div className="px-4 py-2 bg-muted/20 flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground">{title}</span>
                      <button
                        onClick={() => handleDeletePanel(items)}
                        disabled={pending}
                        title={t("DeletePanel")}
                        className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <table className="w-full text-sm">
                      <thead className="border-b bg-muted/10">
                        <tr>
                          <th className="px-4 py-2 text-left font-medium text-xs">{t("Parameter")}</th>
                          <th className="px-4 py-2 text-left font-medium text-xs">{t("Result")}</th>
                          <th className="px-4 py-2 text-left font-medium text-xs">{t("Reference")}</th>
                          <th className="px-4 py-2 text-left font-medium text-xs">{tc("Source")}</th>
                          <th className="px-4 py-2" />
                        </tr>
                      </thead>
                      <tbody className="divide-y">{paramRows(items)}</tbody>
                    </table>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
