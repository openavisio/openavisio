"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Pencil, Trash2 } from "lucide-react";
import { deleteHistoryFact, updateHistoryFact } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { AGINGS, type Aging, type HistoryFact } from "@/lib/intake";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const btnCls = "inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50";

// No "add" here: a History Fact only comes into being through a form's question (ADR 047).
export function HistoryFactsView({ patientId, facts }: { patientId: string; facts: HistoryFact[] }) {
  const t = useTranslations("HistoryFacts");
  const ti = useTranslations("IntakeForms");
  const locale = useLocale();
  const router = useRouter();
  const [draft, setDraft] = useState<{ id: string; answer: string; aging: Aging } | null>(null);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  function save(e: React.FormEvent) {
    e.preventDefault();
    const d = draft!;
    setError("");
    startTransition(async () => {
      try {
        await updateHistoryFact(d.id, { answer: d.answer, aging: d.aging });
        setDraft(null);
        router.refresh();
      } catch {
        setError(t("SaveError"));
      }
    });
  }

  function remove(f: HistoryFact) {
    if (!confirm(t("DeleteConfirm"))) return;
    startTransition(async () => {
      try {
        await deleteHistoryFact(f.id);
        router.refresh();
      } catch {
        setError(t("DeleteError"));
      }
    });
  }

  if (!facts.length) return <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>;

  return (
    <div className="space-y-3">
      {error && <p className="text-sm text-destructive">{error}</p>}
      {facts.map((f) => (
        <section key={f.id} className="rounded-xl border bg-card p-4 text-sm">
          <div className="flex flex-wrap items-start gap-2">
            <p className="font-semibold">{f.question}</p>
            <span className="ml-auto flex gap-1">
              <button onClick={() => setDraft({ id: f.id, answer: f.answer, aging: f.aging })} aria-label={t("Edit")}
                className="rounded p-1 text-muted-foreground hover:text-foreground">
                <Pencil className="h-4 w-4" />
              </button>
              <button onClick={() => remove(f)} aria-label={t("Delete")}
                className="rounded p-1 text-muted-foreground hover:text-destructive">
                <Trash2 className="h-4 w-4" />
              </button>
            </span>
          </div>
          {draft?.id === f.id ? (
            <form onSubmit={save} className="mt-2 space-y-2">
              <textarea required autoFocus rows={2} className={inputCls} value={draft.answer}
                onChange={(e) => setDraft({ ...draft, answer: e.target.value })} />
              <select value={draft.aging} aria-label={ti("AgingLabel")} className="rounded border bg-background px-2 py-1 text-sm"
                onChange={(e) => setDraft({ ...draft, aging: e.target.value as Aging })}>
                {AGINGS.map((a) => <option key={a} value={a}>{ti("AgingLabel")}: {ti(`Aging.${a}`)}</option>)}
              </select>
              <div className="flex gap-2">
                <button type="submit" disabled={pending} className={btnCls}>{t("Save")}</button>
                <button type="button" onClick={() => setDraft(null)} className="rounded-lg border px-3 py-1.5 text-sm">{t("Cancel")}</button>
              </div>
            </form>
          ) : (
            <p className="mt-2 whitespace-pre-wrap">{f.answer}</p>
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            {[ti(`Aging.${f.aging}`), t("ConfirmedOn", { date: formatDate(f.confirmed_on, locale) })].join(" · ")}{" · "}
            {f.document_reference_id ? (
              <Link href={`/patients/${patientId}/documents/${f.document_reference_id}`} className="underline">{t("Source.document")}</Link>
            ) : t(`Source.${f.source}`)}
          </p>
        </section>
      ))}
    </div>
  );
}
