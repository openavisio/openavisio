"use client";

import { useState, useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Check, Pencil, Pill, Plus, Trash2 } from "lucide-react";
import { createDoses, createIncident, deleteIncident, updateIncident, type S } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Fields, inputCls, now, type Draft as DoseDraft } from "../medications/DosesPanel";
import { IncidentNowButton } from "./IncidentNowButton";

type Incident = S<"IncidentDto">;
type Medication = S<"MedicationDto">;
type Dose = S<"DoseDto">;
type IncidentType = S<"IncidentIn">["incident_type"];
type Draft = { id?: string; incident_type: IncidentType; display: string; when: string; duration: string; actions: string; note: string };

export const TYPES: IncidentType[] = ["seizure", "fall", "allergic_reaction", "other"];

export function IncidentsView({ patientId, incidents, medications, doses, rescue, openId }: {
  patientId: string; incidents: Incident[]; medications: Medication[]; doses: Dose[]; rescue: string[]; openId?: string;
}) {
  const t = useTranslations("Incidents");
  const td = useTranslations("Dose");
  const locale = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<IncidentType | "">("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(() => {
    const i = openId ? incidents.find((x) => x.id === openId) : undefined;
    return i ? toDraft(i) : null;
  });
  const [dose, setDose] = useState<(DoseDraft & { incident_id: string }) | null>(null);
  // ADR 062: the same counts as the doctor Handout, no curve over time
  const [cutoffs] = useState(() => ({
    q: new Date(Date.now() - 91 * 86400000).toLocaleDateString("sv"),
    y: new Date(Date.now() - 365 * 86400000).toLocaleDateString("sv"),
  }));

  const label = (i: Incident) => i.incident_type_display || t(`types.${i.incident_type}`);
  const names = new Map(medications.map((m) => [m.id, m.medication_display]));
  const rescueSet = new Set(rescue);
  const active = medications.filter((m) => m.is_active);
  const doseChoices = [...active.filter((m) => rescueSet.has(m.id)), ...active.filter((m) => !rescueSet.has(m.id))];
  const suggestions = [...new Set(incidents.map((i) => i.incident_type_display).filter((d): d is string => !!d))];

  const counts = new Map<string, { q: number; y: number }>();
  for (const i of incidents) {
    if (i.occurred_at.slice(0, 10) < cutoffs.y) continue;
    const c = counts.get(label(i)) ?? { q: 0, y: 0 };
    c.y += 1;
    if (i.occurred_at.slice(0, 10) >= cutoffs.q) c.q += 1;
    counts.set(label(i), c);
  }
  const shown = incidents.filter((i) => !filter || i.incident_type === filter);
  const byMonth = [...new Map(shown.map((i) => [i.occurred_at.slice(0, 7), shown.filter((x) => x.occurred_at.startsWith(i.occurred_at.slice(0, 7)))]))];
  const monthName = (ym: string) => new Date(`${ym}-15T12:00`).toLocaleDateString(locale, { month: "long", year: "numeric" });

  function toDraft(i: Incident): Draft {
    return { id: i.id, incident_type: i.incident_type as IncidentType, display: i.incident_type_display ?? "", when: i.occurred_at,
             duration: i.duration_minutes?.toString() ?? "", actions: i.actions_taken ?? "", note: i.note ?? "" };
  }

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

  function close() {
    setDraft(null);
    if (openId) router.replace(`/patients/${patientId}/incidents`);
  }

  function save(e: React.FormEvent) {
    e.preventDefault();
    const d = draft!;
    const body: S<"IncidentIn"> = { incident_type: d.incident_type, incident_type_display: d.display.trim() || null,
                                    occurred_at: d.when, duration_minutes: d.duration ? Number(d.duration) : null,
                                    actions_taken: d.actions.trim() || null, note: d.note.trim() || null };
    run(() => (d.id ? updateIncident(d.id, body) : createIncident(patientId, body)), close);
  }

  function saveDose(e: React.FormEvent) {
    e.preventDefault();
    const d = dose!;
    run(() => createDoses(patientId, [{ medication_id: d.medication_id, given_at: d.when, incident_id: d.incident_id,
                                        given_by: d.other ? d.given_by.trim() || null : null,
                                        amount: d.amount.trim() || null, note: d.note.trim() || null }]), () => setDose(null));
  }

  const openNew = () => {
    setConfirmDelete(false);
    setDraft({ incident_type: incidents[0]?.incident_type as IncidentType ?? "seizure", display: "", when: now(), duration: "", actions: "", note: "" });
  };
  const openDose = (i: Incident) => setDose({ incident_id: i.id, medication_id: doseChoices[0]?.id ?? "",
                                              when: i.occurred_at.length === 16 ? i.occurred_at : now(), other: false,
                                              given_by: "", amount: "", note: "" });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <IncidentNowButton patientId={patientId} lastType={incidents[0]?.incident_type} />
        <Button variant="outline" onClick={openNew}><Plus className="size-4" />{t("Add")}</Button>
      </div>
      {error && !draft && !dose && <p className="text-sm text-destructive">{error}</p>}

      {counts.size > 0 && (
        <section className="rounded-xl border bg-card p-4">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr><th className="font-medium">{t("Type")}</th><th className="w-24 text-right font-medium">{t("Last3")}</th><th className="w-24 text-right font-medium">{t("Last12")}</th></tr>
            </thead>
            <tbody>
              {[...counts].sort(([a], [b]) => a.localeCompare(b, locale)).map(([name, c]) => (
                <tr key={name}><td className="py-1">{name}</td><td className="text-right tabular-nums">{c.q}</td><td className="text-right tabular-nums">{c.y}</td></tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {incidents.length === 0 ? <p className="py-8 text-center text-muted-foreground">{t("Empty")}</p> : (
        <section className="rounded-xl border bg-card">
          <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
            <h2 className="text-sm font-semibold">{t("All")}</h2>
            <select value={filter} onChange={(e) => setFilter(e.target.value as IncidentType | "")} aria-label={t("Filter")}
                    className="rounded-lg border border-input bg-card px-2 py-1 text-sm">
              <option value="">{t("AllTypes")}</option>
              {TYPES.map((ty) => <option key={ty} value={ty}>{t(`types.${ty}`)}</option>)}
            </select>
          </div>
          {byMonth.map(([month, list]) => (
            <div key={month} className="border-b px-4 py-3 last:border-b-0">
              <div className="mb-2 text-xs font-medium text-muted-foreground">{monthName(month)}</div>
              <ul className="space-y-3">
                {list.map((i) => {
                  const given = doses.filter((d) => d.incident_id === i.id);
                  return (
                    <li key={i.id} className="flex items-start gap-3 text-sm">
                      <span className="w-24 shrink-0 tabular-nums text-muted-foreground">
                        {formatDate(i.occurred_at.slice(0, 10), locale)}{i.occurred_at.length > 10 && <> {i.occurred_at.slice(11, 16)}</>}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">{label(i)}{i.duration_minutes != null && <span className="font-normal text-muted-foreground"> · {t("Minutes", { n: i.duration_minutes })}</span>}</div>
                        {i.actions_taken && <div>{i.actions_taken}</div>}
                        {i.note && <div className="whitespace-pre-line text-muted-foreground">{i.note}</div>}
                        {given.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1.5">
                            {given.map((d) => (
                              <span key={d.id} className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-800 dark:text-emerald-300">
                                <Check className="size-3" />{d.given_at.slice(11, 16)} {names.get(d.medication_id)}{d.amount && <> · {d.amount}</>} · {d.given_by ?? d.entered_by}
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground">{t("EnteredBy", { name: i.entered_by })}</div>
                      </div>
                      <div className="flex shrink-0 gap-1">
                        {doseChoices.length > 0 && (
                          <Button variant="outline" size="sm" onClick={() => openDose(i)} title={t("AddDose")} aria-label={t("AddDose")}>
                            <Pill className="size-4" />
                          </Button>
                        )}
                        {i.can_edit && (
                          <Button variant="outline" size="sm" onClick={() => { setConfirmDelete(false); setDraft(toDraft(i)); }} aria-label={t("Edit")} title={t("Edit")}>
                            <Pencil className="size-4" />
                          </Button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </section>
      )}

      <Dialog open={!!draft} onOpenChange={(v) => !pending && !v && close()}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          {draft && (
            <form onSubmit={save}>
              <DialogHeader><DialogTitle>{draft.id ? t("Edit") : t("Add")}</DialogTitle></DialogHeader>
              <div className="space-y-3 px-6">
                <label className="block text-sm font-medium">{t("Type")}
                  <select value={draft.incident_type} onChange={(e) => setDraft({ ...draft, incident_type: e.target.value as IncidentType })} className={inputCls}>
                    {TYPES.map((ty) => <option key={ty} value={ty}>{t(`types.${ty}`)}</option>)}
                  </select>
                </label>
                <label className="block text-sm font-medium">{t("Display")}
                  <input value={draft.display} onChange={(e) => setDraft({ ...draft, display: e.target.value })} maxLength={256}
                         list="incident-labels" placeholder={t("DisplayPlaceholder")} className={inputCls} />
                  <datalist id="incident-labels">{suggestions.map((s) => <option key={s} value={s} />)}</datalist>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block text-sm font-medium">{t("When")}
                    <input type="datetime-local" required value={draft.when} max={now()} onChange={(e) => setDraft({ ...draft, when: e.target.value })} className={inputCls} />
                  </label>
                  <label className="block text-sm font-medium">{t("Duration")}
                    <input type="number" min={0} inputMode="numeric" value={draft.duration} onChange={(e) => setDraft({ ...draft, duration: e.target.value })} className={inputCls} />
                  </label>
                </div>
                <label className="block text-sm font-medium">{t("Actions")}
                  <textarea value={draft.actions} onChange={(e) => setDraft({ ...draft, actions: e.target.value })} rows={2} className={inputCls} />
                </label>
                <label className="block text-sm font-medium">{t("Note")}
                  <textarea value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} rows={3} className={inputCls} />
                </label>
                {error && <p className="text-sm text-destructive">{error}</p>}
              </div>
              <DialogFooter>
                {draft.id && (
                  <Button type="button" variant="outline" size="sm" disabled={pending} className="mr-auto text-destructive"
                          onClick={() => confirmDelete ? run(() => deleteIncident(draft.id!), close) : setConfirmDelete(true)}>
                    <Trash2 className="size-4" />{confirmDelete ? t("DeleteConfirm") : t("Delete")}
                  </Button>
                )}
                <Button type="button" variant="outline" size="sm" onClick={close} disabled={pending}>{t("Cancel")}</Button>
                <Button type="submit" size="sm" disabled={pending || !draft.when.match(/T\d\d:\d\d$/)}>{pending ? t("Saving") : t("Save")}</Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!dose} onOpenChange={(v) => !pending && !v && setDose(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          {dose && (
            <form onSubmit={saveDose}>
              <DialogHeader><DialogTitle>{t("AddDose")}</DialogTitle></DialogHeader>
              <div className="space-y-3 px-6">
                <Fields t={td} draft={dose} setDraft={(d) => setDose({ ...d, incident_id: dose.incident_id })} medications={doseChoices} />
                {error && <p className="text-sm text-destructive">{error}</p>}
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" size="sm" onClick={() => setDose(null)} disabled={pending}>{t("Cancel")}</Button>
                <Button type="submit" size="sm" disabled={pending || !dose.when || (dose.other && !dose.given_by.trim())}>{pending ? t("Saving") : t("Save")}</Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
