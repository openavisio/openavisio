"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { verifyDocument } from "@/lib/api";
import { DocumentViewer } from "@/components/DocumentViewer";
import { Check, ChevronDown, FileText } from "lucide-react";

interface MentionedPerson {
  name: string;
  role: string;
  institution?: string;
}

interface Appointment {
  date?: string;
  time?: string;
  provider?: string;
  location?: string;
  purpose?: string;
  is_future?: boolean;
}

interface Observation {
  type?: string;
  value?: string | number;
  unit?: string;
  category?: string;
}

/** A Kassenbescheid's Rechtsbehelfsbelehrung — ADR 041. deadline_date is computed
 *  by the backend, never here; this screen only shows it and lets it be corrected. */
interface Decision {
  decision_date?: string | null;
  deadline_months?: number | null;
  deadline_date?: string | null;
  authority?: string | null;
  file_reference?: string | null;
  subject?: string | null;
  grounds?: string | null;
}

interface ExtractionJson {
  summary?: string;
  mentioned_persons?: MentionedPerson[];
  diagnoses?: Record<string, any>[];
  medications?: Record<string, any>[];
  observations?: Observation[];
  appointments?: Appointment[];
  recommendations?: string[];
  decision?: Decision | null;
}

interface Props {
  docId: string;
  patientId: string;
  extractionJson: ExtractionJson;
  contentType: string;
  extractedText?: string | null;
}

function useSelectionSet(length: number) {
  return useState<Set<number>>(() => new Set(Array.from({ length }, (_, i) => i)));
}

function toggle(setFn: React.Dispatch<React.SetStateAction<Set<number>>>, index: number) {
  setFn((prev) => {
    const next = new Set(prev);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    return next;
  });
}

export function VerifyForm({ docId, patientId, extractionJson, contentType, extractedText }: Props) {
  const router = useRouter();
  // ponytail: only the deadline block is translated; the rest of this form is still
  // hard-coded English and predates the i18n setup. Widening that is its own change.
  const t = useTranslations("Verify");
  const tc = useTranslations("Common");
  const td = useTranslations("DocDetail");
  const tCal = useTranslations("Calendar");
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const diagnoses = extractionJson.diagnoses ?? [];
  const medications = extractionJson.medications ?? [];
  const allObservations = extractionJson.observations ?? [];
  const measurements = allObservations.filter((o) => o.category !== "lab");
  const labResults = allObservations.filter((o) => o.category === "lab");
  const appointments = extractionJson.appointments ?? [];
  const mentionedPersons = extractionJson.mentioned_persons ?? [];
  const recommendations = extractionJson.recommendations ?? [];

  const [selectedDx, setSelectedDx] = useSelectionSet(diagnoses.length);
  const [selectedMeds, setSelectedMeds] = useSelectionSet(medications.length);
  const [selectedMeasurements, setSelectedMeasurements] = useSelectionSet(measurements.length);
  const [selectedLab, setSelectedLab] = useSelectionSet(labResults.length);
  const [selectedAppts, setSelectedAppts] = useSelectionSet(appointments.length);
  const [selectedRecs, setSelectedRecs] = useSelectionSet(recommendations.length);

  const [editedDx, setEditedDx] = useState<Record<string, any>[]>(() => diagnoses.map((d) => ({ ...d })));

  function addNewDx() {
    const idx = editedDx.length;
    setEditedDx((prev) => [...prev, { name: "", severity: null, status: "active", onset_date: null }]);
    setSelectedDx((prev) => { const next = new Set(prev); next.add(idx); return next; });
    setEditingDx(idx);
  }
  const [editedMeds, setEditedMeds] = useState<Record<string, any>[]>(() => medications.map((m) => ({ ...m })));
  const [editedMeasurements, setEditedMeasurements] = useState<Observation[]>(() => measurements.map((o) => ({ ...o })));
  const [editedLab, setEditedLab] = useState<Observation[]>(() => labResults.map((o) => ({ ...o })));
  const [editedAppts, setEditedAppts] = useState<Appointment[]>(() => appointments.map((a) => ({ ...a })));
  const [editedRecs, setEditedRecs] = useState<string[]>(() => [...recommendations]);

  // A deadline is offered only when the letter carried a Rechtsbehelfsbelehrung and a
  // date could be computed from it. Unchecking it is the way to decline it.
  const decision = extractionJson.decision ?? null;
  const [editedDecision, setEditedDecision] = useState<Decision>(() => ({ ...(decision ?? {}) }));
  const [decisionSelected, setDecisionSelected] = useState(true);
  const [editingDecision, setEditingDecision] = useState(false);
  const hasDeadline = Boolean(decision && editedDecision.deadline_date);
  function patchDecision(key: keyof Decision, value: string) {
    setEditedDecision((prev) => ({ ...prev, [key]: value }));
  }

  const [editingDx, setEditingDx] = useState<number | null>(null);
  const [editingMed, setEditingMed] = useState<number | null>(null);
  const [editingMeasurement, setEditingMeasurement] = useState<number | null>(null);
  const [editingLab, setEditingLab] = useState<number | null>(null);
  const [editingAppt, setEditingAppt] = useState<number | null>(null);
  const [editingRec, setEditingRec] = useState<number | null>(null);

  const [summaryExpanded, setSummaryExpanded] = useState(false);

  const hasContent =
    diagnoses.length > 0 ||
    medications.length > 0 ||
    allObservations.length > 0 ||
    appointments.length > 0 ||
    recommendations.length > 0 ||
    hasDeadline ||
    extractionJson.summary;

  // OCR text panel — open by default when there's nothing to verify.
  const [ocrOpen, setOcrOpen] = useState(!hasContent);

  function handleSubmit() {
    setError(null);
    startTransition(async () => {
      try {
        await verifyDocument(docId, {
          diagnoses: editedDx.filter((_, i) => selectedDx.has(i)),
          medications: editedMeds.filter((_, i) => selectedMeds.has(i)),
          observations: [
            ...editedMeasurements.filter((_, i) => selectedMeasurements.has(i)),
            ...editedLab.filter((_, i) => selectedLab.has(i)),
          ],
          appointments: editedAppts.filter((_, i) => selectedAppts.has(i)),
          recommendations: editedRecs.filter((_, i) => selectedRecs.has(i)),
          decision: hasDeadline && decisionSelected ? editedDecision : null,
        });
        // push re-fetches the (dynamic) list route; a following refresh() would
        // keep the transition pending and hang the "Saving…" button.
        router.push(`/patients/${patientId}/documents`);
      } catch (e) {
        setError(e instanceof Error ? e.message : t("SubmitError"));
      }
    });
  }

  const mainContent = (
    <div className="space-y-6">
      {/* Empty state */}
      {!hasContent && (
        <div className="rounded-xl border bg-card p-8 text-center space-y-2">
          <p className="font-medium">{t("NoDataTitle")}</p>
          <p className="text-sm text-muted-foreground">
            {t("NoDataBody")}
          </p>
        </div>
      )}

      {/* Widerspruch deadline — first, because it is the only thing here that expires. */}
      {hasDeadline && (
        <div className="rounded-xl border border-amber-300 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-950/20 p-5">
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={decisionSelected}
              onChange={() => setDecisionSelected((v) => !v)}
              className="mt-1 h-4 w-4 rounded border-input accent-primary shrink-0"
              aria-label={t("Deadline")}
            />
            <div className="flex-1 min-w-0 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <h2 className="font-semibold">{t("Deadline")}</h2>
                <button
                  onClick={() => setEditingDecision((v) => !v)}
                  className="text-xs text-primary hover:underline font-medium shrink-0"
                >
                  {editingDecision ? tc("Done") : tc("Edit")}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">{t("DeadlineHint")}</p>

              {editingDecision ? (
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <LabeledInput label={t("DeadlineDate")} value={editedDecision.deadline_date ?? ""} onChange={(v) => patchDecision("deadline_date", v)} />
                  <LabeledInput label={t("Subject")} value={editedDecision.subject ?? ""} onChange={(v) => patchDecision("subject", v)} />
                  <LabeledInput label={t("Authority")} value={editedDecision.authority ?? ""} onChange={(v) => patchDecision("authority", v)} />
                  <LabeledInput label={t("FileReference")} value={editedDecision.file_reference ?? ""} onChange={(v) => patchDecision("file_reference", v)} />
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="text-2xl font-semibold tabular-nums">{editedDecision.deadline_date}</div>
                  <div className="text-sm">{editedDecision.subject}</div>
                  <div className="text-sm text-muted-foreground">
                    {[
                      editedDecision.authority,
                      editedDecision.file_reference && `${t("FileReference")}: ${editedDecision.file_reference}`,
                      editedDecision.decision_date && `${t("DecisionDate")} ${editedDecision.decision_date}`,
                    ].filter(Boolean).join(" · ")}
                  </div>
                </div>
              )}

              {editedDecision.grounds && (
                <blockquote className="text-sm text-muted-foreground border-l-2 pl-3 mt-2">
                  <span className="block text-xs font-medium mb-0.5">{t("Grounds")}</span>
                  {editedDecision.grounds}
                </blockquote>
              )}

              <p className="text-xs text-muted-foreground pt-1">{t("DeadlineDisclaimer")}</p>
            </div>
          </div>
        </div>
      )}

      {/* Summary */}
      {extractionJson.summary && (
        <div className="rounded-xl border bg-card p-5">
          <h2 className="font-semibold mb-2">{td("summary")}</h2>
          <p className={`text-sm text-muted-foreground leading-relaxed ${!summaryExpanded ? "line-clamp-3" : ""}`}>
            {extractionJson.summary}
          </p>
          {extractionJson.summary.length > 200 && (
            <button
              onClick={() => setSummaryExpanded((v) => !v)}
              className="mt-1 text-xs text-primary hover:underline"
            >
              {summaryExpanded ? t("ShowLess") : t("ShowMore")}
            </button>
          )}
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <SelectionSection title={td("recommendations")} hint={t("RecommendationsHint")}>
          {recommendations.map((rec, i) => (
            <EditableCheckRow
              key={i}
              checked={selectedRecs.has(i)}
              onToggle={() => toggle(setSelectedRecs, i)}
              editing={editingRec === i}
              onEdit={() => setEditingRec(i)}
              onDone={() => setEditingRec(null)}
            >
              {editingRec === i ? (
                <input
                  autoFocus
                  className="w-full text-sm border rounded px-2 py-1 bg-background"
                  value={editedRecs[i]}
                  onChange={(e) => setEditedRecs((prev) => prev.map((r, idx) => (idx === i ? e.target.value : r)))}
                />
              ) : (
                <span className="text-sm">{editedRecs[i]}</span>
              )}
            </EditableCheckRow>
          ))}
        </SelectionSection>
      )}

      {/* Diagnoses */}
      <SelectionSection
        title={t("Diagnoses")}
        action={<button onClick={addNewDx} className="text-xs text-primary hover:underline font-medium">{t("AddDiagnosis")}</button>}
      >
        {editedDx.map((dx, i) => (
            <EditableCheckRow
              key={i}
              checked={selectedDx.has(i)}
              onToggle={() => toggle(setSelectedDx, i)}
              editing={editingDx === i}
              onEdit={() => setEditingDx(i)}
              onDone={() => setEditingDx(null)}
            >
              {editingDx === i ? (
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <LabeledInput label={tc("Name")} value={editedDx[i].name ?? ""} onChange={(v) => patchDx(i, "name", v)} />
                  <LabeledInput label={t("Severity")} value={editedDx[i].severity ?? ""} onChange={(v) => patchDx(i, "severity", v)} />
                  <LabeledInput label={tc("Status")} value={editedDx[i].status ?? ""} onChange={(v) => patchDx(i, "status", v)} />
                  <LabeledInput label={t("OnsetDate")} value={editedDx[i].onset_date ?? ""} onChange={(v) => patchDx(i, "onset_date", v)} />
                  {editedDx[i].category === "allergy" && (
                    <LabeledInput label={t("reaction")} value={editedDx[i].reaction ?? ""} onChange={(v) => patchDx(i, "reaction", v)} />
                  )}
                </div>
              ) : (
                <div className="text-sm">
                  <div className="font-medium">
                    {editedDx[i].name ?? editedDx[i].code_display ?? tc("Unknown")}
                    {editedDx[i].verification_status === "provisional" && (
                      <span className="ml-2 rounded-full border border-dashed px-2 py-0.5 text-xs font-normal text-muted-foreground">{t("suspected")}</span>
                    )}
                  </div>
                  <div className="text-muted-foreground">
                    {[editedDx[i].category === "allergy" && editedDx[i].reaction, editedDx[i].severity, editedDx[i].status, editedDx[i].onset_date].filter(Boolean).join(" · ")}
                  </div>
                </div>
              )}
            </EditableCheckRow>
          ))}
      </SelectionSection>

      {/* Medications */}
      {medications.length > 0 && (
        <SelectionSection title={t("Medications")}>
          {medications.map((_, i) => (
            <EditableCheckRow
              key={i}
              checked={selectedMeds.has(i)}
              onToggle={() => toggle(setSelectedMeds, i)}
              editing={editingMed === i}
              onEdit={() => setEditingMed(i)}
              onDone={() => setEditingMed(null)}
            >
              {editingMed === i ? (
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <LabeledInput label={tc("Name")} value={editedMeds[i].name ?? ""} onChange={(v) => patchMed(i, "name", v)} />
                  <LabeledInput label={t("Dosage")} value={editedMeds[i].dosage ?? ""} onChange={(v) => patchMed(i, "dosage", v)} />
                </div>
              ) : (
                <div className="text-sm">
                  <div className="font-medium">{editedMeds[i].name ?? editedMeds[i].medication_display ?? tc("Unknown")}</div>
                  {editedMeds[i].dosage && <div className="text-muted-foreground">{editedMeds[i].dosage}</div>}
                </div>
              )}
            </EditableCheckRow>
          ))}
        </SelectionSection>
      )}

      {/* Measurements */}
      {measurements.length > 0 && (
        <SelectionSection title={td("measurements")}>
          {measurements.map((_, i) => (
            <EditableCheckRow
              key={i}
              checked={selectedMeasurements.has(i)}
              onToggle={() => toggle(setSelectedMeasurements, i)}
              editing={editingMeasurement === i}
              onEdit={() => setEditingMeasurement(i)}
              onDone={() => setEditingMeasurement(null)}
            >
              {editingMeasurement === i ? (
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <LabeledInput label={tc("Type")} value={editedMeasurements[i].type ?? ""} onChange={(v) => patchObs(editedMeasurements, setEditedMeasurements, i, "type", v)} />
                  <LabeledInput label={tc("Value")} value={String(editedMeasurements[i].value ?? "")} onChange={(v) => patchObs(editedMeasurements, setEditedMeasurements, i, "value", v)} />
                  <LabeledInput label={t("Unit")} value={editedMeasurements[i].unit ?? ""} onChange={(v) => patchObs(editedMeasurements, setEditedMeasurements, i, "unit", v)} />
                </div>
              ) : (
                <div className="text-sm">
                  <div className="font-medium">{editedMeasurements[i].type ?? t("Measurement")}</div>
                  <div className="text-muted-foreground">
                    {editedMeasurements[i].unit ? `${editedMeasurements[i].value} ${editedMeasurements[i].unit}` : String(editedMeasurements[i].value ?? "")}
                  </div>
                </div>
              )}
            </EditableCheckRow>
          ))}
        </SelectionSection>
      )}

      {/* Lab Results */}
      {labResults.length > 0 && (
        <SelectionSection title={td("labResults")}>
          {labResults.map((_, i) => (
            <EditableCheckRow
              key={i}
              checked={selectedLab.has(i)}
              onToggle={() => toggle(setSelectedLab, i)}
              editing={editingLab === i}
              onEdit={() => setEditingLab(i)}
              onDone={() => setEditingLab(null)}
            >
              {editingLab === i ? (
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <LabeledInput label={tc("Type")} value={editedLab[i].type ?? ""} onChange={(v) => patchObs(editedLab, setEditedLab, i, "type", v)} />
                  <LabeledInput label={tc("Value")} value={String(editedLab[i].value ?? "")} onChange={(v) => patchObs(editedLab, setEditedLab, i, "value", v)} />
                  <LabeledInput label={t("Unit")} value={editedLab[i].unit ?? ""} onChange={(v) => patchObs(editedLab, setEditedLab, i, "unit", v)} />
                </div>
              ) : (
                <div className="text-sm">
                  <div className="font-medium">{editedLab[i].type ?? t("LabResult")}</div>
                  <div className="text-muted-foreground">
                    {editedLab[i].unit ? `${editedLab[i].value} ${editedLab[i].unit}` : String(editedLab[i].value ?? "")}
                  </div>
                </div>
              )}
            </EditableCheckRow>
          ))}
        </SelectionSection>
      )}

      {/* Events */}
      {appointments.length > 0 && (
        <SelectionSection title={t("Events")} hint={t("EventsHint")}>
          {appointments.map((_, i) => (
            <EditableCheckRow
              key={i}
              checked={selectedAppts.has(i)}
              onToggle={() => toggle(setSelectedAppts, i)}
              editing={editingAppt === i}
              onEdit={() => setEditingAppt(i)}
              onDone={() => setEditingAppt(null)}
            >
              {editingAppt === i ? (
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <LabeledInput label={tCal("Purpose")} value={editedAppts[i].purpose ?? ""} onChange={(v) => patchAppt(i, "purpose", v)} />
                  <LabeledInput label={tCal("Provider")} value={editedAppts[i].provider ?? ""} onChange={(v) => patchAppt(i, "provider", v)} />
                  <LabeledInput label={tc("Date")} value={editedAppts[i].date ?? ""} onChange={(v) => patchAppt(i, "date", v)} />
                  <LabeledInput label={tCal("Location")} value={editedAppts[i].location ?? ""} onChange={(v) => patchAppt(i, "location", v)} />
                </div>
              ) : (
                <div className="text-sm">
                  <div className="font-medium">
                    {editedAppts[i].purpose || (editedAppts[i].provider ? t("AppointmentWith", { provider: editedAppts[i].provider }) : tCal("Appointment"))}
                  </div>
                  <div className="text-muted-foreground">
                    {[
                      editedAppts[i].date && (editedAppts[i].time ? t("DateAtTime", { date: editedAppts[i].date, time: editedAppts[i].time }) : editedAppts[i].date),
                      editedAppts[i].provider,
                      editedAppts[i].location,
                      editedAppts[i].is_future === false ? t("Past") : editedAppts[i].is_future === true ? t("Upcoming") : undefined,
                    ].filter(Boolean).join(" · ")}
                  </div>
                </div>
              )}
            </EditableCheckRow>
          ))}
        </SelectionSection>
      )}

      {/* Referenced Persons */}
      {mentionedPersons.length > 0 && (
        <div className="rounded-xl border bg-card p-5">
          <h2 className="font-semibold mb-3">{td("referencedPersons")}</h2>
          <div className="space-y-2">
            {mentionedPersons.map((p, i) => (
              <div key={i} className="flex flex-wrap gap-x-3 text-sm">
                <span className="font-medium">{p.name}</span>
                <span className="text-muted-foreground">{p.role}</span>
                {p.institution && <span className="text-muted-foreground">· {p.institution}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex items-center gap-4 pt-2">
        <button
          onClick={handleSubmit}
          disabled={isPending}
          className="px-5 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {isPending ? tc("Saving") : t("ConfirmSave")}
        </button>
        <Link href={`/patients/${patientId}/documents/${docId}`} className="text-sm text-muted-foreground hover:text-foreground">
          {tc("Cancel")}
        </Link>
      </div>
    </div>
  );

  // Patch helpers
  function patchDx(i: number, key: string, value: string) {
    setEditedDx((prev) => prev.map((d, idx) => (idx === i ? { ...d, [key]: value } : d)));
  }
  function patchMed(i: number, key: string, value: string) {
    setEditedMeds((prev) => prev.map((m, idx) => (idx === i ? { ...m, [key]: value } : m)));
  }
  function patchObs(
    list: Observation[],
    setList: React.Dispatch<React.SetStateAction<Observation[]>>,
    i: number,
    key: string,
    value: string,
  ) {
    setList((prev) => prev.map((o, idx) => (idx === i ? { ...o, [key]: value } : o)));
  }
  function patchAppt(i: number, key: string, value: string) {
    setEditedAppts((prev) => prev.map((a, idx) => (idx === i ? { ...a, [key]: value } : a)));
  }

  const rightColumn = (
    <div className="space-y-4">
      <DocumentViewer docId={docId} contentType={contentType} className="w-full h-[60vh]" />
      {extractedText && (
        <div className="rounded-xl border bg-card overflow-hidden">
          <button
            onClick={() => setOcrOpen((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/40 transition-colors"
          >
            <span className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              {t("OcrText")}
            </span>
            <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${ocrOpen ? "rotate-180" : ""}`} />
          </button>
          {ocrOpen && (
            <pre className="text-xs bg-muted/50 border-t p-4 overflow-auto max-h-[50vh] whitespace-pre-wrap">
              {extractedText}
            </pre>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div className="flex gap-6 items-start">
      <div className="flex-1 min-w-0 space-y-6">
        {mainContent}
        {/* viewer + OCR below content on mobile */}
        <div className="lg:hidden">{rightColumn}</div>
      </div>
      {/* viewer + OCR sidebar on desktop */}
      <div className="hidden lg:block flex-1 min-w-0 sticky top-6">{rightColumn}</div>
    </div>
  );
}

function SelectionSection({ title, hint, action, children }: { title: string; hint?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-semibold">{title}</h2>
        {action}
      </div>
      {hint && <p className="text-xs text-muted-foreground mb-3">{hint}</p>}
      <div className="space-y-3 mt-3">{children}</div>
    </div>
  );
}

function EditableCheckRow({
  checked,
  onToggle,
  editing,
  onEdit,
  onDone,
  children,
}: {
  checked: boolean;
  onToggle: () => void;
  editing: boolean;
  onEdit: () => void;
  onDone: () => void;
  children: React.ReactNode;
}) {
  const tc = useTranslations("Common");
  return (
    <div className={`flex items-start gap-3 transition-opacity ${!checked && !editing ? "opacity-40" : ""}`}>
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        className="mt-1 h-4 w-4 rounded border-input accent-primary shrink-0"
      />
      <div className="flex-1 min-w-0">{children}</div>
      {editing ? (
        <button onClick={onDone} className="shrink-0 text-primary hover:text-primary/80 mt-1" aria-label={tc("Done")}>
          <Check className="h-3.5 w-3.5" />
        </button>
      ) : (
        <button onClick={onEdit} className="shrink-0 text-muted-foreground hover:text-foreground mt-1" aria-label={tc("Edit")}>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
          </svg>
        </button>
      )}
    </div>
  );
}

function LabeledInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        className="border rounded px-2 py-1 text-sm bg-background"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
