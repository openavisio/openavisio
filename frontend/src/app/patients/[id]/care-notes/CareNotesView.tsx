"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Pencil, Plus } from "lucide-react";
import { saveCareNotes } from "@/lib/api";
import { CARE_NOTE_HEADINGS, type CareNotes } from "@/lib/careNotes";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const btnCls = "inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50";

const empty = Object.fromEntries(CARE_NOTE_HEADINGS.map((h) => [h, null])) as CareNotes;

export function CareNotesView({ patientId, notes, children }: { patientId: string; notes: CareNotes | null; children: React.ReactNode }) {
  const t = useTranslations("CareNotes");
  const router = useRouter();
  const [draft, setDraft] = useState<CareNotes | null>(null);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const filled = CARE_NOTE_HEADINGS.filter((h) => notes?.[h]);

  function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        await saveCareNotes(patientId, draft!);
        setDraft(null);
        router.refresh();
      } catch {
        setError(t("SaveError"));
      }
    });
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        {children}
        {!draft && (
          <button onClick={() => setDraft(notes ?? empty)} className={btnCls}>
            {filled.length ? <Pencil className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            {filled.length ? t("Edit") : t("Create")}
          </button>
        )}
      </div>

      {draft ? (
        <form onSubmit={save} className="space-y-4">
          {CARE_NOTE_HEADINGS.map((h) => (
            <label key={h} className="block space-y-1">
              <span className="text-sm font-semibold">{t(`h.${h}`)}</span>
              <textarea className={inputCls} rows={3} value={draft[h] ?? ""}
                onChange={(e) => setDraft({ ...draft, [h]: e.target.value })} />
            </label>
          ))}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={pending} className={btnCls}>{t("Save")}</button>
            <button type="button" onClick={() => setDraft(null)} className="rounded-lg border px-3 py-1.5 text-sm">{t("Cancel")}</button>
          </div>
        </form>
      ) : filled.length ? (
        <div className="space-y-4">
          {filled.map((h) => (
            <section key={h} className="rounded-xl border bg-card p-4">
              <h2 className="font-semibold">{t(`h.${h}`)}</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm">{notes![h]}</p>
            </section>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      )}
    </div>
  );
}
