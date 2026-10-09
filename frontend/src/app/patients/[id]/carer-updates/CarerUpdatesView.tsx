"use client";

import { useState, useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { createCarerUpdate, createCorrespondent, deleteCarerUpdate, updateCarerUpdate } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { CarerUpdate } from "@/lib/carerUpdates";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const btnCls = "inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50";

type Correspondent = { id: string; name: string };
type Draft = { id?: string; source: string; person: string; day: string; text: string; retold: boolean };

const today = () => new Date().toLocaleDateString("sv"); // YYYY-MM-DD in local time

export function CarerUpdatesView({ patientId, updates, correspondents, children }: {
  patientId: string; updates: CarerUpdate[]; correspondents: Correspondent[]; children: React.ReactNode;
}) {
  const t = useTranslations("CarerUpdates");
  const locale = useLocale();
  const router = useRouter();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const sources = [...new Map(updates.map((u) => [u.correspondent_id, u.correspondent_name])).entries()];
  const shown = filter ? updates.filter((u) => u.correspondent_id === filter) : updates;

  function edit(u: CarerUpdate) {
    setDraft({ id: u.id, source: u.correspondent_name, person: u.person ?? "", day: u.day, text: u.text, retold: u.retold });
  }

  function save(e: React.FormEvent) {
    e.preventDefault();
    const d = draft!;
    setError("");
    startTransition(async () => {
      try {
        const name = d.source.trim();
        const known = correspondents.find((c) => c.name.toLowerCase() === name.toLowerCase());
        const correspondent_id = known?.id ?? (await createCorrespondent(name)).id;
        const data = { correspondent_id, person: d.person.trim() || null, day: d.day, text: d.text, retold: d.retold };
        await (d.id ? updateCarerUpdate(d.id, data) : createCarerUpdate(patientId, data));
        setDraft(null);
        router.refresh();
      } catch {
        setError(t("SaveError"));
      }
    });
  }

  function remove(u: CarerUpdate) {
    if (!confirm(t("DeleteConfirm"))) return;
    startTransition(async () => {
      try {
        await deleteCarerUpdate(u.id);
        router.refresh();
      } catch {
        setError(t("DeleteError"));
      }
    });
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        {children}
        {!draft && (
          <button onClick={() => setDraft({ source: "", person: "", day: today(), text: "", retold: false })} className={btnCls}>
            <Plus className="h-4 w-4" />
            {t("Add")}
          </button>
        )}
      </div>
      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      {draft && (
        <form onSubmit={save} className="mb-6 space-y-4 rounded-xl border bg-card p-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block space-y-1">
              <span className="text-sm font-semibold">{t("Source")}</span>
              <input required list="carer-sources" className={inputCls} value={draft.source} placeholder={t("SourcePlaceholder")}
                onChange={(e) => setDraft({ ...draft, source: e.target.value })} />
              <datalist id="carer-sources">
                {correspondents.map((c) => <option key={c.id} value={c.name} />)}
              </datalist>
            </label>
            <label className="block space-y-1">
              <span className="text-sm font-semibold">{t("Person")}</span>
              <input className={inputCls} value={draft.person} placeholder={t("PersonPlaceholder")}
                onChange={(e) => setDraft({ ...draft, person: e.target.value })} />
            </label>
            <label className="block space-y-1">
              <span className="text-sm font-semibold">{t("Day")}</span>
              <input required type="date" className={inputCls} value={draft.day}
                onChange={(e) => setDraft({ ...draft, day: e.target.value })} />
            </label>
          </div>
          <label className="block space-y-1">
            <span className="text-sm font-semibold">{t("Text")}</span>
            <textarea required className={inputCls} rows={5} value={draft.text}
              onChange={(e) => setDraft({ ...draft, text: e.target.value })} />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={draft.retold} onChange={(e) => setDraft({ ...draft, retold: e.target.checked })} />
            {t("RetoldLabel")}
          </label>
          <div className="flex gap-2">
            <button type="submit" disabled={pending} className={btnCls}>{t("Save")}</button>
            <button type="button" onClick={() => setDraft(null)} className="rounded-lg border px-3 py-1.5 text-sm">{t("Cancel")}</button>
          </div>
        </form>
      )}

      {sources.length > 1 && (
        <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label={t("Filter")}
          className="mb-4 rounded-lg border bg-background px-2 py-1.5 text-sm">
          <option value="">{t("AllSources")}</option>
          {sources.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
      )}

      {shown.length ? (
        <div className="space-y-3">
          {shown.map((u) => (
            <section key={u.id} className="rounded-xl border bg-card p-4">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
                <span className="font-semibold">{formatDate(u.day, locale)}</span>
                <span>{[u.correspondent_name, u.person].filter(Boolean).join(", ")}</span>
                {u.retold && <span className="rounded border px-1 text-xs text-muted-foreground">{t("Retold")}</span>}
                <span className="ml-auto flex gap-1">
                  <button onClick={() => edit(u)} aria-label={t("Edit")} className="rounded p-1 text-muted-foreground hover:text-foreground">
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button onClick={() => remove(u)} aria-label={t("Delete")} className="rounded p-1 text-muted-foreground hover:text-destructive">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm">{u.text}</p>
            </section>
          ))}
        </div>
      ) : (
        !draft && <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      )}
    </div>
  );
}
