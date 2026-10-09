import { AppLayout } from "@/components/layout/AppLayout";
import { getObservations, getPatient } from "@/lib/api";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { AddMeasurementPanel } from "./AddMeasurementPanel";
import { MeasurementGroups } from "./MeasurementGroups";
import { getTranslations } from "next-intl/server";

export default async function MeasurementsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("Measurement");
  const tc = await getTranslations("Common");
  let patient: any = null;
  let observations: any[] = [];
  let fetchError = false;

  try { patient = await getPatient(id); } catch {}
  try { observations = await getObservations(id, { category: "measurement" }); } catch { fetchError = true; }

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{tc("PatientNotFound")}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <AddMeasurementPanel patientId={id}>
        <Breadcrumb
          crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
          current={t("Title")}
          className=""
        />
      </AddMeasurementPanel>

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("LoadError")}
        </div>
      ) : observations.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      ) : (
        <MeasurementGroups observations={observations} />
      )}
    </AppLayout>
  );
}
