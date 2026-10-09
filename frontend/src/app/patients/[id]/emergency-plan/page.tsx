import { AppLayout } from "@/components/layout/AppLayout";
import { getDocuments, getEmergencyPlan, getMedications, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { EmergencyPlanView } from "./EmergencyPlanView";

export default async function EmergencyPlanPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("EmergencyPlan");
  const [patient, data] = await Promise.all([
    getPatient(id).catch(() => null),
    Promise.all([getEmergencyPlan(id), getMedications(id), getDocuments(id)]).catch(() => null),
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
      {data === null ? (
        <>
          <div className="mb-6">{crumb}</div>
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
            <AlertCircle className="size-4 shrink-0" />
            {t("LoadError")}
          </div>
        </>
      ) : (
        <EmergencyPlanView patientId={id} plan={data[0]} medications={data[1]} documents={data[2]}>
          {crumb}
        </EmergencyPlanView>
      )}
    </AppLayout>
  );
}
