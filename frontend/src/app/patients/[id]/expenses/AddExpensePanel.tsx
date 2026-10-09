"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { createExpense, exportExpensesCsv } from "@/lib/api";
import { Plus, X, Download } from "lucide-react";

export const EXPENSE_CATEGORIES = ["pflegehilfsmittel", "medication_copay", "therapy", "aid", "travel", "other"] as const;

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

export function AddExpensePanel({ patientId, children }: { patientId: string; children: React.ReactNode }) {
  const t = useTranslations("Exp");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [category, setCategory] = useState<string>("other");
  const [note, setNote] = useState("");
  const [reimbursed, setReimbursed] = useState("");
  const [error, setError] = useState("");

  function reset() {
    setAmount(""); setDate(""); setCategory("other"); setNote(""); setReimbursed(""); setError("");
  }
  function close() { reset(); setOpen(false); }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        await createExpense(patientId, {
          amount,  // string preserves decimal exactness for the backend's Numeric column
          incurred_on: date || undefined,
          category,
          note: note || undefined,
          reimbursed_amount: reimbursed || undefined,
        });
        close();
        router.refresh();
      } catch {
        setError(t("AddError"));
      }
    });
  }

  async function downloadCsv() {
    const csv = await exportExpensesCsv(patientId);
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "expenses.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between">
        {children}
        <div className="flex items-center gap-2">
          <button
            onClick={downloadCsv}
            className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted transition-colors"
          >
            <Download className="h-4 w-4" />
            {t("ExportCsv")}
          </button>
          <button
            onClick={() => setOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            {t("AddTitle")}
          </button>
        </div>
      </div>

      {open && (
        <div className="rounded-xl border bg-card p-4 mt-4">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-semibold">{t("AddTitle")}</span>
            <button onClick={close} className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>

          {error && (
            <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm mb-4">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  {t("Amount")} (€) <span className="text-destructive">*</span>
                </label>
                <input type="number" required min="0" step="0.01" value={amount}
                  onChange={(e) => setAmount(e.target.value)} className={inputCls} placeholder="0.00" />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("Date")}</label>
                <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputCls} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("Category")}</label>
                <select value={category} onChange={(e) => setCategory(e.target.value)} className={inputCls}>
                  {EXPENSE_CATEGORIES.map((c) => <option key={c} value={c}>{t(`cat.${c}`)}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("Reimbursed")} (€)</label>
                <input type="number" min="0" step="0.01" value={reimbursed}
                  onChange={(e) => setReimbursed(e.target.value)} className={inputCls} placeholder="0.00" />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("Note")}</label>
              <input type="text" value={note} onChange={(e) => setNote(e.target.value)}
                className={inputCls} placeholder={t("NotePlaceholder")} />
            </div>

            <div className="flex items-center gap-3 pt-1">
              <button type="submit" disabled={pending}
                className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50">
                {pending ? t("Adding") : t("Submit")}
              </button>
              <button type="button" onClick={close}
                className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors">
                {t("Cancel")}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
