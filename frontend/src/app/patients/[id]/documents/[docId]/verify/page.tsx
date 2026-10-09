import { AppLayout } from "@/components/layout/AppLayout";
import { getDocumentDetail, getPatient } from "@/lib/api";
import { Breadcrumb } from "@/components/Breadcrumb";
import { notFound, redirect } from "next/navigation";
import { VerifyForm } from "./VerifyForm";
import { AiNotice } from "@/components/AiNotice";

export default async function VerifyPage({ params }: { params: Promise<{ id: string; docId: string }> }) {
  const { id, docId } = await params;
  const [, doc] = await Promise.all([
    getPatient(id).catch(() => null),
    getDocumentDetail(docId).catch(() => null),
  ]);

  if (!doc) notFound();
  if (!doc.extraction_json) redirect(`/patients/${id}/documents/${docId}`);

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[
          { label: "Documents", href: `/patients/${id}/documents` },
          { label: doc.file_name || "Document", href: `/patients/${id}/documents/${docId}` },
        ]}
        current="Verify"
      />

      <VerifyForm docId={docId} patientId={id} extractionJson={doc.extraction_json} contentType={doc.content_type ?? ""} extractedText={doc.extracted_text ?? null} />
      <AiNotice />

    </AppLayout>
  );
}
