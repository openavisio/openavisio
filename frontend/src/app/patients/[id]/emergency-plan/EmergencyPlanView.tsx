"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { AlertTriangle, FileText, Pencil, Phone, Plus, Trash2, X } from "lucide-react";
import { saveEmergencyPlan } from "@/lib/api";
import { formatDate, formatDose as dose } from "@/lib/utils";
import type { EmergencyPlan, EmergencyPlanInput, PlanDocument, PlanMedication, PlanStep } from "@/lib/emergencyPlan";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const btnCls = "inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50";
const linkBtnCls = "inline-flex items-center gap-1 text-sm text-primary hover:underline";

const docTitle = (d: PlanDocument) => d.description || d.file_name;

function Remove({ label, onClick, Icon = X }: { label: string; onClick: () => void; Icon?: typeof X }) {
  return (
    <button type="button" aria-label={label} onClick={onClick} className="text-muted-foreground hover:text-destructive">
      <Icon className="h-4 w-4" />
    </button>
  );
}

function toInput(plan: EmergencyPlan | null): EmergencyPlanInput {
  return {
    situations: plan?.situations ?? [],
    contacts: plan?.contacts ?? [],
    notes: plan?.notes ?? null,
    document_ids: (plan?.documents ?? []).map((d) => d.id),
  };
}

export function EmergencyPlanView({
  patientId, plan, medications, documents, children,
}: {
  patientId: string;
  plan: EmergencyPlan | null;
  medications: PlanMedication[];
  documents: PlanDocument[];
  children: React.ReactNode;
}) {
  const t = useTranslations("EmergencyPlan");
  const [editing, setEditing] = useState(false);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        {children}
        {!editing && (
          <button onClick={() => setEditing(true)} className={btnCls}>
            {plan ? <Pencil className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            {plan ? t("Edit") : t("Create")}
          </button>
        )}
      </div>
      {editing ? (
        <Editor patientId={patientId} plan={plan} medications={medications} documents={documents} onDone={() => setEditing(false)} />
      ) : plan ? (
        <Display patientId={patientId} plan={plan} />
      ) : (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      )}
    </div>
  );
}

function StepMedication({ step }: { step: PlanStep }) {
  const t = useTranslations("EmergencyPlan");
  if (!step.medication_id) return null;
  const m = step.medication;
  if (!m || !m.is_active) {
    return (
      <div className="mt-1 inline-flex items-center gap-1.5 rounded-md bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
        <AlertTriangle className="h-3.5 w-3.5" />
        {m ? t("MedicationStopped", { name: m.medication_display }) : t("MedicationDeleted")}
      </div>
    );
  }
  return (
    <div className="mt-1 inline-flex items-center gap-1.5 rounded-md bg-orange-500/10 px-2 py-0.5 text-xs font-medium text-orange-700 dark:text-orange-300">
      {m.medication_display}{dose(m) && `, ${dose(m)}`}{m.route && ` (${m.route})`}
    </div>
  );
}

function Display({ patientId, plan }: { patientId: string; plan: EmergencyPlan }) {
  const t = useTranslations("EmergencyPlan");
  const locale = useLocale();
  return (
    <div className="space-y-6">
      {plan.situations.map((s, i) => (
        <section key={i} className="rounded-xl border bg-card p-4">
          <h2 className="font-semibold text-red-600 dark:text-red-400">{s.trigger}</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm">
            {s.steps.map((st, j) => (
              <li key={j}>
                {st.text}
                {st.medication_id && <div><StepMedication step={st} /></div>}
              </li>
            ))}
          </ol>
        </section>
      ))}

      {plan.contacts.length > 0 && (
        <section className="rounded-xl border bg-card p-4">
          <h2 className="font-semibold">{t("Contacts")}</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {plan.contacts.map((c, i) => (
              <li key={i} className="flex flex-wrap items-center gap-x-3">
                <span className="font-medium">{c.name}</span>
                {c.role && <span className="text-muted-foreground">{c.role}</span>}
                {c.phone && (
                  <a href={`tel:${c.phone}`} className={linkBtnCls}>
                    <Phone className="h-3.5 w-3.5" />{c.phone}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {plan.notes && (
        <section className="rounded-xl border bg-card p-4">
          <h2 className="font-semibold">{t("Notes")}</h2>
          <p className="mt-3 whitespace-pre-wrap text-sm">{plan.notes}</p>
        </section>
      )}

      {plan.documents.length > 0 && (
        <section className="rounded-xl border bg-card p-4">
          <h2 className="font-semibold">{t("Documents")}</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {plan.documents.map((d) => (
              <li key={d.id}>
                <Link href={`/patients/${patientId}/documents/${d.id}`} className={linkBtnCls}>
                  <FileText className="h-3.5 w-3.5" />{docTitle(d)}
                </Link>
                <span className="ml-2 text-muted-foreground">
                  {[d.issued_date && formatDate(d.issued_date, locale), d.correspondent?.name || d.detected_provider].filter(Boolean).join(" · ")}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Editor({
  patientId, plan, medications, documents, onDone,
}: {
  patientId: string;
  plan: EmergencyPlan | null;
  medications: PlanMedication[];
  documents: PlanDocument[];
  onDone: () => void;
}) {
  const t = useTranslations("EmergencyPlan");
  const router = useRouter();
  const [draft, setDraft] = useState(() => toInput(plan));
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  const update = (fn: (d: EmergencyPlanInput) => void) =>
    setDraft((d) => { const next = structuredClone(d); fn(next); return next; });

  const chosenMeds = new Set(draft.situations.flatMap((s) => s.steps.map((st) => st.medication_id)));
  const medOptions = medications.filter((m) => m.is_active || chosenMeds.has(m.id));

  function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        await saveEmergencyPlan(patientId, {
          ...draft,
          situations: draft.situations
            .filter((s) => s.trigger.trim())
            .map((s) => ({ ...s, steps: s.steps.filter((st) => st.text.trim()) })),
          contacts: draft.contacts.filter((c) => c.name.trim()),
          notes: draft.notes?.trim() || null,
        });
        onDone();
        router.refresh();
      } catch {
        setError(t("SaveError"));
      }
    });
  }

  return (
    <form onSubmit={save} className="space-y-6">
      <section className="space-y-4">
        <h2 className="font-semibold">{t("Situations")}</h2>
        {draft.situations.map((s, i) => (
          <div key={i} className="space-y-3 rounded-xl border bg-card p-4">
            <div className="flex gap-2">
              <input className={inputCls} placeholder={t("TriggerPlaceholder")} value={s.trigger}
                onChange={(e) => update((d) => { d.situations[i].trigger = e.target.value; })} />
              <Remove label={t("RemoveSituation")} onClick={() => update((d) => { d.situations.splice(i, 1); })} Icon={Trash2} />
            </div>
            <ol className="space-y-2 pl-4">
              {s.steps.map((st, j) => (
                <li key={j} className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
                  <span className="w-5 text-sm text-muted-foreground">{j + 1}.</span>
                  <input className={inputCls} placeholder={t("StepPlaceholder")} value={st.text}
                    onChange={(e) => update((d) => { d.situations[i].steps[j].text = e.target.value; })} />
                  <select className={`${inputCls} sm:w-56`} aria-label={t("StepMedication")} value={st.medication_id ?? ""}
                    onChange={(e) => update((d) => { d.situations[i].steps[j].medication_id = e.target.value || null; })}>
                    <option value="">{t("NoMedication")}</option>
                    {medOptions.map((m) => (
                      <option key={m.id} value={m.id}>{m.medication_display}{dose(m) && `, ${dose(m)}`}</option>
                    ))}
                    {st.medication_id && !medications.some((m) => m.id === st.medication_id) && (
                      <option value={st.medication_id}>{t("MedicationDeleted")}</option>
                    )}
                  </select>
                  <Remove label={t("RemoveStep")} onClick={() => update((d) => { d.situations[i].steps.splice(j, 1); })} />
                </li>
              ))}
            </ol>
            <button type="button" className={linkBtnCls}
              onClick={() => update((d) => { d.situations[i].steps.push({ text: "", medication_id: null }); })}>
              <Plus className="h-3.5 w-3.5" />{t("AddStep")}
            </button>
          </div>
        ))}
        <button type="button" className={linkBtnCls}
          onClick={() => update((d) => { d.situations.push({ trigger: "", steps: [{ text: "", medication_id: null }] }); })}>
          <Plus className="h-3.5 w-3.5" />{t("AddSituation")}
        </button>
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">{t("Contacts")}</h2>
        {draft.contacts.map((c, i) => (
          <div key={i} className="flex flex-wrap gap-2 sm:flex-nowrap">
            <input className={inputCls} placeholder={t("ContactName")} value={c.name}
              onChange={(e) => update((d) => { d.contacts[i].name = e.target.value; })} />
            <input className={inputCls} placeholder={t("ContactRole")} value={c.role ?? ""}
              onChange={(e) => update((d) => { d.contacts[i].role = e.target.value || null; })} />
            <input className={inputCls} type="tel" placeholder={t("ContactPhone")} value={c.phone ?? ""}
              onChange={(e) => update((d) => { d.contacts[i].phone = e.target.value || null; })} />
            <Remove label={t("RemoveContact")} onClick={() => update((d) => { d.contacts.splice(i, 1); })} Icon={Trash2} />
          </div>
        ))}
        <button type="button" className={linkBtnCls}
          onClick={() => update((d) => { d.contacts.push({ name: "", role: null, phone: null }); })}>
          <Plus className="h-3.5 w-3.5" />{t("AddContact")}
        </button>
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">{t("Notes")}</h2>
        <textarea className={inputCls} rows={4} value={draft.notes ?? ""}
          onChange={(e) => update((d) => { d.notes = e.target.value; })} />
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">{t("Documents")}</h2>
        <p className="text-sm text-muted-foreground">{t("DocumentsHint")}</p>
        {draft.document_ids.map((docId, i) => {
          const d = documents.find((x) => x.id === docId);
          return (
            <div key={docId} className="flex items-center gap-2 text-sm">
              <FileText className="h-3.5 w-3.5" />
              <span>{d ? docTitle(d) : docId}</span>
              <Remove label={t("RemoveDocument")} onClick={() => update((dr) => { dr.document_ids.splice(i, 1); })} />
            </div>
          );
        })}
        <select className={`${inputCls} sm:w-96`} aria-label={t("AddDocument")} value=""
          onChange={(e) => e.target.value && update((d) => { d.document_ids.push(e.target.value); })}>
          <option value="">{t("AddDocument")}</option>
          {documents.filter((d) => !draft.document_ids.includes(d.id)).map((d) => (
            <option key={d.id} value={d.id}>{docTitle(d)}</option>
          ))}
        </select>
      </section>

      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={pending} className={btnCls}>{t("Save")}</button>
        <button type="button" onClick={onDone} className="rounded-lg border px-3 py-1.5 text-sm">{t("Cancel")}</button>
      </div>
    </form>
  );
}
