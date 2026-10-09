import { AppLayout } from "@/components/layout/AppLayout";
import { getDocumentDetail, getPatient, getCorrespondents, getObservations } from "@/lib/api";
import Link from "next/link";
import { Breadcrumb } from "@/components/Breadcrumb";
import { notFound } from "next/navigation";
import { formatDate, statusBadgeColor } from "@/lib/utils";
import { getTranslations } from "next-intl/server";
import { DeleteDocumentButton } from "./DeleteDocumentButton";
import { EditIssuedDate } from "./EditIssuedDate";
import { CorrespondentSelect } from "./CorrespondentSelect";
import { DocumentViewer } from "@/components/DocumentViewer";
import { ClipboardCheck } from "lucide-react";
import { AiNotice } from "@/components/AiNotice";

export default async function DocumentDetailPage({ params }: { params: Promise<{ id: string; docId: string }> }) {
  const { id, docId } = await params;
  const t = await getTranslations("DocDetail");
  const [patient, doc, correspondents, allObs] = await Promise.all([
    getPatient(id).catch(() => null),
    getDocumentDetail(docId).catch(() => null),
    getCorrespondents().catch(() => []),
    getObservations(id).catch(() => [] as any[]),
  ]);
  if (!doc) notFound();

  const j = doc.extraction_json ?? {};
  const obs: any[] = j.observations ?? [];
  const diagnoses: any[] = j.diagnoses ?? [];
  const medications: any[] = j.medications ?? [];
  const appointments: any[] = j.appointments ?? [];
  const recommendations: string[] = j.recommendations ?? [];
  const persons: any[] = j.mentioned_persons ?? [];

  // Prefer the saved (verified) observations for this document — they carry the
  // canonical panel and parsed reference range (out-of-range). Fall back to the
  // raw extraction for a not-yet-verified document.
  const savedForDoc = (allObs as any[]).filter((o) => o.document_reference_id === docId);
  const useSaved = savedForDoc.length > 0;

  const outOfRange = (o: any): "low" | "high" | null => {
    if (o.value_quantity == null) return null;
    if (o.ref_low != null && o.value_quantity < o.ref_low) return "low";
    if (o.ref_high != null && o.value_quantity > o.ref_high) return "high";
    return null;
  };
  const normalize = (o: any) => {
    if (useSaved) {
      const ref = o.reference_range
        || (o.ref_low != null && o.ref_high != null ? `${o.ref_low}–${o.ref_high}`
          : o.ref_high != null ? `< ${o.ref_high}` : o.ref_low != null ? `> ${o.ref_low}` : "");
      return {
        name: o.code_display || o.code || "",
        value: o.value_quantity != null ? `${o.value_quantity}` : (o.value_string || ""),
        unit: o.value_unit || "", reference: ref, flag: outOfRange(o), panel: o.panel, category: o.category,
      };
    }
    return { name: o.type, value: o.value ?? "", unit: o.unit || "", reference: o.reference_range || "", flag: null as null, panel: o.panel, category: o.category };
  };

  const rows = (useSaved ? savedForDoc : obs).map(normalize);
  const labRows = rows.filter((r) => r.category === "lab");
  const vitals = rows.filter((r) => r.category !== "lab");

  // group lab values by panel (canonical when saved)
  const labPanels = new Map<string, typeof rows>();
  for (const r of labRows) {
    const key = r.panel || t("labResults");
    if (!labPanels.has(key)) labPanels.set(key, []);
    labPanels.get(key)!.push(r);
  }

  const nothingExtracted =
    !j.summary && obs.length === 0 && diagnoses.length === 0 && medications.length === 0 &&
    appointments.length === 0 && recommendations.length === 0;

  // A meaningful heading, not the (often cryptic, scanned) file name.
  const KNOWN_CLASS = new Set(["lab_report", "doctor_letter", "therapy_report", "prescription", "imaging_report", "discharge_summary"]);
  const title =
    doc.type ||
    (KNOWN_CLASS.has(doc.document_classification) ? t(`class_${doc.document_classification}`) : null) ||
    t("document");

  return (
    <AppLayout>
      <div className="flex items-center gap-2 mb-6">
        <Breadcrumb
          crumbs={[{ label: patient ? `${patient.given_name} ${patient.family_name}` : "", href: `/patients/${id}/documents` }]}
          current={
            <span className="flex items-center gap-2">
              {title}
              {["pending", "processing", "failed", "extracted"].includes(doc.processing_status) && (
                <span className={`px-2.5 py-1 rounded-full text-sm font-medium ${statusBadgeColor(doc.processing_status)}`}>
                  {doc.processing_status}
                </span>
              )}
            </span>
          }
          className=""
        />
        <div className="ml-auto">
          <DeleteDocumentButton docId={docId} patientId={id} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start">
        {/* PDF — sticky on desktop */}
        <DocumentViewer
          docId={docId}
          contentType={doc.content_type ?? "application/pdf"}
          className="w-full h-[60vh] lg:h-[calc(100vh-8rem)] lg:sticky lg:top-4"
        />

        {/* Extracted data + metadata */}
        <div className="space-y-6 min-w-0">
          {doc.verification_status === "extracted" && (
            <Link
              href={`/patients/${id}/documents/${docId}/verify`}
              className="flex items-center justify-center gap-2 rounded-xl border border-primary/40 bg-primary/5 px-4 py-3 text-sm font-medium text-primary hover:bg-primary/10 transition-colors"
            >
              <ClipboardCheck className="h-4 w-4" />
              {t("reviewCta")}
            </Link>
          )}

          {j.summary && (
            <Section title={t("summary")}>
              <p className="text-sm leading-relaxed">{j.summary}</p>
            </Section>
          )}

          {labRows.length > 0 && (
            <Section title={t("labResults")}>
              <div className="space-y-4">
                {[...labPanels.entries()].map(([panel, items]) => (
                  <div key={panel}>
                    <p className="text-xs font-medium text-muted-foreground mb-1">{panel}</p>
                    <table className="w-full text-sm">
                      <tbody className="divide-y">
                        {items.map((r, i) => (
                          <tr key={i}>
                            <td className="py-1.5 pr-3 font-medium">{r.name}</td>
                            <td className={`py-1.5 pr-3 whitespace-nowrap font-medium ${
                              r.flag === "high" ? "text-destructive" : r.flag === "low" ? "text-amber-600 dark:text-amber-400" : ""
                            }`}>
                              {r.value}{r.unit ? ` ${r.unit}` : ""}
                              {r.flag === "high" ? " ↑" : r.flag === "low" ? " ↓" : ""}
                            </td>
                            <td className="py-1.5 text-right text-xs text-muted-foreground font-mono whitespace-nowrap">
                              {r.reference}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {vitals.length > 0 && (
            <Section title={t("measurements")}>
              <table className="w-full text-sm">
                <tbody className="divide-y">
                  {vitals.map((r, i) => (
                    <tr key={i}>
                      <td className="py-1.5 pr-3 font-medium">{r.name}</td>
                      <td className="py-1.5 whitespace-nowrap">{r.value}{r.unit ? ` ${r.unit}` : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
          )}

          {diagnoses.length > 0 && (
            <Section title={t("diagnoses")}>
              <ul className="space-y-1.5 text-sm">
                {diagnoses.map((d, i) => (
                  <li key={i} className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{d.name}</span>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {[d.severity, d.status, d.onset_date].filter(Boolean).join(" · ")}
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {medications.length > 0 && (
            <Section title={t("medications")}>
              <ul className="space-y-1.5 text-sm">
                {medications.map((m, i) => (
                  <li key={i} className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{m.name}</span>
                    {m.dosage && <span className="text-xs text-muted-foreground whitespace-nowrap">{m.dosage}</span>}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {appointments.length > 0 && (
            <Section title={t("appointments")}>
              <ul className="space-y-1.5 text-sm">
                {appointments.map((a, i) => (
                  <li key={i}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="font-medium">{a.purpose || a.provider || t("appointments")}</span>
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {[a.date, a.time].filter(Boolean).join(" ")}
                      </span>
                    </div>
                    {(a.provider || a.location) && (
                      <p className="text-xs text-muted-foreground">{[a.provider, a.location].filter(Boolean).join(" · ")}</p>
                    )}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {recommendations.length > 0 && (
            <Section title={t("recommendations")}>
              <ul className="list-disc pl-4 space-y-1 text-sm">
                {recommendations.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </Section>
          )}

          {persons.length > 0 && (
            <Section title={t("referencedPersons")}>
              <ul className="space-y-1 text-sm">
                {persons.map((p, i) => (
                  <li key={i}>
                    <span className="font-medium">{p.name}</span>
                    {(p.role || p.institution) && (
                      <span className="text-xs text-muted-foreground"> — {[p.role, p.institution].filter(Boolean).join(", ")}</span>
                    )}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {nothingExtracted && doc.extraction_json && (
            <p className="text-sm text-muted-foreground">{t("noData")}</p>
          )}

          {/* Metadata */}
          <Section title={t("documentInfo")}>
            <dl className="space-y-2 text-sm">
              <Row label={t("type")} value={doc.type} />
              <Row label={t("provider")} value={doc.detected_provider} />
              <div className="flex justify-between items-center">
                <dt className="text-muted-foreground">{t("correspondent")}</dt>
                <dd>
                  <CorrespondentSelect docId={docId} patientId={id} current={doc.correspondent ?? null} correspondents={correspondents} />
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("issued")}</dt>
                <dd><EditIssuedDate docId={docId} patientId={id} value={doc.issued_date ?? null} /></dd>
              </div>
              <Row label={t("added")} value={formatDate(doc.created_at)} />
              {doc.file_name && (
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground shrink-0">{t("file")}</dt>
                  <dd className="font-medium text-right truncate" title={doc.file_name}>{doc.file_name}</dd>
                </div>
              )}
              <Row label={t("ocrConfidence")} value={doc.ocr_confidence != null ? `${(doc.ocr_confidence * 100).toFixed(0)}%` : null} />
              {doc.processing_error && <Row label={t("error")} value={doc.processing_error} className="text-destructive" />}
            </dl>
          </Section>

          {/* Raw OCR text — technical, collapsed by default */}
          {doc.extracted_text && (
            <details className="rounded-xl border bg-card p-5">
              <summary className="cursor-pointer text-sm font-medium text-muted-foreground select-none">
                {t("showText")}
              </summary>
              <pre className="mt-3 text-xs bg-muted rounded-lg p-3 overflow-auto max-h-96 whitespace-pre-wrap">
                {doc.extracted_text}
              </pre>
            </details>
          )}
        </div>
      </div>
      <AiNotice />

    </AppLayout>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-5 space-y-3">
      <h2 className="font-semibold text-sm">{title}</h2>
      {children}
    </div>
  );
}

function Row({ label, value, className = "" }: { label: string; value: any; className?: string }) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground shrink-0">{label}</dt>
      <dd className={`font-medium text-right ${className}`}>{value}</dd>
    </div>
  );
}
