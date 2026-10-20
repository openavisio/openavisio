import { AppLayout } from "@/components/layout/AppLayout";
import { getDocuments, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { UploadPanel, RetryAllButton } from "./UploadPanel";
import { ShareWithSpecialistPanel } from "./ShareWithSpecialistPanel";
import { DocumentsExplorer } from "./DocumentsExplorer";
import { AiNotice } from "@/components/AiNotice";

export default async function DocumentsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("DocumentsPage");
  const tp = await getTranslations("Patient");
  const tc = await getTranslations("Common");
  let patient: any = null;
  let documents: any[] = [];
  let fetchError = false;

  try { patient = await getPatient(id); } catch {}
  try { documents = await getDocuments(id); } catch { fetchError = true; }

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{tc("PatientNotFound")}</div>
      </AppLayout>
    );
  }

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
