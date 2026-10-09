"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Check, Download, FilePlus2, Loader2, Pencil, Printer, RefreshCw, Send, Trash2 } from "lucide-react";
import {
  answerIntakeItem, deleteIntakeForm, releaseIntakeForm, retryIntakeForm, reviseIntakeForm,
} from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { AGINGS, type Aging, type IntakeFormDetail, type IntakeItem } from "@/lib/intake";
import { STATUS_CLS } from "../IntakeFormsView";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const btnCls = "inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50";
const ghostCls = "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50";

export function SheetView({ patientId, form, children }: {
  patientId: string; form: IntakeFormDetail; children: React.ReactNode;
}) {
  const t = useTranslations("IntakeForms");
  const locale = useLocale();
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const draft = form.status === "draft";

  useEffect(() => {
    if (form.status !== "reading") return;
    const id = setInterval(() => router.refresh(), 5000);
    return () => clearInterval(id);
  }, [form.status, router]);

  function run<T>(action: () => Promise<T>, then?: (r: T) => void) {
    setError("");
    startTransition(async () => {
      try {
        const r = await action();
        if (then) then(r);
        else router.refresh();
      } catch {
        setError(t("ActionError"));
      }
    });
  }

  const unconfirmed = form.items.filter((i) => i.answer && !i.confirmed).length;
  const base = `/patients/${patientId}/intake-forms`;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {children}
        <span className={`rounded px-2 py-0.5 text-xs ${STATUS_CLS[form.status]}`}>{t(`Status.${form.status}`)}</span>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <a href={`/api/intake-forms/${form.id}/file`} className={ghostCls}><Download className="h-4 w-4" />{t("Original")}</a>
        {(draft || form.status === "released") && (
          <Link href={`${base}/${form.id}/print`} className={ghostCls}><Printer className="h-4 w-4" />{t("Print")}</Link>
        )}
        {draft && (
          <button disabled={pending} className={btnCls}
            onClick={() => confirm(t("ReleaseConfirm", { open: unconfirmed })) && run(() => releaseIntakeForm(form.id))}>
            <Send className="h-4 w-4" />{t("Release")}
          </button>
        )}
        {form.status === "released" && (
          <button disabled={pending} className={ghostCls}
            onClick={() => run(() => reviseIntakeForm(form.id), (f) => router.push(`${base}/${f.id}`))}>
            <FilePlus2 className="h-4 w-4" />{t("Revise")}
          </button>
        )}
        <button disabled={pending} className={`${ghostCls} ml-auto text-destructive`}
          onClick={() => confirm(t("DeleteConfirm")) && run(() => deleteIntakeForm(form.id), () => router.push(base))}>
          <Trash2 className="h-4 w-4" />{t("Delete")}
        </button>
      </div>
      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      {form.status === "reading" && (
        <div className="flex items-center gap-2 rounded-xl border bg-card p-4 text-sm">
          <Loader2 className="h-4 w-4 animate-spin" />{t("Reading")}
        </div>
      )}
      {form.status === "failed" && (
        <div className="space-y-3 rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm">
          <p>{t("Failed")}</p>
          <button disabled={pending} className={ghostCls} onClick={() => run(() => retryIntakeForm(form.id))}>
            <RefreshCw className="h-4 w-4" />{t("Retry")}
          </button>
        </div>
      )}
      {draft && <p className="mb-6 text-sm text-muted-foreground">{t("DraftHint")}</p>}
      {form.status === "released" && (
        <p className="mb-6 text-sm text-muted-foreground">{t("ReleasedHint", { date: formatDate(form.released_at, locale) })}</p>
      )}

      <div className="space-y-3">
        {form.items.map((item, i) => (
          <div key={i}>
            {item.section && item.section !== form.items[i - 1]?.section && (
              <h2 className="mb-2 mt-6 text-sm font-semibold uppercase tracking-wide text-muted-foreground">{item.section}</h2>
            )}
            <ItemCard item={item} draft={draft} pending={pending} patientId={patientId}
              onSave={(body) => run(() => answerIntakeItem(form.id, i, body))} />
          </div>
        ))}
      </div>
    </div>
  );
}

function ItemCard({ item, draft, pending, patientId, onSave }: {
  item: IntakeItem; draft: boolean; pending: boolean; patientId: string;
  onSave: (body: { answer?: string | null; aging?: Aging; confirm?: boolean }) => void;
}) {
  const t = useTranslations("IntakeForms");
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(item.answer ?? "");
  const judgement = item.kind === "judgement";
  const segments = [...new Set(item.sources.map((s) => s.segment).filter(Boolean))] as string[];

  return (
    <section className="rounded-xl border bg-card p-4 text-sm">
      <div className="flex flex-wrap items-start gap-2">
        <p className="font-semibold">{item.text}</p>
        {judgement && <span className="rounded border px-1 text-xs text-muted-foreground">{t("Judgement")}</span>}
        {draft && !judgement && (
          <select value={item.aging} disabled={pending} aria-label={t("AgingLabel")}
            onChange={(e) => onSave({ aging: e.target.value as Aging })}
            className="ml-auto rounded border bg-background px-1 py-0.5 text-xs">
            {AGINGS.map((a) => <option key={a} value={a}>{t("AgingLabel")}: {t(`Aging.${a}`)}</option>)}
          </select>
        )}
      </div>

      {editing ? (
        <form className="mt-2 space-y-2" onSubmit={(e) => { e.preventDefault(); onSave({ answer: text }); setEditing(false); }}>
          <textarea autoFocus rows={2} className={inputCls} value={text} aria-label={t("Answer")}
            onChange={(e) => setText(e.target.value)} />
          <div className="flex gap-2">
            <button type="submit" disabled={pending} className={btnCls}>{t("Save")}</button>
            <button type="button" onClick={() => setEditing(false)} className={ghostCls}>{t("Cancel")}</button>
          </div>
        </form>
      ) : (
        <div className="mt-2 flex items-start gap-2">
          <p className={`whitespace-pre-wrap ${item.answer ? "" : "text-muted-foreground"} ${item.confirmed ? "" : "italic"}`}>
            {item.answer ?? (draft ? t("Open") : "—")}
          </p>
          {draft && (
            <span className="ml-auto flex shrink-0 gap-1">
              {item.answer && !item.confirmed && (
                <button disabled={pending} onClick={() => onSave({ confirm: true })} className={ghostCls}>
                  <Check className="h-4 w-4" />{t("Confirm")}
                </button>
              )}
              <button onClick={() => { setText(item.answer ?? ""); setEditing(true); }} aria-label={t("Edit")}
                className="rounded p-1 text-muted-foreground hover:text-foreground">
                <Pencil className="h-4 w-4" />
              </button>
            </span>
          )}
        </div>
      )}

      <div className="mt-2 space-y-1 text-xs text-muted-foreground">
        {judgement && draft && <p>{t("JudgementHint")}</p>}
        {item.related.length > 0 && (
          <div>
            <p>{t("Related")}</p>
            <ul className="ml-4 list-disc">{item.related.map((r, j) => <li key={j}>{r}</li>)}</ul>
          </div>
        )}
        {item.answer && (item.origin === "record" || item.origin === "history") && (
          <div>
            <p>{t(item.origin === "history" ? "FromHistory" : "FromRecord")}</p>
            <ul className="ml-4 list-disc">{item.sources.map((s, j) => <li key={j}>{s.text}</li>)}</ul>
          </div>
        )}
        {item.origin === "document" && item.document && (
          <div>
            <p>{t("FromDocument")}{" "}
              <Link href={`/patients/${patientId}/documents/${item.document.id}`} className="underline">{item.document.file_name}</Link>
            </p>
            {item.passage && (
              <details><summary className="cursor-pointer">{t("ShowPassage")}</summary>
                <p className="mt-1 whitespace-pre-wrap">{item.passage}</p>
              </details>
            )}
          </div>
        )}
        {item.origin === "caregiver" && !item.record_corrected && <p>{t("FromCaregiver")}</p>}
        {item.answer && !item.confirmed && <p>{t("Unconfirmed")}</p>}
        {item.record_corrected && (
          <p>{t("RecordCorrected")}{" "}
            {segments.map((s) => (
              <Link key={s} href={`/patients/${patientId}/${s}`} className="mr-2 underline">{t("ChangeInRecord")}</Link>
            ))}
          </p>
        )}
      </div>
    </section>
  );
}
