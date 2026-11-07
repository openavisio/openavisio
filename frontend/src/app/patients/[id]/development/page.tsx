import { AppLayout } from "@/components/layout/AppLayout";
import { getAbilities, getCorrespondents, getDocuments, getPatient, getTestAttempts } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { DevelopmentView } from "./DevelopmentView";

export default async function DevelopmentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("Development");
  const [patient, abilities, attempts, correspondents, documents] = await Promise.all([
    getPatient(id).catch(() => null),
    getAbilities(id).catch(() => null),
    getTestAttempts(id).catch(() => null),
    getCorrespondents().catch(() => []),
    getDocuments(id).catch(() => []),
  ]);

  if (!patient) {
    return <AppLayout><div className="py-12 text-center text-muted-foreground">{t("NotFound")}</div></AppLayout>;
  }

  const crumb = <Breadcrumb crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]} current={t("Title")} className="" />;

  return (
    <AppLayout>
      {abilities === null || attempts === null ? (
        <>
          <div className="mb-6">{crumb}</div>
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="size-4 shrink-0" />{t("LoadError")}
          </div>
        </>
      ) : (
        <DevelopmentView patientId={id} birthDate={patient.birth_date} abilities={abilities} attempts={attempts}
                         correspondents={correspondents} documents={documents}>{crumb}</DevelopmentView>
      )}
    </AppLayout>
  );
}
