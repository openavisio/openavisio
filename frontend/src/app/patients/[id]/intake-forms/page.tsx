import { AppLayout } from "@/components/layout/AppLayout";
import { getIntakeForms, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { IntakeFormsView } from "./IntakeFormsView";

export default async function IntakeFormsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("IntakeForms");
  const [patient, forms] = await Promise.all([
    getPatient(id).catch(() => null),
    getIntakeForms(id).catch(() => null),
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
      {forms === null ? (
        <>
          <div className="mb-6">{crumb}</div>
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
            <AlertCircle className="size-4 shrink-0" />
            {t("LoadError")}
          </div>
        </>
      ) : (
        <IntakeFormsView patientId={id} forms={forms}>{crumb}</IntakeFormsView>
      )}
    </AppLayout>
  );
}
