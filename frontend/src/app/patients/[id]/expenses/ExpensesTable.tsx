"use client";

import { useState, useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { formatDate } from "@/lib/utils";
import { confirmExpense, deleteExpense } from "@/lib/api";
import { Check, Trash2 } from "lucide-react";

const eur = (v: any) => `${Number(v ?? 0).toFixed(2)} €`;
const openOf = (e: any) => Number(e.amount ?? 0) - Number(e.reimbursed_amount ?? 0);

export function ExpensesTable({ expenses, summary }: { expenses: any[]; summary: any }) {
  const t = useTranslations("Exp");
  const locale = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  // Phone: cards + tap-reveal action bar, like medications and conditions — a
  // seven-column table can only lose against a 400px viewport.
  const [revealed, setRevealed] = useState<string | null>(null);

  function act(fn: () => Promise<unknown>) {
    startTransition(async () => { await fn(); router.refresh(); });
  }

  function StatusBadge({ proposed }: { proposed: boolean }) {
    return (
      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${proposed
        ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
        : "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"}`}>
        {proposed ? t("Proposed") : t("Confirmed")}
      </span>
    );
  }

  function Actions({ e, iconBar }: { e: any; iconBar?: boolean }) {
    const proposed = e.status === "proposed";
    return (
      <div className={iconBar ? "flex items-center justify-end gap-1 border-t bg-muted/30 px-2 py-1.5" : "flex items-center gap-1"}>
        {proposed && (
          <button disabled={pending} onClick={() => act(() => confirmExpense(e.id))} title={t("Confirm")}
            className="rounded-md p-1.5 text-green-600 hover:bg-green-500/10 disabled:opacity-50">
            <Check className="h-4 w-4" />
          </button>
        )}
        <button disabled={pending} onClick={() => act(() => deleteExpense(e.id))} title={t("Delete")}
          className="rounded-md p-1.5 text-destructive hover:bg-destructive/10 disabled:opacity-50">
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label={t("Total")} value={eur(summary.total)} />
          <Stat label={t("TotalReimbursed")} value={eur(summary.total_reimbursed)} />
          <Stat label={t("TotalOpen")} value={eur(summary.total_open)} strong />
          {summary.proposed_count > 0 && (
            <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300">
              {t("ProposedHint", { count: summary.proposed_count })}
            </div>
          )}
        </div>
      )}

      {/* Phone: cards */}
      <div className="space-y-3 lg:hidden">
        {expenses.map((e: any) => {
          const proposed = e.status === "proposed";
          const isOpen = revealed === e.id;
          return (
            <div key={e.id} className={`overflow-hidden rounded-xl border bg-card ${proposed ? "bg-amber-500/5" : ""}`}>
              <div className="p-4" onClick={() => setRevealed(isOpen ? null : e.id)}>
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0 truncate text-sm font-medium">{t(`cat.${e.category}`)}</span>
                  <span className="shrink-0 font-semibold tabular-nums">{eur(e.amount)}</span>
                </div>
                <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span className="min-w-0 truncate">
                    {e.incurred_on ? formatDate(e.incurred_on, locale) : "—"}{e.note ? ` · ${e.note}` : ""}
                  </span>
                  <StatusBadge proposed={proposed} />
                </div>
                {e.reimbursed_amount != null && (
                  <div className="mt-1 text-xs text-muted-foreground tabular-nums">
                    {t("Reimbursed")} {eur(e.reimbursed_amount)} · {t("Open")} {eur(openOf(e))}
                  </div>
                )}
              </div>
              {isOpen && <Actions e={e} iconBar />}
            </div>
          );
        })}
      </div>

      {/* Desktop: table */}
      <div className="hidden overflow-hidden rounded-xl border bg-card lg:block">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">{t("Date")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("Category")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("Note")}</th>
              <th className="px-4 py-3 text-right font-medium">{t("Amount")}</th>
              <th className="px-4 py-3 text-right font-medium">{t("Reimbursed")}</th>
              <th className="px-4 py-3 text-right font-medium">{t("Open")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("Status")}</th>
              <th className="w-px px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {expenses.map((e: any) => {
              const proposed = e.status === "proposed";
              return (
                <tr key={e.id} className={`transition-colors hover:bg-muted/30 ${proposed ? "bg-amber-500/5" : ""}`}>
                  <td className="px-4 py-3 text-muted-foreground">{e.incurred_on ? formatDate(e.incurred_on, locale) : "—"}</td>
                  <td className="px-4 py-3">{t(`cat.${e.category}`)}</td>
                  <td className="px-4 py-3 text-muted-foreground">{e.note || "—"}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right font-medium tabular-nums">{eur(e.amount)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-muted-foreground">{e.reimbursed_amount != null ? eur(e.reimbursed_amount) : "—"}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums">{eur(openOf(e))}</td>
                  <td className="px-4 py-3">
                    <StatusBadge proposed={proposed} />
                    <span className="ml-2 text-xs text-muted-foreground">{e.source === "pipeline" ? t("Extracted") : t("Manual")}</span>
                  </td>
                  <td className="w-px whitespace-nowrap px-4 py-3"><Actions e={e} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-xl border bg-card p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`tabular-nums ${strong ? "text-lg font-semibold" : "text-base font-medium"}`}>{value}</div>
    </div>
  );
}
