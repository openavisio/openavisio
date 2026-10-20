import { AppLayout } from "@/components/layout/AppLayout";
import { getMedications, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { AddMedicationPanel } from "./AddMedicationPanel";
import { MedicationsTable } from "./MedicationsTable";
import { AiNotice } from "@/components/AiNotice";

export default async function MedicationsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("Med");
  let patient: any = null;
  let medications: any[] = [];
  let fetchError = false;

  try { patient = await getPatient(id); } catch {}
  try { medications = await getMedications(id); } catch { fetchError = true; }

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{t("NotFound")}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <AddMedicationPanel patientId={id}>
        <Breadcrumb
          crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
          current={t("Title")}
          className=""
        />
      </AddMedicationPanel>

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("LoadError")}
        </div>
      ) : medications.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      ) : (
        <MedicationsTable medications={medications} />
      )}
      {medications.length > 0 && <AiNotice />}

    </AppLayout>
  );
}
