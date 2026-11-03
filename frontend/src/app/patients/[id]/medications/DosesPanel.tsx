"use client";

import { useState, useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Check, CalendarPlus, Pencil, SlidersHorizontal, Trash2, X } from "lucide-react";
import { createDoses, deleteDose, updateDose, type S } from "@/lib/api";
import { formatDate, formatDose } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

type Medication = S<"MedicationDto">;
type Dose = S<"DoseDto">;
export type Draft = { id?: string; medication_id: string; when: string; other: boolean; given_by: string; amount: string; note: string };

export const inputCls = "mt-1 w-full rounded-lg border border-input bg-card px-3 py-2 text-sm";
const chipCls = "inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-800 dark:text-emerald-300";
// local wall time (ADR 060)
export const now = () => new Date().toLocaleString("sv").slice(0, 16).replace(" ", "T");
const MAX_DAYS = 62;

function days(from: string, to: string): string[] {
  const out: string[] = [];
  for (let d = new Date(`${from}T12:00`); d <= new Date(`${to}T12:00`) && out.length <= MAX_DAYS; d.setDate(d.getDate() + 1)) {
    out.push(d.toLocaleDateString("sv"));
  }
  return out;
}

export function DosesPanel({ patientId, medications, doses }: { patientId: string; medications: Medication[]; doses: Dose[] }) {
  const t = useTranslations("Dose");
  const locale = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [catchUp, setCatchUp] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const active = medications.filter((m) => m.is_active);
  const names = new Map(medications.map((m) => [m.id, m.medication_display]));
  const today = now().slice(0, 10);
  const giver = (d: Dose) => d.given_by ?? d.entered_by;
  const history = doses.filter((d) => !d.given_at.startsWith(today) && names.has(d.medication_id));
  const byDay = [...new Map(history.map((d) => [d.given_at.slice(0, 10), history.filter((x) => x.given_at.startsWith(d.given_at.slice(0, 10)))]))];

  function run(job: () => Promise<unknown>, done: () => void = () => {}) {
    setError("");
    startTransition(async () => {
      try {
        await job();
        done();
        router.refresh();
      } catch {
        setError(t("SaveError"));
      }
    });
  }

  function body(d: Draft): S<"DoseIn"> {
    return { medication_id: d.medication_id, given_at: d.when, given_by: d.other ? d.given_by.trim() || null : null,
             amount: d.amount.trim() || null, note: d.note.trim() || null };
  }

  function open(d?: Dose, medication_id?: string) {
    setConfirmDelete(false);
    setDraft(d ? { id: d.id, medication_id: d.medication_id, when: d.given_at, other: !!d.given_by, given_by: d.given_by ?? "",
                   amount: d.amount ?? "", note: d.note ?? "" }
               : { medication_id: medication_id ?? active[0]?.id ?? "", when: now(), other: false, given_by: "", amount: "", note: "" });
  }

  function save(e: React.FormEvent) {
    e.preventDefault();
    const d = draft!;
    run(() => (d.id ? updateDose(d.id, body(d)) : createDoses(patientId, [body(d)])), () => setDraft(null));
  }

  const chip = (d: Dose) => (
    <button key={d.id} type="button" onClick={() => d.can_edit && open(d)} disabled={!d.can_edit}
            className={`${chipCls} ${d.can_edit ? "cursor-pointer hover:bg-emerald-500/20" : ""}`}>
      <Check className="size-3" />{d.given_at.slice(11, 16)} {giver(d)}{d.amount && <> · {d.amount}</>}
    </button>
  );

  return (
    <section className="mb-6 rounded-xl border bg-card">
      <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
        <h2 className="text-sm font-semibold">{t("Today")}</h2>
        <Button variant="outline" size="sm" onClick={() => setCatchUp(true)} disabled={!active.length}>
          <CalendarPlus className="size-4" />{t("CatchUp")}
        </Button>
      </div>
      {error && <p className="px-4 pt-3 text-sm text-destructive">{error}</p>}
      <ul className="divide-y">
        {active.map((m) => {
          const todays = doses.filter((d) => d.medication_id === m.id && d.given_at.startsWith(today)).reverse();
          return (
            <li key={m.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{m.medication_display}</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {todays.length ? todays.map(chip) : <span className="text-xs text-muted-foreground">{t("NoneToday")}</span>}
                </div>
              </div>
              <div className="flex shrink-0 gap-1.5">
                <Button size="sm" disabled={pending} title={t("GivenTitle")}
                        onClick={() => run(() => createDoses(patientId, [{ medication_id: m.id, given_at: now() }]))}>
                  <Check className="size-4" />{t("Given")}
                </Button>
                <Button variant="outline" size="sm" disabled={pending} onClick={() => open(undefined, m.id)} aria-label={t("Details")} title={t("Details")}>
                  <SlidersHorizontal className="size-4" />
                </Button>
              </div>
            </li>
          );
        })}
      </ul>

      <details className="border-t px-4 py-3">
        <summary className="cursor-pointer text-sm font-medium">{t("History")}</summary>
        {byDay.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">{t("NoHistory")}</p> : (
          <div className="mt-2 space-y-3">
            {byDay.map(([day, list]) => (
              <div key={day}>
                <div className="text-xs font-medium text-muted-foreground">{formatDate(day, locale)}</div>
                <ul className="mt-1 space-y-1">
                  {list.map((d) => (
                    <li key={d.id} className="flex items-start gap-2 text-sm">
                      <span className="w-12 shrink-0 tabular-nums">{d.given_at.slice(11, 16)}</span>
                      <span className="min-w-0 flex-1">
                        {names.get(d.medication_id)}{d.amount && <>, {d.amount}</>}
                        <span className="text-muted-foreground"> · {giver(d)}{d.given_by && <> ({t("EnteredBy", { name: d.entered_by })})</>}</span>
                        {d.note && <span className="block text-xs text-muted-foreground">{d.note}</span>}
                      </span>
                      {d.can_edit && (
                        <button type="button" onClick={() => open(d)} aria-label={t("EditTitle")} className="cursor-pointer text-muted-foreground hover:text-foreground">
                          <Pencil className="size-4" />
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </details>

      <Dialog open={!!draft} onOpenChange={(v) => !pending && !v && setDraft(null)}>
        <DialogContent>
          {draft && (
            <form onSubmit={save}>
              <DialogHeader>
                <DialogTitle>{draft.id ? t("EditTitle") : t("NewTitle")}</DialogTitle>
              </DialogHeader>
              <div className="space-y-3 px-6">
                <Fields t={t} draft={draft} setDraft={setDraft} medications={draft.id ? medications : active} />
              </div>
              <DialogFooter>
                {draft.id && (
                  <Button type="button" variant="outline" size="sm" disabled={pending} className="mr-auto text-destructive"
                          onClick={() => confirmDelete ? run(() => deleteDose(draft.id!), () => setDraft(null)) : setConfirmDelete(true)}>
                    <Trash2 className="size-4" />{confirmDelete ? t("DeleteConfirm") : t("Delete")}
                  </Button>
                )}
                <Button type="button" variant="outline" size="sm" onClick={() => setDraft(null)} disabled={pending}>{t("Cancel")}</Button>
                <Button type="submit" size="sm" disabled={pending || !draft.when || (draft.other && !draft.given_by.trim())}>
                  {pending ? t("Saving") : t("Save")}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      {catchUp && (
        <CatchUp t={t} medications={active} doses={doses} pending={pending} error={error}
                 onClose={() => setCatchUp(false)}
                 onSave={(items) => run(() => createDoses(patientId, items), () => setCatchUp(false))} />
      )}
    </section>
  );
}

type T = ReturnType<typeof useTranslations>;

export function Fields({ t, draft, setDraft, medications, when = true }: {
  t: T; draft: Draft; setDraft: (d: Draft) => void; medications: Medication[]; when?: boolean;
}) {
  const plan = medications.find((m) => m.id === draft.medication_id);
  const set = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });
  return (
    <>
      <label className="block text-sm font-medium">{t("Medication")}
        <select value={draft.medication_id} onChange={(e) => set({ medication_id: e.target.value })} className={inputCls}>
          {medications.map((m) => <option key={m.id} value={m.id}>{m.medication_display}</option>)}
        </select>
      </label>
      {when && (
        <label className="block text-sm font-medium">{t("When")}
          <input type="datetime-local" required value={draft.when} max={now()} onChange={(e) => set({ when: e.target.value })} className={inputCls} />
        </label>
      )}
      <fieldset className="text-sm">
        <legend className="font-medium">{t("GivenBy")}</legend>
        <div className="mt-1 flex gap-4">
          <label className="flex items-center gap-1.5"><input type="radio" checked={!draft.other} onChange={() => set({ other: false })} />{t("Me")}</label>
          <label className="flex items-center gap-1.5"><input type="radio" checked={draft.other} onChange={() => set({ other: true })} />{t("Someone")}</label>
        </div>
        {draft.other && (
          <input value={draft.given_by} onChange={(e) => set({ given_by: e.target.value })} maxLength={256} required
                 placeholder={t("SomeonePlaceholder")} aria-label={t("GivenBy")} className={inputCls} />
        )}
      </fieldset>
      <label className="block text-sm font-medium">{t("Amount")}
        <input value={draft.amount} onChange={(e) => set({ amount: e.target.value })} maxLength={256}
               placeholder={plan && formatDose(plan) ? t("AmountPlaceholder", { plan: formatDose(plan) }) : t("AmountPlanned")} className={inputCls} />
      </label>
      <label className="block text-sm font-medium">{t("Note")}
        <textarea value={draft.note} onChange={(e) => set({ note: e.target.value })} rows={2} className={inputCls} />
      </label>
    </>
  );
}

function CatchUp({ t, medications, doses, pending, error, onClose, onSave }: {
  t: T; medications: Medication[]; doses: Dose[]; pending: boolean; error: string;
  onClose: () => void; onSave: (items: S<"DoseIn">[]) => void;
}) {
  const locale = useLocale();
  const [draft, setDraft] = useState<Draft>({ medication_id: medications[0]?.id ?? "", when: "", other: false, given_by: "", amount: "", note: "" });
  const [range, setRange] = useState(() => {
    const yesterday = new Date(Date.now() - 86400000).toLocaleDateString("sv");
    return { from: yesterday, to: yesterday };
  });
  const [times, setTimes] = useState(["08:00"]);
  const [dropped, setDropped] = useState<Set<string>>(new Set());

  // ADR 060: one Dose per day and time, nothing in the future, a recorded one is offered unticked
  const limit = now();
  const recorded = new Set(doses.filter((d) => d.medication_id === draft.medication_id).map((d) => d.given_at));
  const slots = range.from && range.to && range.from <= range.to
    ? days(range.from, range.to).flatMap((d) => [...new Set(times.filter(Boolean))].sort().map((tm) => `${d}T${tm}`)).filter((s) => s <= limit)
    : [];
  const tooLong = range.from && range.to && days(range.from, range.to).length > MAX_DAYS;
  const off = (s: string) => dropped.has(s) !== recorded.has(s);
  const chosen = slots.filter((s) => !off(s));
  const toggle = (s: string) => setDropped((prev) => { const n = new Set(prev); if (n.has(s)) n.delete(s); else n.add(s); return n; });

  function save(e: React.FormEvent) {
    e.preventDefault();
    const given_by = draft.other ? draft.given_by.trim() || null : null;
    onSave(chosen.map((s) => ({ medication_id: draft.medication_id, given_at: s, given_by,
                                amount: draft.amount.trim() || null, note: draft.note.trim() || null })));
  }

  return (
    <Dialog open onOpenChange={(v) => !pending && !v && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-md overflow-y-auto">
        <form onSubmit={save}>
          <DialogHeader>
            <DialogTitle>{t("CatchUpTitle")}</DialogTitle>
            <DialogDescription>{t("CatchUpHint")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 px-6">
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-sm font-medium">{t("From")}
                <input type="date" required value={range.from} max={limit.slice(0, 10)} onChange={(e) => setRange({ ...range, from: e.target.value })} className={inputCls} />
              </label>
              <label className="block text-sm font-medium">{t("To")}
                <input type="date" required value={range.to} max={limit.slice(0, 10)} onChange={(e) => setRange({ ...range, to: e.target.value })} className={inputCls} />
              </label>
            </div>
            <fieldset className="text-sm">
              <legend className="font-medium">{t("Times")}</legend>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                {times.map((tm, i) => (
                  <span key={i} className="inline-flex items-center gap-1">
                    <input type="time" required value={tm} aria-label={t("Times")} className="rounded-lg border border-input bg-card px-2 py-1"
                           onChange={(e) => setTimes(times.map((x, j) => (j === i ? e.target.value : x)))} />
                    {times.length > 1 && (
                      <button type="button" onClick={() => setTimes(times.filter((_, j) => j !== i))} aria-label={t("RemoveTime")}
                              className="cursor-pointer text-muted-foreground hover:text-foreground"><X className="size-4" /></button>
                    )}
                  </span>
                ))}
                <Button type="button" variant="outline" size="sm" onClick={() => setTimes([...times, "20:00"])}>{t("AddTime")}</Button>
              </div>
            </fieldset>
            <Fields t={t} draft={draft} setDraft={setDraft} medications={medications} when={false} />
            {tooLong ? <p className="text-sm text-destructive">{t("TooLong", { n: MAX_DAYS })}</p> : slots.length > 0 && (
              <ul className="max-h-48 space-y-1 overflow-y-auto rounded-lg border p-2 text-sm">
                {slots.map((s) => (
                  <li key={s}>
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked={!off(s)} onChange={() => toggle(s)} />
                      {formatDate(s.slice(0, 10), locale)} {s.slice(11)}
                      {recorded.has(s) && <span className="text-xs text-muted-foreground">({t("AlreadyRecorded")})</span>}
                    </label>
                  </li>
                ))}
              </ul>
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={pending}>{t("Cancel")}</Button>
            <Button type="submit" size="sm" disabled={pending || !chosen.length || !!tooLong || (draft.other && !draft.given_by.trim())}>
              {pending ? t("Saving") : t("SaveCount", { n: chosen.length })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
