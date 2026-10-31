import { AppLayout } from "@/components/layout/AppLayout";
import { getDocuments, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle, ChevronRight, ListChecks } from "lucide-react";
import { UploadPanel, RetryAllButton } from "./UploadPanel";
import { ShareWithSpecialistPanel } from "./ShareWithSpecialistPanel";
import { DocumentsExplorer } from "./DocumentsExplorer";
import { AiNotice } from "@/components/AiNotice";
import Link from "next/link";

export default async function DocumentsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("DocumentsPage");
  const tr = await getTranslations("ProposalReview");
  const tp = await getTranslations("Patient");
  const tc = await getTranslations("Common");
  const patient = await getPatient(id).catch(() => null);
  const fetched = await getDocuments(id).catch(() => null);
  const fetchError = fetched === null;
  const documents = fetched ?? [];

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{tc("PatientNotFound")}</div>
      </AppLayout>
    );
  }

  // what the review page can actually settle: letters with undecided diagnoses (ADR 058)
  const withOpenDiagnoses = documents.filter((d) => d.open_diagnoses > 0).length;
  const failedDocIds = documents
    .filter((d) => d.processing_status === "failed")
    .map((d) => d.id);

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <Breadcrumb
          crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
          current={tp("Documents")}
          className=""
        />
        {failedDocIds.length > 0 && <RetryAllButton failedDocIds={failedDocIds} />}
      </div>

      {withOpenDiagnoses > 0 && (
        <Link
          href={`/patients/${id}/proposals`}
          className="mb-6 flex items-center gap-3 rounded-xl border border-primary/30 bg-primary/5 p-4 hover:bg-primary/10"
        >
          <ListChecks className="size-5 shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="font-medium">{tr("Banner", { count: withOpenDiagnoses })}</p>
            <p className="text-sm text-muted-foreground">{tr("BannerHint")}</p>
          </div>
          <ChevronRight className="size-5 shrink-0 text-muted-foreground" />
        </Link>
      )}

      <UploadPanel patientId={id} demoMode={process.env.DEMO_MODE === "true"} />

      {documents.length > 0 && <ShareWithSpecialistPanel patientId={id} documents={documents} />}

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("loadError")}
        </div>
      ) : (
        <DocumentsExplorer patientId={id} initialDocuments={documents} />
      )}
      {documents.length > 0 && <AiNotice />}

    </AppLayout>
  );
}
