import { AppLayout } from "@/components/layout/AppLayout";
import { getIntakeForm, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { SheetView } from "./SheetView";

export default async function IntakeFormPage({ params }: { params: Promise<{ id: string; formId: string }> }) {
  const { id, formId } = await params;
  const t = await getTranslations("IntakeForms");
  const [patient, form] = await Promise.all([
    getPatient(id).catch(() => null),
    getIntakeForm(formId).catch(() => null),
  ]);

  if (!patient || !form) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{t("NotFound")}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <SheetView patientId={id} form={form}>
        <Breadcrumb
          crumbs={[
            { label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` },
            { label: t("Title"), href: `/patients/${id}/intake-forms` },
          ]}
          current={form.title || form.file_name || t("Title")}
          className=""
        />
      </SheetView>
    </AppLayout>
  );
}
