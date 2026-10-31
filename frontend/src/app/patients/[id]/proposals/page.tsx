import { AppLayout } from "@/components/layout/AppLayout";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AiNotice } from "@/components/AiNotice";
import { getCorrespondentProposals, getDiagnosisProposals, getDocuments, getPatient } from "@/lib/api";
import { DocumentFacts } from "./DocumentFacts";
import { fromCorrespondents, fromDiagnoses } from "@/lib/proposals";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { ProposalReview } from "./ProposalReview";

export default async function ProposalsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("ProposalReview");
  const tp = await getTranslations("Patient");
  const patient = await getPatient(id).catch(() => null);
  if (!patient) notFound();
  const [correspondents, diagnoses, docs] = await Promise.all([
    getCorrespondentProposals(id).then(fromCorrespondents).catch(() => null),
    getDiagnosisProposals(id).then(fromDiagnoses).catch(() => null),
    getDocuments(id).catch(() => []),
  ]);
  const ids = (r: typeof correspondents) => r?.groups.map((g) => g.spellings.map((s) => s.ids.join()).join()).join("|");

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[
          { label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` },
          { label: tp("Documents"), href: `/patients/${id}/documents` },
        ]}
        current={t("Title")}
      />
      <div className="mb-8">
        <DocumentFacts patientId={id} docs={docs} birthDate={patient.birth_date ?? null} />
      </div>
      {correspondents || diagnoses ? (
        <ProposalReview
          // new data after a decision must replace the cards, not sit under the old client state
          key={`${ids(correspondents)}#${ids(diagnoses)}`}
          patientId={id}
          correspondents={correspondents}
          diagnoses={diagnoses}
        />
      ) : <p className="text-sm text-destructive">{t("LoadError")}</p>}
      <AiNotice />
    </AppLayout>
  );
}
