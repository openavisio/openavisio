import { AppLayout } from "@/components/layout/AppLayout";
import { getCareNotes, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { CareNotesView } from "./CareNotesView";

export default async function CareNotesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("CareNotes");
  const [patient, notes] = await Promise.all([
    getPatient(id).catch(() => null),
    getCareNotes(id).catch(() => undefined),
  ]);

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{t("NotFound")}</div>
      </AppLayout>
    );
  }

  const crumb = (
    <Breadcrumb
      crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
      current={t("Title")}
      className=""
    />
  );

  return (
    <AppLayout>
      {notes === undefined ? (
        <>
          <div className="mb-6">{crumb}</div>
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
            <AlertCircle className="size-4 shrink-0" />
            {t("LoadError")}
          </div>
        </>
      ) : (
        <CareNotesView patientId={id} notes={notes}>{crumb}</CareNotesView>
      )}
    </AppLayout>
  );
}
